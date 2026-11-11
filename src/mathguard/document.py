"""Check a whole worked solution written in Markdown/LaTeX.

``check_document`` finds the formulas in a text (``$...$``, ``$$...$$``,
``\\[...\\]``, ``align`` …), splits them into chains ``a = b = c``, and checks
every link:

* symbolic steps with :func:`mathguard.check_equal`,
* purely numerical steps (``\\approx 35{,}3\\,\\mathrm{m}``) with a tolerance
  that matches the number of digits written,
* optionally the dimensions of every step, if units for the variables are given.

A formula that starts with a single name (``T = \\frac{2 v_0 \\sin\\alpha}{g}``)
defines that name. Later steps that only hold after inserting such definitions
are accepted, and the report says which definitions were used.

>>> r = check_document(r"$$ (a+b)^2 = a^2 + 2ab + b^2 = a^2 + b^2 $$")
>>> r.status.value
'refuted'
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import sympy as sp

from ._timeout import run_with_limit
from .checks import check_equal, check_value
from .latex import latex_to_expr
from .parsing import ParseError, parse
from .units import check_dimensions
from .verdict import Status, Verdict, worst

_ENV = r"(?:align|equation|gather|eqnarray|multline|flalign|alignat)\*?"
_MATH = re.compile(
    r"\\begin\{(?P<env>" + _ENV + r")\}(?:\{\d+\})?(?P<a>.*?)\\end\{(?P=env)\}"
    r"|\$\$(?P<b>.*?)\$\$"
    r"|\\\[(?P<c>.*?)\\\]"
    r"|\\\((?P<d>.*?)\\\)"
    r"|(?<![\\$])\$(?!\$)(?P<e>[^$\n]+?)(?<!\\)\$",
    re.S,
)
_REL = {"=": "=", "\\approx": "≈", "\\neq": "≠", "\\ne": "≠", "\\leq": "≤", "\\le": "≤",
        "\\geq": "≥", "\\ge": "≥", "<": "<", ">": ">", "\\equiv": "≡",
        "\\simeq": "≈", "\\sim": "~", "\\propto": "∝"}
_BREAK = {"\\Rightarrow", "\\implies", "\\Leftrightarrow", "\\iff", "\\to",
          "\\rightarrow", "\\longrightarrow", "\\Longrightarrow"}
#: Seconds allowed for solving one equation for one variable.
SOLVE_TIMEOUT = 3.0
#: How many earlier equations a new equation is compared with.
MAX_EARLIER = 6

_UNIT_MARK = re.compile(r"\\(?:mathrm|text|textrm|mathsf|unit|si)\s*\{")


class _Positive(dict):
    """Assumption mapping: every variable is positive unless stated otherwise."""

    def get(self, key, default=None):  # noqa: D401 - dict API
        return super().get(key, "positive")

    def __bool__(self) -> bool:  # an empty mapping must still count
        return True


@dataclass
class Step:
    """One link of a chain in the document."""

    line: int
    latex: str
    relation: str
    verdicts: list[Verdict] = field(default_factory=list)
    note: str | None = None

    @property
    def status(self) -> Status | None:
        return worst([v.status for v in self.verdicts]) if self.verdicts else None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"line": self.line, "latex": self.latex,
                             "status": self.status.value if self.status else "skipped"}
        if self.note:
            d["note"] = self.note
        if self.verdicts:
            d["results"] = [v.to_dict() for v in self.verdicts]
        return d


@dataclass
class DocumentReport:
    steps: list[Step]
    formulas: int
    definitions: dict[str, str] = field(default_factory=dict)

    @property
    def checked(self) -> list[Step]:
        return [s for s in self.steps if s.verdicts]

    @property
    def status(self) -> Status:
        statuses = [s.status for s in self.checked]
        return worst(statuses) if statuses else Status.INCONCLUSIVE  # type: ignore[arg-type]

    @property
    def ok(self) -> bool:
        return self.status.ok

    @property
    def first_error(self) -> Step | None:
        return next((s for s in self.steps if s.status == Status.REFUTED), None)

    def to_dict(self) -> dict[str, Any]:
        first = self.first_error
        return {
            "status": self.status.value,
            "ok": self.ok,
            "formulas": self.formulas,
            "checked_steps": len(self.checked),
            "skipped_steps": len(self.steps) - len(self.checked),
            "first_error_line": first.line if first else None,
            "definitions": self.definitions,
            "steps": [s.to_dict() for s in self.steps],
        }

    def _lines(self, markdown: bool) -> list[str]:
        icon = {Status.VERIFIED: "✔", Status.LIKELY: "≈", Status.REFUTED: "✘",
                Status.INCONCLUSIVE: "?", Status.ERROR: "!", None: "·"}
        out = []
        for s in self.steps:
            st = s.status
            label = st.value if st else "skipped"
            code = f"`{s.latex}`" if markdown else s.latex
            out.append(f"{icon[st]} line {s.line}: {code}  [{label}]")
            for v in s.verdicts:
                if v.status != Status.VERIFIED or v.check == "dimensions":
                    out.append(f"    {v.check}: {v.message}")
                if v.counterexample:
                    pairs = ", ".join(f"{k} = {val}" for k, val in v.counterexample.items())
                    out.append(f"    counterexample: {pairs}")
            if s.note:
                out.append(f"    note: {s.note}")
        return out

    def __str__(self) -> str:
        head = (f"mathguard report: {self.formulas} formulas, "
                f"{len(self.checked)} steps checked, "
                f"{len(self.steps) - len(self.checked)} skipped")
        first = self.first_error
        tail = f"\nOverall: {self.status.value.upper()}"
        if first:
            tail += f" (first error in line {first.line})"
        return "\n".join([head, ""] + self._lines(False) + [tail])

    def to_markdown(self) -> str:
        first = self.first_error
        head = [f"**mathguard: {self.status.value.upper()}**"
                + (f" — first error in line {first.line}" if first else ""), ""]
        return "\n".join(head + [f"- {ln}" if not ln.startswith("    ") else f"  {ln.strip()}"
                                 for ln in self._lines(True)])


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def _formulas(text: str) -> list[tuple[int, str, bool]]:
    """Return (line, latex, is_multiline_env) for every formula in the text."""
    out = []
    for m in _MATH.finditer(text):
        body = next(g for g in (m.group("a"), m.group("b"), m.group("c"),
                                m.group("d"), m.group("e")) if g is not None)
        line = text.count("\n", 0, m.start()) + 1
        # starting line of the first non-empty content
        lead = len(body) - len(body.lstrip())
        line += body[:lead].count("\n")
        out.append((line, body, m.group("a") is not None))
    return out


def _clean(body: str) -> str:
    body = re.sub(r"\\(?:label|tag)\*?\{[^}]*\}", " ", body)
    body = re.sub(r"\\(?:nonumber|notag)\b", " ", body)
    # "\quad\text{(Energieerhaltung)}" style comments
    body = re.sub(r"\\q?quad\s*\\text\{[^}]*\}", " ", body)
    body = re.sub(r"\\text\{\s*[,.;]?\s*(?:und|and|mit|with|also|so|daher|thus)?\s*\}", " ", body)
    return body


def _split_top(s: str, seps: re.Pattern) -> list[tuple[str | None, str]]:
    """Split at separators that are not inside braces/parentheses."""
    parts: list[tuple[str | None, str]] = []
    depth, start, i, sep = 0, 0, 0, None
    while i < len(s):
        ch = s[i]
        if ch in "{([":
            depth += 1
        elif ch in "})]":
            depth -= 1
        elif depth == 0:
            m = seps.match(s, i)
            if m:
                parts.append((sep, s[start:i]))
                sep = m.group(0)
                i = m.end()
                start = i
                continue
        if ch == "\\":
            m = re.match(r"\\[A-Za-z]+|\\.", s[i:])
            if m:
                # don't treat "\left(" as a depth change twice; skip the command
                i += len(m.group(0))
                continue
        i += 1
    parts.append((sep, s[start:]))
    return parts


_REL_PAT = re.compile(r"\\(?:approx|neq|ne|leq|le|geq|ge|equiv|simeq|sim|propto)(?![A-Za-z])|=|<|>")
_BREAK_PAT = re.compile(r"\\(?:Rightarrow|implies|Leftrightarrow|iff|to|rightarrow|"
                        r"longrightarrow|Longrightarrow)(?![A-Za-z])")
_STATEMENT_PAT = re.compile(r"\\q?quad(?![A-Za-z])|;|,(?=\s|\\[,;: ]|\\q?quad)")


def _chains(body: str, multiline: bool) -> list[list[tuple[str | None, str, int]]]:
    """Split a formula into chains of (relation, side, row offset)."""
    rows = re.split(r"\\\\(?:\[[^\]]*\])?", body)
    chains: list[list[tuple[str | None, str, int]]] = []
    offset = 0
    for row in rows:
        row_line = offset
        offset += row.count("\n")
        row = row.replace("&", " ").strip().rstrip(".,;").strip()
        if not row:
            continue
        for _, piece in _split_top(row, _BREAK_PAT):
            for _, stmt in _split_top(piece, _STATEMENT_PAT):
                stmt = stmt.strip().rstrip(".,;").strip()
                if not stmt:
                    continue
                sides = _split_top(stmt, _REL_PAT)
                if len(sides) == 1 and not chains:
                    chains.append([(None, sides[0][1].strip(), row_line)])
                    continue
                first_rel, first_side = sides[0]
                if not first_side.strip() and chains and multiline:
                    # continuation row: "&= ..." continues the previous chain
                    chain = chains[-1]
                    for rel, side in sides[1:]:
                        chain.append((rel, side.strip(), row_line))
                else:
                    chains.append([(rel, side.strip(), row_line) for rel, side in sides])
    return [c for c in chains if c and c[0][1]]


# --------------------------------------------------------------------------
# checking
# --------------------------------------------------------------------------

def _strip_units(latex: str) -> tuple[str, bool]:
    """Remove unit markup such as ``\\,\\mathrm{m/s^2}``. Returns (text, had_units)."""
    had = False
    out, i = [], 0
    for m in _UNIT_MARK.finditer(latex):
        start = m.start()
        # find the matching brace
        depth, j = 1, m.end()
        while j < len(latex) and depth:
            depth += {"{": 1, "}": -1}.get(latex[j], 0)
            j += 1
        content = latex[m.end():j - 1]
        out.append(latex[i:start])
        word = re.sub(r"[^A-Za-z]", "", content)
        if content.strip() in ("e", "d") or (word in ("sin", "cos", "tan", "ln", "exp", "log")):
            out.append(latex[start:j])
        else:
            had = True
            # keep a unit-free placeholder so "x\,\mathrm{m}" stays "x"
        # also drop a following exponent of the unit (\mathrm{m}^2)
        k = j
        if latex[k:k + 1] == "^":
            k += 1
            if latex[k:k + 1] == "{":
                depth, k = 1, k + 1
                while k < len(latex) and depth:
                    depth += {"{": 1, "}": -1}.get(latex[k], 0)
                    k += 1
            else:
                k += 1
            if had:
                j = k
        i = j
    out.append(latex[i:])
    text = "".join(out)
    text = re.sub(r"\\[,;:!]\s*$", "", text).strip()
    return text, had


def _literal_tolerance(latex: str) -> float | None:
    """If ``latex`` is one written number, the relative precision it implies.

    ``35{,}3`` -> half a unit in the last place relative to the value (0.0014).
    """
    stripped, _ = _strip_units(latex)
    m = re.fullmatch(r"\s*-?\s*(\d+)(?:(?:\{,\}|[.,])(\d+))?\s*", stripped)
    if not m:
        return None
    whole, frac = m.group(1), m.group(2) or ""
    value = Decimal(f"{whole}.{frac}" if frac else whole)
    if value == 0:
        return None
    half_unit = Decimal(5) * Decimal(10) ** (-len(frac) - 1)
    return float(half_unit / abs(value)) * 1.01


@dataclass
class _Side:
    latex: str
    text: str | None
    expr: sp.Expr | None
    had_units: bool
    error: str | None = None

    @property
    def numeric(self) -> bool:
        return self.expr is not None and not self.expr.free_symbols


def _read_side(latex: str, assumptions: Mapping[str, object]) -> _Side:
    stripped, had = _strip_units(latex)
    try:
        text = latex_to_expr(stripped)
        expr = parse(text, assumptions)
    except ParseError as exc:
        return _Side(latex, None, None, had, str(exc))
    return _Side(latex, text, expr, had)


def _is_label(latex: str, side: _Side) -> str | None:
    """'T', 'v_0', 'x(T)', 'E_{kin}' at the start of a chain name a quantity."""
    if side.expr is not None and isinstance(side.expr, sp.Symbol):
        return side.expr.name
    if re.fullmatch(r"\s*[A-Za-z](?:_\{?[A-Za-z0-9]+\}?)?\s*(?:\\left)?\(.*\)(?:\\right\))?\s*",
                    latex) and "(" in latex:
        return None if side.expr is None else ""
    return None


def _subst(expr: sp.Expr, defs: Mapping[str, sp.Expr], skip: str | None = None) -> sp.Expr:
    for _ in range(5):  # definitions may refer to each other
        mapping = {s: defs[s.name] for s in expr.free_symbols
                   if s.name in defs and s.name != skip}
        if not mapping:
            break
        expr = expr.xreplace(mapping)
    return expr


def _pair(a: _Side, b: _Side, rel: str, defs: dict[str, sp.Expr],
          assumptions: Mapping[str, object], units: Mapping[str, str] | None,
          label: str) -> tuple[list[Verdict], str | None]:
    rel_name = _REL.get(rel, rel)
    if a.expr is None or b.expr is None:
        return [], f"not read: {(a.error or b.error)}"
    if rel_name not in ("=", "≈"):
        return [], f"relation '{rel_name}' is not checked"

    # purely numerical step (units removed): compare with the written precision
    if a.numeric and b.numeric:
        tol = _literal_tolerance(b.latex) or _literal_tolerance(a.latex) or 1e-9
        v = check_value(a.expr, b.expr, rel_tol=tol)
        v.check = label
        return [v], None

    if a.had_units or b.had_units:
        return [], "mixes symbols and units; not checked"
    if rel_name == "≈":
        return [], "approximation between formulas is not checked"

    v = check_equal(a.expr, b.expr, assumptions, label=label)
    note = None
    if v.status == Status.REFUTED and defs:
        a2, b2 = _subst(a.expr, defs), _subst(b.expr, defs)
        if a2 != a.expr or b2 != b.expr:
            v2 = check_equal(a2, b2, assumptions, label=label)
            if v2.ok:
                used = sorted({s.name for s in (a.expr.free_symbols | b.expr.free_symbols)
                               if s.name in defs})
                note = f"holds after inserting {', '.join(used)}"
                v = v2
    verdicts = [v]
    if units:
        names = {s.name for s in (a.expr.free_symbols | b.expr.free_symbols)}
        missing = sorted(n for n in names if n not in units)
        if not missing:
            dv = check_dimensions(units, lhs=a.text, rhs=b.text)
            verdicts.append(dv)
        else:
            extra = f"no unit for {', '.join(missing)}; dimensions not checked"
            note = f"{note}; {extra}" if note else extra
    return verdicts, note


@dataclass
class _Equation:
    line: int
    lhs: sp.Expr
    rhs: sp.Expr
    bad: bool = False


def _solve(eq: sp.Expr, x: sp.Symbol) -> list[sp.Expr]:
    sols = run_with_limit(lambda: sp.solve(eq, x), SOLVE_TIMEOUT)
    if not sols:
        return []
    return [s for s in sols if not isinstance(s, dict)][:4]


def _relate(new: _Equation, earlier: list[_Equation], defs: Mapping[str, sp.Expr],
            assumptions: Mapping[str, object], label: str) -> tuple[Verdict | None, str]:
    """Does ``new`` follow from (or contradict) one of the earlier equations?"""
    r_new = sp.expand(_subst(new.lhs, defs) - _subst(new.rhs, defs))
    if r_new == 0:
        return None, "trivial"
    contradiction: tuple[int, sp.Symbol, sp.Expr, sp.Expr] | None = None
    for old in reversed(earlier[-MAX_EARLIER:]):
        r_old = _subst(old.lhs, defs) - _subst(old.rhs, defs)
        lhs_syms = new.lhs.free_symbols
        common = sorted(r_new.free_symbols & r_old.free_symbols,
                        key=lambda s: (s not in lhs_syms, s.name))
        for x in common:
            for sol in _solve(r_old, x):
                if x in sol.free_symbols:
                    continue
                v = check_equal(r_new.xreplace({x: sol}), sp.Integer(0), assumptions,
                                label=label)
                if v.ok:
                    v.message = f"follows from line {old.line}"
                    if old.bad:
                        v.message += f" (so it inherits the error in line {old.line})"
                    v.counterexample = None
                    return v, ""
                if contradiction is None:
                    for mine in _solve(r_new, x):
                        if x not in mine.free_symbols and mine.free_symbols and \
                                mine.free_symbols == sol.free_symbols:
                            contradiction = (old.line, x, mine, sol)
                            break
    if contradiction:
        line, x, mine, theirs = contradiction
        return Verdict(label, Status.REFUTED,
                       f"contradicts line {line}: here {x} = {sp.sstr(mine)}, "
                       f"but line {line} gives {x} = {sp.sstr(theirs)}",
                       method="solving both equations"), ""
    return None, "new equation (not derived from earlier ones)"


def check_document(
    text: str,
    units: Mapping[str, str] | None = None,
    assumptions: Mapping[str, object] | None = None,
    *,
    positive: bool = True,
) -> DocumentReport:
    """Check every formula chain in a Markdown/LaTeX solution.

    ``units`` maps variable names (as mathguard reads them: ``v_0`` → ``v0``) to
    units and switches on a dimension check for every step. With
    ``positive=True`` (the default, as usual in physics) variables are taken
    to be positive unless ``assumptions`` says otherwise.
    """
    if positive:
        assume: Mapping[str, object] = _Positive(assumptions or {})
    else:
        assume = dict(assumptions or {})
    formulas = _formulas(text)
    steps: list[Step] = []
    defs: dict[str, sp.Expr] = {}
    shown_defs: dict[str, str] = {}

    equations: list[_Equation] = []
    # Pre-pass: plain definitions ("with U_0 = Q_0/C") may come after their use.
    later: dict[str, sp.Expr] = {}
    for _line, body, multiline in formulas:
        for chain in _chains(_clean(body), multiline):
            if len(chain) != 2:
                continue
            head = _read_side(chain[0][1], assume)
            if head.expr is None or not isinstance(head.expr, sp.Symbol):
                continue
            tail = _read_side(chain[1][1], assume)
            if tail.expr is not None and not tail.numeric and not tail.had_units and \
                    head.expr not in tail.expr.free_symbols:
                later.setdefault(head.expr.name, tail.expr)

    for line, body, multiline in formulas:
        for chain in _chains(_clean(body), multiline):
            sides = [(rel, _read_side(lx, assume), lx, off) for rel, lx, off in chain]
            if len(sides) < 2:
                continue
            first = sides[0][1]
            name = _is_label(sides[0][2], first)
            # definitions from later in the text only help to check rewritings,
            # never to justify an equation (that would be circular)
            earlier_defs = {n: e for n, e in defs.items() if n != name}
            others = {n: e for n, e in {**later, **defs}.items() if n != name}
            # the last symbolic side carries the result of the chain
            last = next((s for _, s, _, _ in reversed(sides[1:])
                         if s.expr is not None and not s.numeric and not s.had_units), None)
            start = 0
            if name is not None:
                start = 1
                if name and last is not None and \
                        name not in {x.name for x in last.expr.free_symbols}:
                    eq = _Equation(line + sides[0][3], first.expr, last.expr)
                    verdict, note = _relate(eq, equations, earlier_defs, assume,
                                            f"line {eq.line}")
                    if verdict is not None:
                        steps.append(Step(eq.line, f"{sides[0][2]} = {last.latex}", "=",
                                          [verdict], None))
                        eq.bad = verdict.status == Status.REFUTED or \
                            "inherits the error" in verdict.message
                    equations.append(eq)
                    defs[name] = last.expr
                    shown_defs[name] = sp.sstr(last.expr)
            for k in range(start, len(sides) - 1):
                rel, b, blx, off = sides[k + 1]
                a, alx = sides[k][1], sides[k][2]
                step_line = line + off
                lx = f"{alx} {rel} {blx}".strip()
                verdicts, note = _pair(a, b, rel or "=",
                                       earlier_defs if (k == 0 and name is None) else others,
                                       assume, units, f"line {step_line}")
                if k == 0 and name is None and verdicts and \
                        verdicts[0].status == Status.REFUTED and \
                        a.expr is not None and b.expr is not None and \
                        not (a.numeric and b.numeric):
                    # not an identity: read the first link as an equation
                    eq = _Equation(step_line, a.expr, last.expr if last else b.expr)
                    v, why = _relate(eq, equations, earlier_defs, assume,
                                     f"line {step_line}")
                    dims = [d for d in verdicts[1:]]
                    verdicts = ([v] if v else []) + dims
                    if why.startswith("new equation"):
                        why = ("new equation, not derived from earlier ones "
                               "(as an identity it would be false)")
                    note = why or note
                    eq.bad = bool(v) and (v.status == Status.REFUTED
                                          or "inherits the error" in v.message)
                    equations.append(eq)
                steps.append(Step(step_line, lx, _REL.get(rel or "=", rel or "="),
                                  verdicts, note))
    return DocumentReport(steps, len(formulas), shown_defs)

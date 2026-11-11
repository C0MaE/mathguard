"""Grade an answer against a reference solution.

``check_answer`` finds the final result for every wanted quantity in an
answer (Markdown, LaTeX or plain text), and compares it with the reference:

* formulas symbolically (``sqrt(10 g h / 7)`` equals ``sqrt(70 g h) / 7``),
* numbers with units, converted with Pint (``14.8 km/h`` equals ``4.1 m/s``),
* with a tolerance for rounding: the larger of ``rel_tol`` and half a unit in
  the last digit that was written.

If a formula answer and a numerical reference meet (or the other way round),
the formula is evaluated with the ``given`` values.

>>> r = check_answer("so $v = \\\\sqrt{2 g h}$", "v = sqrt(10 g h / 7)", steps=False)
>>> r.status.value
'wrong'
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any

import sympy as sp

from .checks import check_equal
from .document import DocumentReport, _chains, _clean, _formulas, check_document
from .latex import latex_to_expr
from .parsing import ParseError, parse
from .units import DimensionError, _q, _ureg, _walk
from .verdict import Status, Verdict

#: Relative tolerance for numbers if the reference does not set one.
DEFAULT_REL_TOL = 0.01


class Grade(str, Enum):
    """Outcome for one wanted quantity (and, combined, for the whole answer)."""

    CORRECT = "correct"            # agrees with the reference
    WRONG = "wrong"                # disagrees with the reference
    MISSING = "missing"            # no result for this quantity found in the answer
    INCONCLUSIVE = "inconclusive"  # found, but could not be compared


# --------------------------------------------------------------------------
# result types
# --------------------------------------------------------------------------

@dataclass
class Extracted:
    """The result for one quantity as it was read from the answer."""

    name: str
    line: int
    text: str
    formula: str | None = None      # mathguard syntax
    value: float | None = None
    unit: str | None = None
    value_text: str | None = None   # the number as written ("4,10")
    boxed: bool = False
    tol: float = 0.0                # rounding tolerance of the written number
    formula_line: int | None = None # if the formula comes from an earlier line
    formula_text: str | None = None # the formula as written (LaTeX or text)
    expr: Any = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        d = {"name": self.name, "line": self.line, "text": self.text,
             "formula": self.formula, "value": self.value, "unit": self.unit,
             "formula_line": self.formula_line}
        if self.boxed:
            d["boxed"] = True
        return {k: v for k, v in d.items() if v is not None}

    def short(self) -> str:
        parts = []
        if self.formula:
            parts.append(self.formula_text or self.formula)
        if self.value is not None:
            parts.append(f"{self.value_text or self.value}" + (f" {self.unit}" if self.unit else ""))
        return f"{self.name} = " + " = ".join(parts) if parts else self.text


@dataclass
class QuantityResult:
    name: str
    grade: Grade
    message: str
    extracted: Extracted | None = None
    verdicts: list[Verdict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.grade == Grade.CORRECT

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "grade": self.grade.value,
                             "message": self.message}
        if self.extracted:
            d["extracted"] = self.extracted.to_dict()
        if self.verdicts:
            d["results"] = [v.to_dict() for v in self.verdicts]
        return d


_ICON = {Grade.CORRECT: "✔", Grade.WRONG: "✘", Grade.MISSING: "∅", Grade.INCONCLUSIVE: "?"}


@dataclass
class AnswerReport:
    """Grades for all wanted quantities, plus the step check of the working."""

    results: list[QuantityResult]
    steps: DocumentReport | None = None

    @property
    def status(self) -> Grade:
        grades = [r.grade for r in self.results]
        if not grades:
            return Grade.INCONCLUSIVE
        if Grade.WRONG in grades:
            return Grade.WRONG
        if all(g == Grade.CORRECT for g in grades):
            return Grade.CORRECT
        if all(g == Grade.MISSING for g in grades):
            return Grade.MISSING
        return Grade.INCONCLUSIVE

    @property
    def ok(self) -> bool:
        return self.status == Grade.CORRECT

    @property
    def score(self) -> float:
        return sum(r.ok for r in self.results) / len(self.results) if self.results else 0.0

    @property
    def extracted(self) -> dict[str, Extracted | None]:
        return {r.name: r.extracted for r in self.results}

    def __getitem__(self, name: str) -> QuantityResult:
        for r in self.results:
            if r.name == name:
                return r
        raise KeyError(name)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status.value,
            "ok": self.ok,
            "score": round(self.score, 4),
            "correct": sum(r.ok for r in self.results),
            "total": len(self.results),
            "quantities": [r.to_dict() for r in self.results],
        }
        if self.steps is not None:
            first = self.steps.first_error
            d["steps"] = {"status": self.steps.status.value,
                          "checked_steps": len(self.steps.checked),
                          "first_error_line": first.line if first else None}
        return d

    def _lines(self, markdown: bool) -> list[str]:
        out = []
        for r in self.results:
            name = f"`{r.name}`" if markdown else r.name
            where = f" (line {r.extracted.line})" if r.extracted else ""
            out.append(f"{_ICON[r.grade]} {name}{where}: {r.grade.value} — {r.message}")
        if self.steps is not None and self.steps.checked:
            first = self.steps.first_error
            if first:
                out.append(f"✘ working: first error in line {first.line}: {first.latex}")
            else:
                out.append(f"· working: {len(self.steps.checked)} steps checked, "
                           f"no error found ({self.steps.status.value})")
        return out

    def __str__(self) -> str:
        correct = sum(r.ok for r in self.results)
        head = f"mathguard answer check: {correct}/{len(self.results)} correct"
        return "\n".join([head, ""] + self._lines(False)
                         + [f"\nOverall: {self.status.value.upper()}"])

    def to_markdown(self) -> str:
        correct = sum(r.ok for r in self.results)
        head = f"**mathguard: {self.status.value.upper()}** ({correct}/{len(self.results)} correct)"
        return "\n".join([head, ""] + [f"- {line}" for line in self._lines(True)])


# --------------------------------------------------------------------------
# reading numbers with units
# --------------------------------------------------------------------------

_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
_UNICODE = [("·", "*"), ("×", "*"), ("−", "-"), ("–", "-"), ("√", "sqrt"),
            ("°C", " degC"), ("°", " degree"), ("%", " percent"), ("≈", "="),
            ("\u00a0", " "), ("\u202f", " ")]
_GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon",
          "ζ": "zeta", "η": "eta", "θ": "theta", "κ": "kappa", "λ": "lambda", "μ": "mu",
          "µ": "mu", "ν": "nu", "ξ": "xi", "π": "pi", "ρ": "rho", "σ": "sigma", "τ": "tau",
          "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega", "Γ": "Gamma", "Δ": "Delta",
          "Θ": "Theta", "Λ": "Lambda", "Φ": "Phi", "Ψ": "Psi", "Ω": "Omega"}
_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_FUNC_POW = re.compile(r"\b(sin|cos|tan|sinh|cosh|tanh|ln|log)\s*\^\s*(\d+)\s*\(")


def _plain(text: str, quantity: bool = False) -> str:
    """Unicode maths (√, ², ·, ω) to mathguard syntax.

    With ``quantity=True`` "µ" and "Ω" are read as unit prefixes/units.
    """
    for a, b in _UNICODE:
        text = text.replace(a, b)
    if quantity:
        text = re.sub(r"[µμ](?=[A-Za-z])", "u", text).replace("Ω", "ohm")
    for g, name in _GREEK.items():
        text = re.sub(g + r"(?=[A-Za-z])", name + " ", text)
        text = text.replace(g, name)
    text = text.translate(_SUBSCRIPTS)
    text = re.sub(r"([A-Za-z0-9)\]])([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)",
                  lambda m: f"{m.group(1)}^{m.group(2).translate(_SUPERSCRIPTS)}", text)
    text = re.sub(r"sqrt\s*([A-Za-z0-9]+)(?![A-Za-z0-9(])", r"sqrt(\1)", text)
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)  # decimal comma
    if not quantity:
        text = text.replace("[", "(").replace("]", ")")
        text = re.sub(r"(?<=[A-Za-z0-9])'", "prime", text)
        # names with underscores as LaTeX would read them: R_a -> Ra, x_{0} -> x0
        text = re.sub(r"\b([A-Za-z]+[0-9]*)_\{?([A-Za-z0-9]+)\}?", r"\1\2", text)
        # sin^2(x) -> sin(x)^2
        for _ in range(3):
            m = _FUNC_POW.search(text)
            if not m:
                break
            depth, j = 1, m.end()
            while j < len(text) and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            text = text[:m.start()] + f"{m.group(1)}({text[m.end():j - 1]})^{m.group(2)}" + text[j:]
    return text


_CANON = [(re.compile(r"^(?:var)?epsilon"), "eps"), (re.compile(r"^lambda"), "lam"),
          (re.compile(r"^(?:Delta|delta)(?=[A-Za-z])"), "d"), (re.compile(r"^vartheta"), "theta"),
          (re.compile(r"^varphi"), "phi")]


def _canon(name: str) -> str:
    """Spelling-independent form of a name: varepsilon_0 / epsilon0 / eps0 → eps0."""
    name = name.replace("_", "").replace("{", "").replace("}", "")
    for pat, rep in _CANON:
        name = pat.sub(rep, name)
    return name


def _unbrace(s: str, i: int) -> tuple[str, int]:
    """Content of the brace group starting at s[i] == '{'."""
    depth, j = 1, i + 1
    while j < len(s) and depth:
        depth += {"{": 1, "}": -1}.get(s[j], 0)
        j += 1
    return s[i + 1:j - 1], j


def _latex_plain(s: str) -> str:
    """Rough LaTeX → plain text, good enough for numbers with units."""
    s = s.replace("{,}", ".").replace("{.}", ".")
    s = re.sub(r"\\(?:left|right|displaystyle|textstyle)(?![A-Za-z])", "", s)
    s = re.sub(r"\^\s*\{?\\circ\}?\s*C", " degC", s)
    s = re.sub(r"\^\s*\{?\\circ\}?", " degree", s)
    s = re.sub(r"\\(?:,|;|:|!|\s|quad|qquad)|~", " ", s)
    s = s.replace("\\%", " percent")
    s = re.sub(r"\\(?:cdot|times)(?![A-Za-z])", "*", s)
    s = re.sub(r"\\Omega(?![A-Za-z])", "ohm", s)
    s = re.sub(r"\\(?:mu|micro)(?![A-Za-z])\s*", "u", s)
    s = re.sub(r"\\deg(?![A-Za-z])", " degree", s)
    # \mathrm{..}, \text{..}, \unit{..}, \si{..}: keep the content
    out, i = [], 0
    pat = re.compile(r"\\(?:mathrm|text|textrm|mathsf|mathit|operatorname|unit|si|mbox)\s*\{")
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:])
            break
        content, j = _unbrace(s, m.end() - 1)
        out.append(s[i:m.start()] + " " + content + " ")
        i = j
    s = "".join(out)
    # \frac{a}{b} -> (a)/(b)
    for _ in range(5):
        m = re.search(r"\\[dt]?frac\s*\{", s)
        if not m:
            break
        a, j = _unbrace(s, m.end() - 1)
        k = j
        while k < len(s) and s[k] == " ":
            k += 1
        if k < len(s) and s[k] == "{":
            b, k = _unbrace(s, k)
        else:
            b, k = s[k:k + 1], k + 1
        s = s[:m.start()] + f"({a})/({b})" + s[k:]
    s = re.sub(r"\^\s*\{\s*([-+]?\s*[\d.]+)\s*\}", lambda m: "^" + m.group(1).replace(" ", ""), s)
    s = s.replace("{", "(").replace("}", ")")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


_NUMBER = re.compile(
    r"^\s*(?P<num>[-+]?\s*(?:\d+(?:[.,]\d+)?|[.,]\d+))"
    r"(?:\s*(?:e|E)\s*(?P<e1>[-+]?\d+)|\s*\*\s*10\s*\^\s*\(?\s*(?P<e2>[-+]?\d+)\s*\)?)?"
    r"(?P<rest>.*)$")
_UNIT_TEXT = re.compile(r"^[\sA-Za-z/*^().\-0-9]*$")
_UNIT_TOKEN = re.compile(r"[A-Za-z]+")


def _rounding_tol(num: str, exponent: int = 0) -> float:
    """Half a unit in the last written digit, relative to the value."""
    num = num.replace(" ", "").replace(",", ".").lstrip("+-")
    try:
        value = Decimal(num) * Decimal(10) ** exponent
    except InvalidOperation:
        return 0.0
    if value == 0:
        return 0.0
    decimals = len(num.partition(".")[2])
    half = Decimal(5) * Decimal(10) ** (exponent - decimals - 1)
    return float(half / abs(value)) * 1.01


@dataclass
class _Quantity:
    value: float          # in the written unit
    unit: str | None      # pint unit string as written, None if no unit
    text: str
    tol: float            # rounding tolerance of the written number


def _read_quantity(text: str) -> _Quantity | None:
    """'4.10 m/s', '1.6e-3 kg', '5,33 s', '30 degree' → quantity, else None."""
    t = text.strip().rstrip(".;:")
    m = _NUMBER.match(t)
    if not m:
        return None
    num = m.group("num").replace(" ", "").replace(",", ".")
    exp = int(m.group("e1") or m.group("e2") or 0)
    rest = m.group("rest").strip()
    if rest.startswith("*"):
        rest = rest[1:].strip()
    try:
        value = float(num) * 10.0 ** exp
    except ValueError:
        return None
    tol = _rounding_tol(num, exp)
    if not rest:
        return _Quantity(value, None, t, tol)
    if not _UNIT_TEXT.match(rest) or re.search(r"\s[-+]\s|[-+]\s*\d+\s*[A-Za-z]", rest):
        return None
    if not _UNIT_TOKEN.search(rest):
        return None
    unit = re.sub(r"\s*\*\s*", " * ", rest)
    unit = re.sub(r"\^\s*\(?\s*([-+]?\d+)\s*\)?", r"^\1", unit)
    try:
        q = _ureg().Quantity(1.0, unit)
    except Exception:  # noqa: BLE001 - pint raises many kinds
        return None
    if not isinstance(q.magnitude, float):
        return None
    return _Quantity(value, unit.strip(), t, tol)


# --------------------------------------------------------------------------
# finding results in the answer
# --------------------------------------------------------------------------

@dataclass
class _Statement:
    name: str
    line: int
    pos: int
    sides: list[tuple[str, bool]]   # (text, is_latex)
    boxed: bool = False
    raw: str = ""


_LATEX_NAME = re.compile(r"^\s*(\\?[A-Za-z][A-Za-z0-9]*'?)\s*(?:_\s*(\{[^{}]*\}|[A-Za-z0-9]))?\s*$")


def _normalize_name(raw: str) -> str | None:
    """'v_0', 'v_{0}', '\\omega_{max}', 'E_kin' → 'v0', 'omega_max'-style names."""
    raw = raw.strip().strip("$").strip()
    raw = re.sub(r"\\(?:mathrm|text|mathit)\s*\{([^{}]*)\}", r"\1", raw)
    raw = re.sub(r"\s*\((?:[^()]*)\)\s*$", "", raw)      # x(t) -> x
    m = _LATEX_NAME.match(raw)
    if not m:
        return None
    base = m.group(1).lstrip("\\").replace("'", "prime")
    sub = (m.group(2) or "").strip("{} ")
    sub = re.sub(r"\\?([A-Za-z]+)", r"\1", sub).replace(" ", "")
    if not re.fullmatch(r"[A-Za-z0-9]*", sub):
        return None
    return base + sub


def _name_key(name: str) -> str:
    return _canon(name)


_BOXED = re.compile(r"\\boxed\s*\{")
# Headings that mark the final result (English and German, as in the benchmark answers)
_RESULT_WORDS = (r"(?:Ergebnis|Endergebnis|Resultat|Result|Results|Antwort|Answer|"
                 r"Final answer|Lösung|Loesung|Solution)")
_PLAIN_LABEL = re.compile(
    r"(?<![\w\\$])(?P<name>[A-Za-z][A-Za-z0-9]*(?:_\{?[A-Za-z0-9]+\}?)?)"
    r"\s*(?:\([A-Za-z0-9_, ]*\))?\s*(?:\[[^\]\n]*\])?\s*(?P<rel>=|≈|~=|\\approx)(?!=)")
_PLAIN_SPLIT = re.compile(r"\s(?:=|≈|~=)\s|(?<=[^=<>!])=(?!=)|≈")
_PLAIN_END = re.compile(r"(?:[.;](?:\s|$)|,\s+(?=[A-Za-zÄÖÜäöüß]{2,})"
                        r"|\s+(?:und|and|bzw|also|so|mit|with|wobei|where)\s)")


def _unbox(latex: str) -> tuple[str, bool]:
    m = _BOXED.search(latex)
    if not m:
        return latex, False
    content, j = _unbrace(latex, m.end() - 1)
    return latex[:m.start()] + content + latex[j:], True


def _mask_math(line: str) -> str:
    """Replace math segments by spaces (same length) so plain labels are found outside."""
    return re.sub(r"\$\$.*?\$\$|\$[^$]*\$|\\\(.*?\\\)", lambda m: " " * len(m.group(0)), line)


_WORD = re.compile(r"(?<=\s)([A-Za-zÄÖÜäöüß]{2,})(?=[\s,.;:!?]|$)")


def _cut_prose(text: str) -> str:
    """'2 m/s would be too slow' → '2 m/s': two words in a row that are not maths end it."""
    from .parsing import CONSTANTS, FUNCTIONS

    def prose(word: str) -> bool:
        return not (word in FUNCTIONS or word in CONSTANTS or word in _GREEK.values()) and \
            (len(word) >= 3 or word.lower() in {"is", "in", "at", "an", "am", "be", "so",
                                                 "da", "es", "if", "or", "of", "to"})

    words = list(_WORD.finditer(" " + text))
    for w1, w2 in zip(words, words[1:], strict=False):
        between = (" " + text)[w1.end():w2.start()]
        if between.strip(" ,") == "" and prose(w1.group(1)) and prose(w2.group(1)):
            return text[:w1.start() - 1].rstrip(" ,;:")
    return text


def _split_plain_sides(rest: str) -> list[tuple[str, bool]]:
    """Split 'sqrt(2gh) = $4{,}1\\,\\mathrm{m/s}$ ≈ 4.1 m/s' into sides."""
    sides: list[tuple[str, bool]] = []
    # cut at the end of the sentence (outside math)
    masked = _mask_math(rest)
    depth = 0
    for i, ch in enumerate(masked):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0 and _PLAIN_END.match(masked, i):
            rest, masked = rest[:i], masked[:i]
            break
    pieces, start, depth = [], 0, 0
    i = 0
    while i < len(masked):
        ch = masked[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0:
            m = _PLAIN_SPLIT.match(masked, i)
            if m and m.group(0):
                pieces.append(rest[start:i])
                i = m.end()
                start = i
                continue
        i += 1
    pieces.append(rest[start:])
    for p in pieces:
        p = p.strip().strip("*").strip().rstrip(",").strip()
        # "0,45 (0,448)": a remark in parentheses after a number
        p = re.sub(r"^([-+]?\d[\d.,]*(?:\s*[A-Za-z/^\-0-9]+)?)\s+\([^()]*\)$", r"\1", p)
        if not p:
            continue
        maths = re.fullmatch(r"\$\$?(.*?)\$?\$", p, re.S)
        if maths:
            sides.append((maths.group(1), True))
        elif "\\" in p and "$" not in p:
            sides.append((p, True))   # raw LaTeX without dollar signs
        elif "$" in p:
            inner = re.findall(r"\$([^$]+)\$", p)
            sides.extend((x, True) for x in inner)
        else:
            sides.append((_cut_prose(p), False))
    return sides


def _statements(text: str) -> list[_Statement]:
    out: list[_Statement] = []
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]

    # 1. LaTeX formulas: chains that start with a name
    for line, body, multiline in _formulas(text):
        pos = line_starts[min(line, len(line_starts)) - 1]
        body, boxed = _unbox(body)
        for chain in _chains(_clean(body), multiline):
            if len(chain) < 2:
                continue
            name = _normalize_name(chain[0][1])
            if not name:
                continue
            sides = [(side, True) for rel, side, _ in chain[1:]
                     if (rel or "=") in ("=", "\\approx", "\\simeq")]
            if sides:
                out.append(_Statement(name, line + chain[0][2], pos, sides, boxed,
                                      raw=" = ".join(s for _, s, _ in chain)))
    # 2. plain-text lines ("v = sqrt(2 g h) = 6.3 m/s", "tv [time] = $\frac{..}{..}$")
    # lines of a block under a heading such as "Result" / "Ergebnis" (until a blank line)
    result_lines: set[int] = set()
    in_result = False
    for idx, line in enumerate(text.split("\n")):
        if re.fullmatch(r"[\s#*_>:-]*" + _RESULT_WORDS + r"[\s*_:.-]*", line, re.I):
            in_result = True
            continue
        if in_result and not line.strip() and any(i in result_lines for i in range(idx - 1, idx + 1)):
            in_result = False
        if in_result and line.strip():
            result_lines.add(idx + 1)
        masked = _mask_math(line)
        matches = []
        for m in _PLAIN_LABEL.finditer(masked):
            if matches and not re.search(
                    r"(?:[,;:]|\s(?:und|and|bzw|so|also|mit|with|sowie))\s*$",
                    masked[matches[-1].end():m.start()]):
                continue  # "v0^2 sin(2 alpha) / g = 35.3 m": g is not a new label
            matches.append(m)
        for k, m in enumerate(matches):
            name = _normalize_name(m.group("name"))
            if not name or name.lower() in {"ergebnis", "result", "answer", "antwort"}:
                continue
            stop = matches[k + 1].start() if k + 1 < len(matches) else len(line)
            rest = line[m.end():stop]
            sides = _split_plain_sides(rest)
            if sides:
                pos = line_starts[idx] + m.start()
                out.append(_Statement(name, idx + 1, pos, sides,
                                      boxed=bool(re.search(_RESULT_WORDS, line[:m.start()], re.I)),
                                      raw=line[m.start():stop].strip()))
    for st in out:
        if st.line in result_lines:
            st.boxed = True
    out.sort(key=lambda s: (s.line, s.pos))
    return out


_PART_HEAD = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*(?:(?:Teil|Teilaufgabe|Aufgabe|Part|Exercise)\s*)?"
    r"\(?(?P<part>[a-h])\)\s*|^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*(?:Teil|Teilaufgabe|Part)\s+"
    r"(?P<part2>[a-h])\b", re.I)


def _parts(text: str) -> dict[int, str]:
    """Line number → part letter ('a', 'b', …) from headings like 'b)' or '## Part b'."""
    current, out = "", {}
    for i, line in enumerate(text.split("\n"), start=1):
        m = _PART_HEAD.match(line)
        if m:
            current = (m.group("part") or m.group("part2")).lower()
        out[i] = current
    return out


# --------------------------------------------------------------------------
# comparing
# --------------------------------------------------------------------------

@dataclass
class _Ref:
    name: str
    formula: str | None = None
    value: float | None = None
    unit: str | None = None
    rel_tol: float | None = None
    aliases: tuple[str, ...] = ()
    part: str | None = None
    symbolic_only: bool = False
    raw: str | None = None


def _ref_from(name: str, spec: Any) -> _Ref:
    if isinstance(spec, (int, float)):
        return _Ref(name, value=float(spec))
    if isinstance(spec, str):
        ref = _Ref(name, raw=spec)
        for side in [s.strip() for s in re.split(r"(?<![<>!=])=(?!=)|≈", spec) if s.strip()]:
            q = _read_quantity(_plain(side, quantity=True))
            if q is not None:
                ref.value, ref.unit = q.value, q.unit
            elif ref.formula is None:
                ref.formula = side
        return ref
    if isinstance(spec, Mapping):
        formula = spec.get("formula")
        if formula is None and isinstance(spec.get("path_a"), Mapping):  # benchmark format
            formula = spec["path_a"].get("formula")
        value = spec.get("value")
        unit = spec.get("unit")
        if isinstance(value, str):
            q = _read_quantity(_plain(value, quantity=True))
            if q is None:
                raise ValueError(f"reference for '{name}': cannot read value '{value}'")
            value, unit = q.value, unit or q.unit
        aliases = spec.get("aliases") or ()
        if isinstance(aliases, str):
            aliases = (aliases,)
        return _Ref(name, formula, None if value is None else float(value), unit,
                    _tolerance(spec),
                    tuple(aliases), spec.get("part"), bool(spec.get("symbolic_only")))
    raise ValueError(f"reference for '{name}' must be a string, a number or a mapping")


def _tolerance(spec: Mapping[str, Any]) -> float | None:
    if spec.get("answer_tol") is not None:
        return float(spec["answer_tol"])
    if "path_a" in spec:   # benchmark tasks: rel_tol is the precision of the reference
        return None
    return None if spec.get("rel_tol") is None else float(spec["rel_tol"])


def _references(reference: Any) -> list[_Ref]:
    if isinstance(reference, str):
        refs = []
        for item in [x.strip() for x in re.split(r"[;\n]", reference) if x.strip()]:
            m = re.match(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*=(?!=)(.*)$", item)
            if m:
                refs.append(_ref_from(m.group(1), m.group(2)))
            else:
                refs.append(_ref_from("result", item))
        return refs
    if isinstance(reference, Mapping):
        return [_ref_from(str(k), v) for k, v in reference.items()]
    raise ValueError("reference must be a string or a mapping name -> reference")


class _Context:
    def __init__(self, given: Mapping[str, Any] | None, units: Mapping[str, str] | None,
                 assumptions: Mapping[str, object] | None):
        ureg = _ureg()
        self.values: dict[str, float] = {}
        self.units: dict[str, str] = dict(units or {})
        for name, raw in (given or {}).items():
            if isinstance(raw, (int, float)):
                self.values[name] = float(raw)
                self.units.setdefault(name, "dimensionless")
                continue
            q = _read_quantity(_plain(str(raw), quantity=True))
            if q is None:
                try:
                    pq = ureg.Quantity(str(raw))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"given value '{name}: {raw}' is not readable: {exc}") from None
                self.values[name] = float(pq.to_base_units().magnitude)
                self.units.setdefault(name, str(pq.units))
                continue
            unit = q.unit or "dimensionless"
            self.values[name] = float(ureg.Quantity(q.value, unit).to_base_units().magnitude)
            self.units.setdefault(name, unit)
        self.assume: dict[str, object] = {}
        for name in set(self.units) | set(self.values):
            self.assume[name] = "positive"
        self.assume.update(assumptions or {})

    def parse(self, formula: str) -> sp.Expr:
        class _Pos(dict):
            def get(s, key, default=None):  # noqa: N805
                return super().get(key, "positive")

            def __bool__(s):  # noqa: N805
                return True
        return parse(formula, _Pos(self.assume))

    def evaluate(self, expr: sp.Expr) -> tuple[Any | None, str]:
        """Value of a formula with the given values, as a Pint quantity in SI units."""
        missing = sorted(s.name for s in expr.free_symbols if s.name not in self.values)
        if missing:
            return None, f"no value given for {', '.join(missing)}"
        subs = {s: self.values[s.name] for s in expr.free_symbols}
        try:
            val = complex(sp.N(expr.xreplace(subs), 30))
        except (TypeError, ValueError) as exc:
            return None, f"cannot be evaluated: {exc}"
        if abs(val.imag) > 1e-12 * max(1.0, abs(val.real)):
            return None, f"value is complex ({val})"
        try:
            dim = _walk(expr, {n: _q(u) for n, u in self.units.items()})
            base = dim.to_base_units().units
        except DimensionError as exc:
            return None, f"dimension unknown: {exc}"
        return _ureg().Quantity(val.real, base), ""


def _formula_of(text: str, is_latex: bool) -> str | None:
    """A side as mathguard syntax, if it is a formula without units."""
    try:
        if is_latex:
            from .document import _strip_units
            stripped, had = _strip_units(text)
            if had:
                return None
            return latex_to_expr(stripped)
        plain = _plain(text)
        parse(plain)  # validate
        return plain
    except ParseError:
        return None


def _quantity_of(text: str, is_latex: bool) -> _Quantity | None:
    return _read_quantity(_latex_plain(text) if is_latex else _plain(text, quantity=True))


def _rename(expr: sp.Expr, known: set[str]) -> sp.Expr:
    """Rename symbols to the spelling used in the task (varepsilon0 → eps0)."""
    canon = {_canon(k): k for k in known}
    mapping = {}
    for sym in expr.free_symbols:
        if sym.name not in known and _canon(sym.name) in canon:
            target = canon[_canon(sym.name)]
            mapping[sym] = sp.Symbol(target, **sym.assumptions0)
    return expr.xreplace(mapping) if mapping else expr


def _charge_e(text: str, known: set[str]) -> str:
    """A lone 'e' means the elementary charge if the task calls it qe."""
    if "qe" in known and "e" not in known:
        return re.sub(r"(?<![\w.])e(?![\w^(])(?!\s*\^)", "qe", text)
    return text


def _extract(st: _Statement, ctx: _Context, known: set[str], *,
             strict: bool = True) -> Extracted:
    ex = Extracted(st.name, st.line, st.raw, boxed=st.boxed)
    fallback: str | None = None
    for text, is_latex in st.sides:
        q = _quantity_of(text, is_latex)
        if q is not None and q.unit and known:
            tokens = set(_UNIT_TOKEN.findall(q.unit))
            if len(tokens) >= 2 and tokens <= known:
                q = None  # "6 m g" is six times mass times g, not metre-grams
        if q is not None:
            ex.value, ex.unit = q.value, q.unit
            m = _NUMBER.match(q.text)
            ex.value_text = q.text[:m.start("rest")].strip()
            ex.tol = q.tol
            continue
        if ex.formula is None:
            f = _formula_of(text, is_latex)
            if f is None:
                continue
            f = _charge_e(f, known)
            try:
                parsed = ctx.parse(f)
            except ParseError:
                continue
            expr = _rename(parsed, known)
            syntax = f if expr == parsed else sp.sstr(expr)
            shown = text.strip() if is_latex else syntax
            names = {s.name for s in expr.free_symbols}
            if isinstance(expr, sp.Symbol) and (
                    _name_key(expr.name) == _name_key(st.name)
                    or (strict and known and expr.name not in known)):
                continue  # "alpha1 = alpha1 = ...", "Rth = R = ...": another name, not a result
            if not names:
                # a pure number expression such as 2/3 * 8 or sqrt(2)
                try:
                    v = float(sp.N(expr))
                except (TypeError, ValueError):
                    continue
                if ex.value is None:
                    ex.value, ex.value_text = v, sp.sstr(expr)
                continue
            if strict and known and not names <= known:
                # maybe "(4/15 m/s^3) t^3" (units read as symbols), or other variables;
                # keep it only if nothing better comes
                fallback = fallback or (syntax, shown, expr)
                continue
            ex.formula, ex.formula_text, ex.expr = syntax, shown, expr
    if ex.formula is None and fallback is not None:
        ex.formula, ex.formula_text, ex.expr = fallback
    return ex


def _compare(ref: _Ref, ex: Extracted, ctx: _Context, rel_tol: float,
             own: Mapping[str, tuple[sp.Expr, int]] | None = None) -> QuantityResult:
    verdicts: list[Verdict] = []
    notes: list[str] = []
    outcomes: list[Any] = []
    ureg = _ureg()
    tol = ref.rel_tol if ref.rel_tol is not None else rel_tol

    ref_expr = ans_expr = None
    if ref.formula:
        try:
            ref_expr = ctx.parse(ref.formula)
        except ParseError as exc:
            raise ValueError(f"reference formula for '{ref.name}' is not readable: {exc}") from None
    if ex.expr is not None:
        ans_expr = ex.expr
        if ex.formula_line:
            notes.append(f"formula from line {ex.formula_line}")

    # 1. formula against formula
    if ref_expr is not None and ans_expr is not None and ref_expr.free_symbols:
        allowed = {s.name for s in ref_expr.free_symbols} | set(ctx.values) | set(ctx.units)
        extra = {s.name for s in ans_expr.free_symbols} - allowed
        inserted: list[str] = []
        for _ in range(3):  # insert the answer's own results (t = 2 L / v, v = ...)
            subs = {sym: own[sym.name][0] for sym in ans_expr.free_symbols
                    if own and sym.name in extra and sym.name in own
                    and _name_key(sym.name) != _name_key(ref.name)}
            if not subs:
                break
            inserted += [f"{sym.name} (line {own[sym.name][1]})" for sym in subs]
            ans_expr = ans_expr.xreplace(subs)
            extra = {s.name for s in ans_expr.free_symbols} - allowed
        if inserted and not extra:
            notes.append(f"inserted {', '.join(inserted)} from the answer")
        if extra:
            notes.append(f"formula uses {', '.join(sorted(extra))}, which the reference "
                         "does not; formula not compared")
            outcomes.append(None)
        else:
            ans_expr, ref_expr = _vacuum_constants(ans_expr, ref_expr)
            v = check_equal(ans_expr, ref_expr, ctx.assume, label=f"{ref.name}: formula")
            verdicts.append(v)
            if v.status in (Status.VERIFIED, Status.LIKELY):
                outcomes.append(True)
                notes.append(f"formula {ex.formula_text or ex.formula} matches the reference"
                             + (" (numerically)" if v.status == Status.LIKELY else ""))
            elif v.status == Status.REFUTED and _same_with_given(ans_expr, ref_expr, ctx, tol):
                outcomes.append(True)
                notes.append(f"formula {ex.formula_text or ex.formula} matches the reference after inserting "
                             "the given values")
            elif v.status == Status.REFUTED and inserted:
                outcomes.append("inserted")  # decided below, together with the value
                notes.append(f"formula {ex.formula_text or ex.formula} differs from the "
                             f"reference {ref.formula}")
            elif v.status == Status.REFUTED:
                outcomes.append(False)
                notes.append(f"formula {ex.formula_text or ex.formula} differs from the "
                             f"reference {ref.formula}")
            else:
                outcomes.append(None)
                notes.append(f"formula could not be compared ({v.message})")

    # reference value as a Pint quantity
    ref_q = None
    if not ref.symbolic_only:
        if ref.value is not None:
            ref_q = ureg.Quantity(ref.value, ref.unit or "dimensionless")
        elif ref_expr is not None:
            ref_q, why = ctx.evaluate(ref_expr)
            if ref_q is not None and ref.unit:
                try:
                    ref_q = ref_q.to(ref.unit)
                except Exception:  # noqa: BLE001
                    pass

    # 2. number in the answer against the reference value
    if ex.value is not None and ref_q is not None:
        written_tol = ex.tol
        use_tol = max(tol, written_tol)
        if ex.unit:
            cands: list[tuple[float, str | None]] = []
            try:
                cands.append((ureg.Quantity(ex.value, ex.unit).to(ref_q.units).magnitude, None))
            except Exception:  # noqa: BLE001 - DimensionalityError, offset units …
                pass
            diff = _as_difference(ex.value, ex.unit, ref_q)
            if diff is not None:
                cands.append((diff, f"{ex.unit} read as a temperature difference"))
            ans_in_ref = None
            for val, why in cands:
                if math.isclose(val, ref_q.magnitude, rel_tol=use_tol):
                    ans_in_ref = val
                    if why:
                        notes.append(why)
                    break
            if ans_in_ref is None and cands:
                ans_in_ref = cands[0][0]
            if not cands:
                outcomes.append(False)
                notes.append(f"unit {ex.unit} does not fit the reference "
                             f"({_pretty(ref_q)}); different dimension")
        else:
            ans_in_ref = ex.value
            if not ref_q.dimensionless:
                notes.append(f"no unit written, read as {_unit_name(ref_q)}")
        if ans_in_ref is not None:
            close = math.isclose(ans_in_ref, ref_q.magnitude, rel_tol=use_tol, abs_tol=1e-300)
            outcomes.append(close)
            shown = f"{ex.value_text or ex.value}" + (f" {ex.unit}" if ex.unit else "")
            if close:
                notes.append(f"value {shown} matches {_pretty(ref_q)} "
                             f"(±{_pct(use_tol)})")
            else:
                rel = abs(ans_in_ref - ref_q.magnitude) / abs(ref_q.magnitude) \
                    if ref_q.magnitude else float("inf")
                notes.append(f"value {shown} differs from {_pretty(ref_q)} "
                             f"by {rel:.1%} (±{_pct(use_tol)})")
    # 3. formula only, reference only a number: evaluate the formula
    elif ex.value is None and ans_expr is not None and ref_q is not None and \
            (ref_expr is None or not ref_expr.free_symbols):
        val, why = ctx.evaluate(ans_expr)
        if val is None:
            outcomes.append(None)
            notes.append(f"formula could not be evaluated: {why}")
        else:
            try:
                got = val.to(ref_q.units).magnitude
                close = math.isclose(got, ref_q.magnitude, rel_tol=tol)
                outcomes.append(close)
                notes.append(f"formula gives {_pretty(val.to(ref_q.units))}, reference "
                             f"{_pretty(ref_q)}" + ("" if close else " — differs"))
            except Exception:  # noqa: BLE001
                outcomes.append(False)
                notes.append(f"formula has unit {_unit_name(val)}, reference {_unit_name(ref_q)}")

    if "inserted" in outcomes:
        # a formula that only disagrees after inserting the answer's own symbols may use
        # a name for something else; let a matching number win, else count it as wrong
        others = [o for o in outcomes if o not in (None, "inserted")]
        if True in others and False not in others:
            notes.append("the number matches, so the inserted symbol probably means "
                         "something else; formula not counted")
            outcomes = [o for o in outcomes if o != "inserted"]
        else:
            outcomes = [False if o == "inserted" else o for o in outcomes]
    known = [o for o in outcomes if o is not None]
    if any(o is False for o in known):
        grade = Grade.WRONG
    elif known:
        grade = Grade.CORRECT
    else:
        grade = Grade.INCONCLUSIVE
        if not notes:
            notes.append("nothing comparable found (no formula and no value that fits the reference)")
    return QuantityResult(ref.name, grade, "; ".join(notes), ex, verdicts)


def _vacuum_constants(a: sp.Expr, b: sp.Expr) -> tuple[sp.Expr, sp.Expr]:
    """Use c^2 = 1/(mu0 eps0) if one side writes eps0 and the other mu0."""
    names = {s.name: s for s in a.free_symbols | b.free_symbols}
    eps = next((names[n] for n in ("eps0", "epsilon0") if n in names), None)
    mu, c = names.get("mu0"), names.get("c")
    if eps is not None and mu is not None and c is not None:
        rule = {eps: 1 / (mu * c ** 2)}
        return a.xreplace(rule), b.xreplace(rule)
    return a, b


def _same_with_given(ans: sp.Expr, ref: sp.Expr, ctx: _Context, tol: float) -> bool:
    """Does the answer agree once the given numbers are inserted (c1 = 0.8 → 1.6 t)?

    Only used when the answer itself contains numbers instead of some given
    symbols. Remaining variables are sampled at random positive points.
    """
    ref_given = {s for s in ref.free_symbols if s.name in ctx.values}
    if not ref_given or not (ref_given - ans.free_symbols):
        return False
    subs = {s: ctx.values[s.name] for s in (ans.free_symbols | ref.free_symbols)
            if s.name in ctx.values}
    a, b = ans.xreplace(subs), ref.xreplace(subs)
    rest = sorted(a.free_symbols | b.free_symbols, key=lambda x: x.name)
    import random
    rng = random.Random(1)
    for _ in range(8 if rest else 1):
        point = {x: rng.uniform(0.5, 3.0) for x in rest}
        try:
            va, vb = complex(sp.N(a.xreplace(point))), complex(sp.N(b.xreplace(point)))
        except (TypeError, ValueError):
            return False
        if not math.isclose(abs(va - vb), 0.0, abs_tol=max(tol, 1e-9) * max(abs(va), abs(vb))):
            return False
    return True


def _as_difference(value: float, unit: str, ref_q) -> float | None:
    """3.5 degC as a temperature difference, expressed in the reference unit."""
    delta = {"degC": "delta_degC", "celsius": "delta_degC", "degF": "delta_degF",
             "fahrenheit": "delta_degF"}.get(unit.strip())
    if not delta:
        return None
    try:
        return _ureg().Quantity(value, delta).to(ref_q.units).magnitude
    except Exception:  # noqa: BLE001
        return None


def _pct(x: float) -> str:
    return f"{x * 100:.2g} %"


def _unit_name(q) -> str:
    u = f"{q.units:~P}"
    return u or "dimensionless"


def _pretty(q) -> str:
    u = f"{q.units:~P}"
    return f"{q.magnitude:.6g}" + (f" {u}" if u else "")


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def check_answer(
    answer: str,
    reference: str | Mapping[str, Any],
    *,
    given: Mapping[str, Any] | None = None,
    units: Mapping[str, str] | None = None,
    assumptions: Mapping[str, object] | None = None,
    rel_tol: float = DEFAULT_REL_TOL,
    steps: bool = True,
) -> AnswerReport:
    """Grade the final results in ``answer`` against ``reference``.

    ``reference`` is either a string such as ``"v = sqrt(10 g h / 7)"``
    (several quantities separated by ``;``), or a mapping
    ``{"v": {"formula": "sqrt(10 g h / 7)", "unit": "m/s", "value": 4.1}}``.
    Each entry may also set ``rel_tol``, ``aliases`` (other names the answer
    may use) and ``part`` (only look in the answer's part ``"b)"``).

    ``given`` holds the known values (``{"h": "1.2 m", "g": "9.81 m/s^2"}``);
    they are used to turn formulas into numbers. ``units`` gives units of
    further variables (``{"m": "kg"}``). Variables count as positive.

    With ``steps=True`` the working is also checked with
    :func:`check_document`, so a wrong result comes with the line where the
    calculation goes wrong (if it is a calculation error).
    """
    if not isinstance(answer, str):
        raise TypeError("answer must be a string")
    refs = _references(reference)
    ctx = _Context(given, units, assumptions)
    known: set[str] = set(ctx.values) | set(ctx.units)
    for r in refs:
        if r.raw and r.formula is None and r.unit and \
                len(set(_UNIT_TOKEN.findall(r.unit))) >= 2 and \
                set(_UNIT_TOKEN.findall(r.unit)) <= known:
            r.formula, r.value, r.unit = r.raw.strip(), None, None   # "6 m g": a formula
    for r in refs:
        if r.formula:
            try:
                known |= {s.name for s in ctx.parse(r.formula).free_symbols}
            except ParseError as exc:
                raise ValueError(f"reference formula for '{r.name}' is not readable: {exc}") from None

    statements = _statements(answer)
    parts = _parts(answer)
    # the answer's own results, to insert into later formulas (t = 2 L / v)
    own: dict[str, tuple[sp.Expr, int]] = {}
    for st in statements:
        if st.name in known:
            continue
        ex = _extract(st, ctx, known, strict=False)
        if ex.expr is not None:
            e = _rename(ex.expr, known)
            if st.name not in {x.name for x in e.free_symbols}:
                own[st.name] = (e, st.line)
    results = []
    for r in refs:
        keys = {_name_key(r.name)} | {_name_key(a) for a in r.aliases}
        cands = [s for s in statements if _name_key(s.name) in keys]
        if r.name == "result" and not cands:
            cands = [s for s in statements if s.boxed]
        if r.part:
            cands = [s for s in cands if parts.get(s.line, "") == str(r.part).lower()]
        # a boxed or "Result:" line wins, otherwise the last one
        boxed = [s for s in cands if s.boxed]
        ordered = boxed[::-1] + [s for s in cands[::-1] if not s.boxed]
        if not ordered:
            where = f" in part {r.part})" if r.part else ""
            results.append(QuantityResult(r.name, Grade.MISSING,
                                          f"no line '{r.name} = …' found{where}"))
            continue
        # the last statement (boxed or under "Result" first) that carries a formula or value;
        # earlier ones are not searched for a better match, which would favour "correct"
        chosen = None
        for i, st in enumerate(ordered):
            ex = _extract(st, ctx, known)
            if not (ex.formula or ex.value is not None):
                continue
            if ex.formula is None:
                # "v = 2.87 m/s" at the end: take the formula from the last line that has one
                for earlier in ordered[i + 1:]:
                    if earlier.line > st.line:
                        continue
                    if earlier.line == st.line:
                        fx = _extract(earlier, ctx, known)
                        if fx.formula:
                            ex.formula, ex.formula_text, ex.expr = fx.formula, fx.formula_text, fx.expr
                            break
                        continue
                    fx = _extract(earlier, ctx, known)
                    if fx.formula:
                        ex.formula, ex.formula_line = fx.formula, earlier.line
                        ex.formula_text, ex.expr = fx.formula_text, fx.expr
                        break
            chosen = _compare(r, ex, ctx, rel_tol, own)
            break
        if chosen is None:
            chosen = _compare(r, _extract(ordered[0], ctx, known), ctx, rel_tol, own)
        results.append(chosen)

    doc = None
    if steps and _formulas(answer):
        doc = check_document(answer, units=ctx.units or None, assumptions=assumptions)
    return AnswerReport(results, doc)


# --------------------------------------------------------------------------
# task files
# --------------------------------------------------------------------------

def load_task(path: str | Path) -> dict[str, Any]:
    """Read a task file (YAML or JSON) with ``reference`` and optional ``given``."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        task = json.loads(text)
    else:
        try:
            import yaml
        except ImportError:  # pragma: no cover
            raise SystemExit("YAML task files need PyYAML: pip install pyyaml "
                             "(or write the task as JSON)") from None
        task = yaml.safe_load(text) or {}
    if not isinstance(task, dict) or "reference" not in task:
        raise ValueError(f"{p.name}: a task needs a 'reference' section")
    task.setdefault("id", p.stem)
    return task


def grade(task: Mapping[str, Any] | str | Path, answer: str, *, steps: bool = True) -> AnswerReport:
    """Grade an answer against a task (a mapping or a task file).

    A task has ``reference`` (as for :func:`check_answer`) and may have
    ``given``, ``units``, ``assumptions`` and ``rel_tol``. Benchmark tasks
    (``wanted`` + ``reference`` with ``path_a``) work as well.
    """
    if not isinstance(task, Mapping):
        task = load_task(task)
    reference = task["reference"]
    wanted = task.get("wanted")
    if isinstance(reference, Mapping):
        reference = {k: v for k, v in reference.items()
                     if (wanted is None or k in wanted) and isinstance(v, (Mapping, str, int, float))}
        if wanted:
            for k, spec in wanted.items():
                if k in reference and isinstance(spec, Mapping) and isinstance(reference[k], Mapping):
                    merged = dict(reference[k])
                    merged.setdefault("unit", spec.get("unit"))
                    merged.setdefault("symbolic_only", spec.get("symbolic_only"))
                    reference[k] = merged
    units = dict(task.get("units") or {})
    units.update(task.get("auxiliary") or {})
    return check_answer(answer, reference, given=task.get("given"), units=units,
                        assumptions=task.get("assumptions"),
                        rel_tol=float(task.get("rel_tol", DEFAULT_REL_TOL)), steps=steps)

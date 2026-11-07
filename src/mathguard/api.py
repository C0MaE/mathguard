"""JSON interface, designed so a language model can emit checks directly.

A check is a dict with a ``"check"`` field. ``verify`` accepts one check, a
list of checks, or ``{"checks": [...]}`` and always returns a JSON-serialisable
report.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .checks import (
    check_antiderivative,
    check_chain,
    check_definite_integral,
    check_derivative,
    check_equal,
    check_limit,
    check_solutions,
    check_value,
)
from .units import check_dimensions
from .verdict import Report, Status, Verdict


def _req(spec: dict[str, Any], *keys: str) -> list[Any]:
    missing = [k for k in keys if k not in spec]
    if missing:
        raise KeyError(f"missing field(s): {', '.join(missing)}")
    return [spec[k] for k in keys]


def _equal(s):
    _req(s, "lhs", "rhs")
    return check_equal(_latex(s, "lhs"), _latex(s, "rhs"), s.get("assumptions"))


def _chain(s):
    (steps,) = _req(s, "steps")
    if s.get("latex"):
        from .latex import latex_to_expr
        steps = [latex_to_expr(x) for x in steps]
    return check_chain(steps, s.get("assumptions"))


def _derivative(s):
    f, claimed = _req(s, "function", "claimed")
    return check_derivative(f, claimed, s.get("variable", "x"), s.get("assumptions"),
                            order=int(s.get("order", 1)))


def _antiderivative(s):
    f, claimed = _req(s, "integrand", "claimed")
    return check_antiderivative(f, claimed, s.get("variable", "x"), s.get("assumptions"))


def _definite(s):
    f, lo, hi, claimed = _req(s, "integrand", "lower", "upper", "claimed")
    return check_definite_integral(f, s.get("variable", "x"), lo, hi, claimed,
                                   s.get("assumptions"),
                                   rel_tol=float(s.get("rel_tol", 1e-8)))


def _solutions(s):
    eq, claimed = _req(s, "equation", "claimed")
    if isinstance(claimed, (str, int, float)):
        claimed = [claimed]
    return check_solutions(eq, s.get("variable", "x"), claimed, s.get("assumptions"),
                           complete=bool(s.get("complete", True)))


def _value(s):
    e, claimed = _req(s, "expression", "claimed")
    return check_value(e, claimed, rel_tol=float(s.get("rel_tol", 1e-9)),
                       abs_tol=float(s.get("abs_tol", 0.0)))


def _limit(s):
    e, var, point, claimed = _req(s, "expression", "variable", "point", "claimed")
    return check_limit(e, var, point, claimed, s.get("assumptions"),
                       direction=s.get("direction", "+-"))


def _dimensions(s):
    (units,) = _req(s, "units")
    return check_dimensions(units, equation=s.get("equation"), lhs=s.get("lhs"),
                            rhs=s.get("rhs"), expression=s.get("expression"),
                            expected=s.get("expected"))


def _document(s):
    from .document import check_document
    (text,) = _req(s, "text")
    rep = check_document(text, units=s.get("units"), assumptions=s.get("assumptions"),
                         positive=bool(s.get("positive", True)))
    verdicts = []
    for step in rep.steps:
        for v in step.verdicts:
            v.details["latex"] = step.latex
            if step.note:
                v.details["note"] = step.note
            verdicts.append(v)
    if not verdicts:
        verdicts.append(Verdict("document", Status.INCONCLUSIVE,
                                "no checkable formula chain found"))
    return Report(verdicts)


def _latex(s, key):
    from .latex import latex_to_expr
    return latex_to_expr(s[key]) if s.get("latex") else s[key]


CHECKS: dict[str, Callable[[dict[str, Any]], Verdict | Report]] = {
    "equal": _equal,
    "chain": _chain,
    "derivative": _derivative,
    "antiderivative": _antiderivative,
    "definite_integral": _definite,
    "solutions": _solutions,
    "value": _value,
    "limit": _limit,
    "dimensions": _dimensions,
    "document": _document,
}


def _run_one(spec: Any) -> list[Verdict]:
    if not isinstance(spec, dict):
        return [Verdict("?", Status.ERROR, "each check must be a JSON object")]
    kind = spec.get("check")
    fn = CHECKS.get(kind)  # type: ignore[arg-type]
    if fn is None:
        return [Verdict(str(kind), Status.ERROR,
                        f"unknown check '{kind}'; available: {', '.join(CHECKS)}")]
    try:
        out = fn(spec)
    except (KeyError, TypeError, ValueError) as exc:
        return [Verdict(str(kind), Status.ERROR, str(exc).strip("'\""))]
    verdicts = out.verdicts if isinstance(out, Report) else [out]
    if spec.get("id") is not None:
        for v in verdicts:
            v.details["id"] = spec["id"]
    return verdicts


def verify(spec: Any) -> Report:
    """Run one check, a list of checks, or ``{"checks": [...]}``."""
    if isinstance(spec, str):
        spec = json.loads(spec)
    if isinstance(spec, dict) and "checks" in spec:
        spec = spec["checks"]
    specs = spec if isinstance(spec, list) else [spec]
    verdicts: list[Verdict] = []
    for s in specs:
        verdicts.extend(_run_one(s))
    return Report(verdicts)


def verify_json(text: str) -> str:
    """String in, string out. Convenient for tool-calling frameworks."""
    try:
        report = verify(text)
    except json.JSONDecodeError as exc:
        report = Report([Verdict("input", Status.ERROR, f"invalid JSON: {exc}")])
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)


#: Instructions you can put into an LLM system prompt so the model knows how
#: to call mathguard. Also served by the MCP server and ``mathguard prompt``.
LLM_INSTRUCTIONS = """\
You have access to `mathguard`, a verifier for mathematical claims. Whenever you
state a non-trivial calculation, send the relevant claims as JSON checks and only
report results whose status is "verified" or "likely". If a check is "refuted",
use the counterexample to find and fix the mistake, then check again.

Expression syntax: ^ or ** for powers, implicit multiplication allowed (2x, m c^2).
Multi-letter names are single variables (v0, dt, lambda), so write a product of
letters with a space or * ("2 a b", not "2ab").
functions sin cos tan exp log/ln sqrt Abs ..., constants pi, e (Euler), oo.
`E` and `I` are ordinary variables. Variables are real unless stated otherwise;
pass "assumptions": {"x": "positive"} where the derivation relies on it.

Checks (one object or a list):
  {"check": "equal", "lhs": "...", "rhs": "..."}
  {"check": "chain", "steps": ["expr0", "expr1", "..."]}          # each step = next
  {"check": "derivative", "function": "...", "claimed": "...", "variable": "x"}
  {"check": "antiderivative", "integrand": "...", "claimed": "...", "variable": "x"}
  {"check": "definite_integral", "integrand": "...", "variable": "x",
   "lower": "0", "upper": "oo", "claimed": "..."}
  {"check": "solutions", "equation": "lhs = rhs", "variable": "x", "claimed": ["..."]}
  {"check": "value", "expression": "...", "claimed": 1.234, "rel_tol": 1e-6}
  {"check": "limit", "expression": "...", "variable": "c", "point": "oo", "claimed": "..."}
  {"check": "dimensions", "equation": "E = m c^2",
   "units": {"E": "J", "m": "kg", "c": "m/s"}}

  {"check": "document", "text": "<your whole answer in Markdown with $...$ LaTeX>",
   "units": {"v0": "m/s", "g": "m/s^2"}}   # checks every formula chain in the text
"equal" and "chain" also accept LaTeX with "latex": true (\\frac, \\sqrt, v_0, ...).
In LaTeX, adjacent letters are products (mv^2 = m*v^2) and v_0 is the variable v0.

Statuses: verified (symbolic proof by CAS), likely (numerical tests only),
refuted (counterexample found), inconclusive, error (bad input).
"""

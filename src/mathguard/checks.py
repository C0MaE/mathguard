"""Core checks: equalities, derivation chains, calculus and numbers.

Every check tries the strongest method first (symbolic simplification) and
falls back to randomised numerical testing. A numerical mismatch is a real
counterexample, so ``REFUTED`` is always backed by concrete values; a
numerical match is only reported as ``LIKELY``.
"""

from __future__ import annotations

import cmath
import math
import random
from typing import Any, Mapping, Sequence

import sympy as sp

from ._timeout import run_with_limit
from .parsing import ParseError, parse, parse_equation, parse_symbol, unify_symbols
from .verdict import Report, Status, Verdict

Assumptions = Mapping[str, object] | None
ExprLike = str | int | float | sp.Basic

#: Seconds allowed for one symbolic simplification attempt.
SIMPLIFY_TIMEOUT = 5.0
#: Number of random points used in numerical testing.
DEFAULT_SAMPLES = 24
#: Digits of working precision for numerical evaluation.
PRECISION = 30


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _fmt(value: Any, digits: int = 10) -> str:
    try:
        z = complex(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(z.imag) < 1e-15 * max(1.0, abs(z.real)):
        return f"{z.real:.{digits}g}"
    return f"{z.real:.{digits}g} {'+' if z.imag >= 0 else '-'} {abs(z.imag):.{digits}g}i"


def _sample_value(sym: sp.Symbol, rng: random.Random) -> sp.Expr:
    a = sym.assumptions0
    if a.get("integer"):
        k = rng.randint(1, 7)
        if a.get("positive") or a.get("nonnegative"):
            return sp.Integer(k)
        if a.get("negative") or a.get("nonpositive"):
            return sp.Integer(-k)
        return sp.Integer(k if rng.random() < 0.5 else -k)
    # log-uniform magnitude between 0.05 and 20 so both small and large values occur
    mag = math.exp(rng.uniform(math.log(0.05), math.log(20.0)))
    if a.get("positive") or a.get("nonnegative"):
        x = mag
    elif a.get("negative") or a.get("nonpositive"):
        x = -mag
    else:
        x = mag if rng.random() < 0.5 else -mag
    if a.get("real") is False or (a.get("real") is None and not a.get("positive")):
        # complex variable: add an imaginary part
        x = complex(x, rng.uniform(-3, 3))
        return sp.Float(x.real, PRECISION) + sp.I * sp.Float(x.imag, PRECISION)
    return sp.Float(x, PRECISION)


def _evaluate(expr: sp.Expr, values: Mapping[sp.Symbol, sp.Expr]) -> complex | None:
    try:
        v = expr.evalf(PRECISION, subs=dict(values))
        z = complex(v)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if not (cmath.isfinite(z)):
        return None
    return z


def _close(a: complex, b: complex, rel_tol: float = 1e-9, abs_tol: float = 1e-12) -> bool:
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))


def _numeric_compare(
    lhs: sp.Expr,
    rhs: sp.Expr,
    samples: int = DEFAULT_SAMPLES,
    seed: int = 12345,
) -> tuple[str, dict[str, Any] | None, int]:
    """Return ("match" | "mismatch" | "undecided", counterexample, n_valid)."""
    symbols = sorted(lhs.free_symbols | rhs.free_symbols, key=lambda s: s.name)
    rng = random.Random(seed)
    valid = 0
    attempts = 0
    while valid < samples and attempts < samples * 6:
        attempts += 1
        point = {s: _sample_value(s, rng) for s in symbols}
        a = _evaluate(lhs, point)
        b = _evaluate(rhs, point)
        if a is None or b is None:
            continue
        valid += 1
        if not _close(a, b):
            ce = {s.name: _fmt(v) for s, v in point.items()}
            ce["lhs"] = _fmt(a)
            ce["rhs"] = _fmt(b)
            return "mismatch", ce, valid
        if not symbols:
            break
    if valid == 0:
        return "undecided", None, 0
    if symbols and valid < 5:
        return "undecided", None, valid
    return "match", None, valid


def _symbolic_zero(diff: sp.Expr, timeout: float = SIMPLIFY_TIMEOUT) -> bool | None:
    """True if ``diff`` simplifies to 0, False if to a non-zero constant, else None."""
    if diff == 0:
        return True
    cheap = [sp.expand, sp.cancel, lambda e: sp.trigsimp(sp.expand(e))]
    for f in cheap:
        r = run_with_limit(lambda f=f: f(diff), timeout)
        if r is not None and r == 0:
            return True
    r = run_with_limit(lambda: sp.simplify(diff), timeout)
    if r is None:
        return None
    if r == 0:
        return True
    if r.is_number and r.is_zero is False:
        return False
    return None


def _parse_pair(lhs: ExprLike, rhs: ExprLike, assumptions: Assumptions) -> tuple[sp.Expr, sp.Expr]:
    a = parse(lhs, assumptions)
    b = parse(rhs, assumptions)
    a, b = unify_symbols(a, b)
    return a, b  # type: ignore[return-value]


def _show(raw: ExprLike, parsed: sp.Basic) -> str:
    """Prefer the text as written, because SymPy auto-simplifies on parsing."""
    return raw.strip() if isinstance(raw, str) else sp.sstr(parsed)


def _error(check: str, exc: Exception) -> Verdict:
    return Verdict(check, Status.ERROR, str(exc))


def _hint_for_domain(lhs: sp.Expr, rhs: sp.Expr) -> str:
    """Suggest assumptions when the identity only fails because of signs/branches."""
    syms = [s.name for s in (lhs.free_symbols | rhs.free_symbols) if not s.is_positive]
    if not syms:
        return ""

    def risky(e: sp.Basic) -> bool:
        if e.has(sp.log, sp.Abs, sp.sign):
            return True
        return any(not p.exp.is_integer for p in e.atoms(sp.Pow))

    if risky(lhs) or risky(rhs):
        return (" (hint: if the variables are meant to be positive, pass "
                f"assumptions such as {{\"{sorted(syms)[0]}\": \"positive\"}})")
    return ""


def _hint_for_merged_names(*exprs: sp.Expr) -> str:
    """Warn when e.g. '2ab' was read as 2*(variable ab) next to variables a and b.

    Multi-letter names are kept intact on purpose (v0, dt, lambda), so a
    product of single letters must be written with a space or '*'.
    """
    names = {s.name for e in exprs for s in e.free_symbols}
    singles = {n for n in names if len(n) == 1}
    merged = sorted(n for n in names
                    if len(n) > 1 and n.isalpha() and all(ch in singles for ch in n))
    if not merged:
        return ""
    return (f" (note: {', '.join(repr(n) for n in merged)} was read as a single variable; "
            f"write '{' '.join(merged[0])}' or '{'*'.join(merged[0])}' for a product)")


# --------------------------------------------------------------------------
# public checks
# --------------------------------------------------------------------------

def check_equal(
    lhs: ExprLike,
    rhs: ExprLike,
    assumptions: Assumptions = None,
    *,
    samples: int = DEFAULT_SAMPLES,
    label: str = "equal",
) -> Verdict:
    """Check that two expressions are identical for all admissible variable values.

    >>> check_equal("sin(x)^2 + cos(x)^2", "1").status.value
    'verified'
    """
    try:
        a, b = _parse_pair(lhs, rhs, assumptions)
    except ParseError as exc:
        return _error(label, exc)

    shown = f"{_show(lhs, a)} = {_show(rhs, b)}"
    diff = a - b

    sym = _symbolic_zero(diff)
    if sym is True:
        return Verdict(label, Status.VERIFIED, shown, method="symbolic simplification")

    outcome, ce, n = _numeric_compare(a, b, samples=samples)
    hints = _hint_for_merged_names(a, b) or _hint_for_domain(a, b)
    if outcome == "mismatch":
        return Verdict(label, Status.REFUTED, f"{shown} is false" + hints,
                       method="numerical counterexample", counterexample=ce)
    if sym is False:
        return Verdict(label, Status.REFUTED, f"{shown} is false (difference simplifies "
                       f"to {sp.sstr(sp.simplify(diff))})" + hints,
                       method="symbolic simplification")
    if outcome == "match":
        return Verdict(label, Status.LIKELY, f"{shown} (no symbolic proof, {n} random "
                       "points agree)", method="numerical testing", details={"samples": n})
    return Verdict(label, Status.INCONCLUSIVE,
                   f"{shown}: could not simplify and could not evaluate numerically",
                   method="none")


def check_chain(
    steps: Sequence[ExprLike],
    assumptions: Assumptions = None,
    *,
    samples: int = DEFAULT_SAMPLES,
) -> Report:
    """Check a derivation ``steps[0] = steps[1] = ... = steps[n]`` step by step.

    The report pinpoints the first step where an error was introduced.
    """
    if len(steps) < 2:
        return Report([Verdict("chain", Status.ERROR, "a chain needs at least two steps")])
    verdicts = []
    for i in range(len(steps) - 1):
        v = check_equal(steps[i], steps[i + 1], assumptions, samples=samples,
                        label=f"step {i + 1} → {i + 2}")
        verdicts.append(v)
    return Report(verdicts)


def check_derivative(
    function: ExprLike,
    claimed: ExprLike,
    variable: str = "x",
    assumptions: Assumptions = None,
    *,
    order: int = 1,
) -> Verdict:
    """Check that ``d^order/dvariable^order function == claimed``."""
    label = "derivative"
    try:
        f, g = _parse_pair(function, claimed, assumptions)
        x = parse_symbol(variable, assumptions)
        (x,) = [s for s in f.free_symbols | g.free_symbols if s.name == x.name] or [x]
    except ParseError as exc:
        return _error(label, exc)
    true = sp.diff(f, x, order)
    v = check_equal(true, g, assumptions, label=label)
    v.details["computed"] = sp.sstr(true)
    if not v.ok and v.status != Status.ERROR:
        v.message = f"d/d{x.name} of {sp.sstr(f)} is {sp.sstr(sp.simplify(true))}, not {sp.sstr(g)}"
    else:
        v.message = f"d/d{x.name} [{sp.sstr(f)}] = {sp.sstr(g)}"
    return v


def check_antiderivative(
    integrand: ExprLike,
    claimed: ExprLike,
    variable: str = "x",
    assumptions: Assumptions = None,
) -> Verdict:
    """Check an indefinite integral by differentiating the claimed result.

    Constants of integration are ignored automatically.
    """
    label = "antiderivative"
    try:
        f, F = _parse_pair(integrand, claimed, assumptions)
        x = parse_symbol(variable, assumptions)
        (x,) = [s for s in f.free_symbols | F.free_symbols if s.name == x.name] or [x]
    except ParseError as exc:
        return _error(label, exc)
    dF = sp.diff(F, x)
    v = check_equal(dF, f, assumptions, label=label)
    v.details["derivative_of_claim"] = sp.sstr(dF)
    if v.ok:
        v.message = f"∫ {sp.sstr(f)} d{x.name} = {sp.sstr(F)} + C"
    elif v.status == Status.REFUTED:
        v.message = (f"∫ {sp.sstr(f)} d{x.name} ≠ {sp.sstr(F)}: differentiating the claim "
                     f"gives {sp.sstr(sp.simplify(dF))}")
    return v


def check_definite_integral(
    integrand: ExprLike,
    variable: str,
    lower: ExprLike,
    upper: ExprLike,
    claimed: ExprLike,
    assumptions: Assumptions = None,
    *,
    rel_tol: float = 1e-8,
) -> Verdict:
    """Check ``∫_lower^upper integrand d(variable) == claimed``."""
    label = "definite_integral"
    try:
        f = parse(integrand, assumptions)
        x = parse_symbol(variable, assumptions)
        (x,) = [s for s in f.free_symbols if s.name == x.name] or [x]
        a, b, c = parse(lower, assumptions), parse(upper, assumptions), parse(claimed, assumptions)
        f, a, b, c = unify_symbols(f, a, b, c)
    except ParseError as exc:
        return _error(label, exc)

    integral = sp.Integral(f, (x, a, b))
    others = (f.free_symbols - {x}) | a.free_symbols | b.free_symbols | c.free_symbols
    if others:
        result = run_with_limit(lambda: integral.doit(), SIMPLIFY_TIMEOUT * 2)
        if result is None or result.has(sp.Integral):
            return Verdict(label, Status.INCONCLUSIVE,
                           "integral has free parameters and could not be done symbolically")
        v = check_equal(result, c, assumptions, label=label)
        v.details["computed"] = sp.sstr(result)
        return v

    value = run_with_limit(lambda: integral.evalf(PRECISION), SIMPLIFY_TIMEOUT * 2)
    target = _evaluate(c, {})
    if value is None or target is None:
        return Verdict(label, Status.INCONCLUSIVE, "could not evaluate the integral numerically")
    try:
        computed = complex(value)
    except TypeError:
        return Verdict(label, Status.INCONCLUSIVE, f"integral evaluated to {value}")
    shown = f"∫_{sp.sstr(a)}^{sp.sstr(b)} {sp.sstr(f)} d{x.name}"
    if _close(computed, target, rel_tol=rel_tol):
        return Verdict(label, Status.VERIFIED, f"{shown} = {_fmt(computed, 15)}",
                       method=f"numerical quadrature ({PRECISION} digits)",
                       details={"computed": _fmt(computed, 15)})
    return Verdict(label, Status.REFUTED,
                   f"{shown} = {_fmt(computed, 15)}, claimed {_fmt(target, 15)}",
                   method=f"numerical quadrature ({PRECISION} digits)",
                   details={"computed": _fmt(computed, 15)})


def _solution_domain(x: sp.Symbol) -> sp.Set:
    """Domain for ``solveset`` that respects the variable's sign assumptions."""
    if x.is_positive:
        return sp.Interval.open(0, sp.oo)
    if x.is_nonnegative:
        return sp.Interval(0, sp.oo)
    if x.is_negative:
        return sp.Interval.open(-sp.oo, 0)
    if x.is_nonpositive:
        return sp.Interval(-sp.oo, 0)
    return sp.S.Reals if x.is_real else sp.S.Complexes


def check_solutions(
    equation: str,
    variable: str,
    claimed: Sequence[ExprLike],
    assumptions: Assumptions = None,
    *,
    complete: bool = True,
) -> Report:
    """Check that each claimed value solves ``equation`` and, optionally, that
    no real solution is missing."""
    try:
        lhs, rhs = parse_equation(equation, assumptions)
        x = parse_symbol(variable, assumptions)
        lhs, rhs = unify_symbols(lhs, rhs)
        (x,) = [s for s in lhs.free_symbols | rhs.free_symbols if s.name == x.name] or [x]
        sols = [parse(s, assumptions) for s in claimed]
    except ParseError as exc:
        return Report([_error("solutions", exc)])

    verdicts: list[Verdict] = []
    for raw, s in zip(claimed, sols):
        v = check_equal(lhs.subs(x, s), rhs.subs(x, s), assumptions,
                        label=f"{x.name} = {raw}")
        if v.ok:
            v.message = f"{x.name} = {sp.sstr(s)} satisfies {sp.sstr(lhs)} = {sp.sstr(rhs)}"
        elif v.status == Status.REFUTED:
            v.message = f"{x.name} = {sp.sstr(s)} does not satisfy {sp.sstr(lhs)} = {sp.sstr(rhs)}"
        verdicts.append(v)

    if complete:
        domain = _solution_domain(x)
        found = run_with_limit(lambda: sp.solveset(sp.Eq(lhs, rhs), x, domain=domain),
                               SIMPLIFY_TIMEOUT * 2)
        if isinstance(found, sp.FiniteSet):
            missing = []
            for r in found:
                if not any(_symbolic_zero(sp.nsimplify(r) - c) or
                           _numeric_compare(r, c, samples=6)[0] == "match" for c in sols):
                    missing.append(sp.sstr(r))
            if missing:
                verdicts.append(Verdict(
                    "completeness", Status.REFUTED,
                    f"missing solution(s): {', '.join(missing)}",
                    method="sympy.solveset",
                    details={"all_solutions": [sp.sstr(r) for r in found]}))
            else:
                verdicts.append(Verdict("completeness", Status.VERIFIED,
                                        f"all {len(found)} solution(s) found",
                                        method="sympy.solveset"))
        else:
            verdicts.append(Verdict("completeness", Status.INCONCLUSIVE,
                                    "could not enumerate all solutions to compare against"))
    return Report(verdicts)


def check_value(
    expression: ExprLike,
    claimed: ExprLike,
    *,
    rel_tol: float = 1e-9,
    abs_tol: float = 0.0,
) -> Verdict:
    """Check a numerical result, e.g. ``check_value("sqrt(2) * pi", 4.4429, rel_tol=1e-4)``."""
    label = "value"
    try:
        e, c = _parse_pair(expression, claimed, None)
    except ParseError as exc:
        return _error(label, exc)
    if e.free_symbols:
        names = ", ".join(sorted(s.name for s in e.free_symbols))
        return Verdict(label, Status.ERROR, f"expression still contains variables: {names}")
    a, b = _evaluate(e, {}), _evaluate(c, {})
    if a is None or b is None:
        return Verdict(label, Status.INCONCLUSIVE, "could not evaluate numerically")
    ok = abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))
    rel = abs(a - b) / abs(a) if a != 0 else abs(a - b)
    msg = f"{_show(expression, e)} = {_fmt(a, 15)}, claimed {_fmt(b, 15)} (rel. error {rel:.2e})"
    return Verdict(label, Status.VERIFIED if ok else Status.REFUTED, msg,
                   method=f"evaluation with {PRECISION} digits",
                   details={"computed": _fmt(a, 15), "relative_error": rel})


def check_limit(
    expression: ExprLike,
    variable: str,
    point: ExprLike,
    claimed: ExprLike,
    assumptions: Assumptions = None,
    *,
    direction: str = "+-",
) -> Verdict:
    """Check ``lim_{variable → point} expression == claimed``.

    Useful for sanity checks such as "the relativistic kinetic energy reduces
    to 1/2 m v^2 for c → oo". Use ``direction="+"`` or ``"-"`` for one-sided
    limits.
    """
    label = "limit"
    try:
        e = parse(expression, assumptions)
        x = parse_symbol(variable, assumptions)
        p, c = parse(point, assumptions), parse(claimed, assumptions)
        e, p, c = unify_symbols(e, p, c)
        (x,) = [s for s in e.free_symbols if s.name == x.name] or [x]
    except ParseError as exc:
        return _error(label, exc)
    if p in (sp.oo, -sp.oo):
        direction = "-" if p == sp.oo else "+"
    result = run_with_limit(lambda: sp.limit(e, x, p, dir=direction), SIMPLIFY_TIMEOUT * 2)
    if result is None or isinstance(result, sp.Limit):
        return Verdict(label, Status.INCONCLUSIVE, "SymPy could not compute the limit")
    v = check_equal(result, c, assumptions, label=label)
    v.details["computed"] = sp.sstr(result)
    arrow = f"lim_{{{x.name}→{sp.sstr(p)}}} {sp.sstr(e)}"
    v.message = (f"{arrow} = {sp.sstr(c)}" if v.ok
                 else f"{arrow} = {sp.sstr(result)}, not {sp.sstr(c)}")
    return v

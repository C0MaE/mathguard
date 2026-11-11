"""Dimensional analysis with Pint.

Each variable is assigned a unit (``{"m": "kg", "v": "m/s"}``). The
expression tree is then walked and every operation is checked:

* terms of a sum must have the same dimension,
* arguments of ``exp``, ``log``, ``sin`` … must be dimensionless,
* exponents must be dimensionless numbers.

Physical constants can be given by their Pint names, e.g.
``{"c": "speed_of_light", "G": "gravitational_constant", "h": "planck_constant",
"k": "boltzmann_constant"}``.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import sympy as sp

from .parsing import ParseError, parse, parse_equation
from .verdict import Status, Verdict

_TRANSCENDENTAL = (
    sp.exp, sp.log, sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc,
    sp.asin, sp.acos, sp.atan, sp.sinh, sp.cosh, sp.tanh,
    sp.asinh, sp.acosh, sp.atanh, sp.erf, sp.gamma, sp.factorial,
)


class DimensionError(ValueError):
    pass


@lru_cache(maxsize=1)
def _ureg():
    try:
        import pint
    except ImportError as exc:  # pragma: no cover - pint is a hard dependency
        raise ImportError("dimension checks need 'pint' (pip install pint)") from exc
    return pint.UnitRegistry()


def _q(unit: str):
    ureg = _ureg()
    unit = unit.strip()
    if unit in ("", "1", "dimensionless", "-"):
        return ureg.Quantity(1.0, "dimensionless")
    try:
        return ureg.Quantity(1.0, unit)
    except Exception as exc:  # noqa: BLE001
        raise DimensionError(f"unknown unit '{unit}': {exc}") from None


def _dim(q) -> str:
    d = q.dimensionality
    return "dimensionless" if not d else str(d)


def _walk(expr: sp.Basic, env: Mapping[str, Any]):
    ureg = _ureg()
    if isinstance(expr, sp.Symbol):
        if expr.name not in env:
            raise DimensionError(f"no unit given for variable '{expr.name}' "
                                 "(use \"dimensionless\" if it has none)")
        return env[expr.name]
    if expr.is_number:
        return ureg.Quantity(1.0, "dimensionless")
    if isinstance(expr, sp.Add):
        terms = [(t, _walk(t, env)) for t in expr.args]
        first_t, first_q = terms[0]
        for t, q in terms[1:]:
            if q.dimensionality != first_q.dimensionality:
                raise DimensionError(
                    f"cannot add '{sp.sstr(first_t)}' [{_dim(first_q)}] and "
                    f"'{sp.sstr(t)}' [{_dim(q)}]")
        return first_q
    if isinstance(expr, sp.Mul):
        out = ureg.Quantity(1.0, "dimensionless")
        for a in expr.args:
            out = out * _walk(a, env)
        return out
    if isinstance(expr, sp.Pow):
        base, exponent = expr.args
        qb = _walk(base, env)
        qe = _walk(exponent, env)
        if qe.dimensionality:
            raise DimensionError(
                f"exponent '{sp.sstr(exponent)}' has dimension [{_dim(qe)}]")
        if not qb.dimensionality:
            return ureg.Quantity(1.0, "dimensionless")
        if not exponent.is_number:
            raise DimensionError(
                f"'{sp.sstr(base)}' [{_dim(qb)}] is raised to the symbolic power "
                f"'{sp.sstr(exponent)}'; the result has no fixed dimension")
        return qb ** float(exponent)
    if isinstance(expr, (sp.Abs, sp.sign, sp.floor, sp.ceiling)):
        return _walk(expr.args[0], env)
    if isinstance(expr, (sp.Min, sp.Max)):
        qs = [_walk(a, env) for a in expr.args]
        if any(q.dimensionality != qs[0].dimensionality for q in qs):
            raise DimensionError(f"arguments of '{sp.sstr(expr)}' have different dimensions")
        return qs[0]
    if isinstance(expr, _TRANSCENDENTAL) or isinstance(expr, sp.Function):
        for a in expr.args:
            q = _walk(a, env)
            if q.dimensionality:
                name = type(expr).__name__
                raise DimensionError(
                    f"argument of {name}() must be dimensionless, but "
                    f"'{sp.sstr(a)}' has dimension [{_dim(q)}]")
        return ureg.Quantity(1.0, "dimensionless")
    raise DimensionError(f"don't know how to check '{sp.sstr(expr)}'")


def dimension_of(expression: str | sp.Basic, units: Mapping[str, str]) -> str:
    """Return the dimension of ``expression`` as a string, or raise DimensionError."""
    expr = parse(expression, {k: "positive" for k in units})
    env = {name: _q(u) for name, u in units.items()}
    return _dim(_walk(expr, env))


def check_dimensions(
    units: Mapping[str, str],
    *,
    equation: str | None = None,
    lhs: str | None = None,
    rhs: str | None = None,
    expression: str | None = None,
    expected: str | None = None,
) -> Verdict:
    """Check that an equation (or expression) is dimensionally consistent.

    Give either ``equation="E = m c^2"`` or ``lhs``/``rhs``, or a single
    ``expression`` together with the ``expected`` unit.

    >>> check_dimensions({"E": "J", "m": "kg", "c": "m/s"}, equation="E = m c^2").ok
    True
    """
    label = "dimensions"
    try:
        env = {name: _q(u) for name, u in units.items()}
        assume = {k: "positive" for k in units}
        if equation is not None:
            a, b = parse_equation(equation, assume)
            shown = equation
        elif lhs is not None and rhs is not None:
            a, b = parse(lhs, assume), parse(rhs, assume)
            shown = f"{lhs} = {rhs}"
        elif expression is not None and expected is not None:
            a = parse(expression, assume)
            qa = _walk(a, env)
            qe = _q(expected)
            if qa.dimensionality == qe.dimensionality:
                return Verdict(label, Status.VERIFIED,
                               f"'{expression}' has dimension [{_dim(qa)}] as expected",
                               method="dimensional analysis (pint)")
            return Verdict(label, Status.REFUTED,
                           f"'{expression}' has dimension [{_dim(qa)}], expected "
                           f"[{_dim(qe)}] ({expected})", method="dimensional analysis (pint)")
        else:
            raise DimensionError("give 'equation', or 'lhs' and 'rhs', "
                                 "or 'expression' and 'expected'")
        qa, qb = _walk(a, env), _walk(b, env)
    except DimensionError as exc:
        return Verdict(label, Status.REFUTED if "no unit given" not in str(exc)
                       and "unknown unit" not in str(exc) and "give '" not in str(exc)
                       else Status.ERROR, str(exc), method="dimensional analysis (pint)")
    except ParseError as exc:
        return Verdict(label, Status.ERROR, str(exc))

    if qa.dimensionality == qb.dimensionality:
        return Verdict(label, Status.VERIFIED,
                       f"{shown}: both sides have dimension [{_dim(qa)}]",
                       method="dimensional analysis (pint)")
    return Verdict(label, Status.REFUTED,
                   f"{shown}: left side is [{_dim(qa)}], right side is [{_dim(qb)}]",
                   method="dimensional analysis (pint)")

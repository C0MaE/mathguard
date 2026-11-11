"""Safe parsing of expression strings coming from people or language models.

SymPy's own ``sympify``/``parse_expr`` uses ``eval`` internally, so feeding it
untrusted text is a code-execution risk. This module only lets a small
character set through, rejects anything that looks like Python attribute
access, and builds the namespace explicitly so every identifier becomes either
a whitelisted maths function or a plain symbol.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)

MAX_LENGTH = 2000

_ALLOWED = re.compile(r"^[A-Za-z0-9_+\-*/^().,\s]*$")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FORBIDDEN_WORDS = {"import", "exec", "eval", "open", "globals", "locals", "compile"}
# Python keywords cannot be used as names by the parser, but some are common
# in physics (``lambda`` for wavelength). They are renamed internally.
_KEYWORDS = {"lambda", "in", "is", "as", "if", "or", "and", "not", "for", "del",
             "def", "try", "with", "from", "class", "pass", "else", "elif",
             "while", "yield", "break", "raise", "global", "return", "assert",
             "except", "finally", "continue", "nonlocal", "async", "await",
             "True", "False", "None"}

_TRANSFORMS = standard_transformations + (implicit_multiplication, convert_xor)

#: Names that are treated as functions when they are directly followed by "(".
FUNCTIONS: dict[str, object] = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot,
    "sec": sp.sec, "csc": sp.csc,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan, "atan2": sp.atan2,
    "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "asinh": sp.asinh, "acosh": sp.acosh, "atanh": sp.atanh,
    "exp": sp.exp, "log": sp.log, "ln": sp.log, "sqrt": sp.sqrt,
    "cbrt": sp.cbrt, "Abs": sp.Abs, "abs": sp.Abs, "sign": sp.sign,
    "floor": sp.floor, "ceiling": sp.ceiling, "factorial": sp.factorial,
    "gamma": sp.gamma, "erf": sp.erf, "min": sp.Min, "max": sp.Max,
}

#: Names that are treated as constants when they appear on their own.
#: ``E`` is intentionally *not* Euler's number (physicists use it for energy);
#: write ``e`` or ``exp(1)`` instead. ``I`` is not the imaginary unit for the
#: same reason (current, moment of inertia).
CONSTANTS: dict[str, object] = {"pi": sp.pi, "e": sp.E, "oo": sp.oo, "inf": sp.oo}

_ASSUMPTION_KEYS = {
    "real", "positive", "negative", "nonnegative", "nonpositive",
    "integer", "nonzero", "complex",
}


class ParseError(ValueError):
    """Raised when an expression is rejected or cannot be parsed."""


def make_symbol(name: str, assumptions: Mapping[str, object] | None = None) -> sp.Symbol:
    flags: dict[str, bool] = {}
    spec = (assumptions or {}).get(name)
    if spec:
        tags = [spec] if isinstance(spec, str) else list(spec)  # type: ignore[arg-type]
        for tag in tags:
            tag = str(tag).strip().lower()
            if tag not in _ASSUMPTION_KEYS:
                raise ParseError(
                    f"unknown assumption '{tag}' for '{name}'; "
                    f"use one of {sorted(_ASSUMPTION_KEYS)}"
                )
            if tag != "complex":
                flags[tag] = True
    elif not (assumptions or {}).get("__complex__"):
        # Default: variables are real. This matches how maths and physics
        # derivations are usually written and avoids branch-cut surprises.
        flags["real"] = True
    return sp.Symbol(name, **flags)


def _validate(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()
    if not text:
        raise ParseError("empty expression")
    if len(text) > MAX_LENGTH:
        raise ParseError(f"expression longer than {MAX_LENGTH} characters")
    if "__" in text:
        raise ParseError("double underscores are not allowed")
    if not _ALLOWED.match(text):
        bad = sorted({c for c in text if not _ALLOWED.match(c)})
        raise ParseError(f"illegal character(s): {' '.join(bad)}")
    if re.search(r"[A-Za-z_)\]]\s*\.\s*[A-Za-z_]", text):
        raise ParseError("attribute access ('.') is not allowed")
    for word in _IDENT.findall(text):
        if word in _FORBIDDEN_WORDS:
            raise ParseError(f"'{word}' is not allowed")
    return text


def parse(
    text: str | int | float | sp.Basic,
    assumptions: Mapping[str, object] | None = None,
) -> sp.Expr:
    """Parse one expression into a SymPy object.

    ``assumptions`` maps variable names to tags such as ``"positive"`` or a
    list of tags. Variables without an entry are assumed to be real.
    """
    if isinstance(text, sp.Basic):
        return text  # type: ignore[return-value]
    if isinstance(text, (int, float)):
        return sp.nsimplify(text) if isinstance(text, float) else sp.Integer(text)

    text = _validate(text)

    local: dict[str, object] = {}
    for match in _IDENT.finditer(text):
        name = match.group(0)
        key = f"kw_{name}_" if name in _KEYWORDS else name
        if key in local:
            continue
        rest = text[match.end():].lstrip()
        is_call = rest.startswith("(")
        if is_call and name in FUNCTIONS:
            local[key] = FUNCTIONS[name]
        elif name in CONSTANTS and not (assumptions and name in assumptions):
            local[key] = CONSTANTS[name]
        else:
            local[key] = make_symbol(name, assumptions)
    text = _IDENT.sub(lambda m: f"kw_{m.group(0)}_" if m.group(0) in _KEYWORDS else m.group(0), text)

    global_ns: dict[str, object] = {
        "Integer": sp.Integer,
        "Float": sp.Float,
        "Rational": sp.Rational,
        "Symbol": sp.Symbol,
        "__builtins__": {},
    }
    try:
        expr = parse_expr(text, local_dict=local, global_dict=global_ns,
                          transformations=_TRANSFORMS, evaluate=True)
    except Exception as exc:  # noqa: BLE001 - anything here is a bad input
        raise ParseError(f"could not parse '{text}': {exc}") from None
    if not isinstance(expr, sp.Basic):
        raise ParseError(f"'{text}' is not a mathematical expression")
    return expr  # type: ignore[return-value]


def parse_equation(
    text: str,
    assumptions: Mapping[str, object] | None = None,
) -> tuple[sp.Expr, sp.Expr]:
    """Parse ``"lhs = rhs"`` (or ``==``) into a pair of expressions.

    A string without ``=`` is read as ``expr = 0``.
    """
    if not isinstance(text, str):
        raise ParseError("an equation must be given as a string")
    parts = re.split(r"==|=", text)
    if len(parts) == 1:
        return parse(parts[0], assumptions), sp.Integer(0)
    if len(parts) != 2:
        raise ParseError(f"'{text}' must contain exactly one '='")
    return parse(parts[0], assumptions), parse(parts[1], assumptions)


def parse_symbol(name: str, assumptions: Mapping[str, object] | None = None) -> sp.Symbol:
    name = _validate(name)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ParseError(f"'{name}' is not a valid variable name")
    return make_symbol(name, assumptions)


def unify_symbols(*exprs: sp.Basic) -> list[sp.Basic]:
    """Make sure symbols with the same name are the same object.

    Two expressions parsed separately can produce ``Symbol('x', real=True)``
    and ``Symbol('x', positive=True)`` which SymPy treats as different
    variables. We map every name to one representative (the one with the most
    assumptions) so comparisons are meaningful.
    """
    by_name: dict[str, sp.Symbol] = {}
    for e in exprs:
        for s in e.free_symbols:
            assert isinstance(s, sp.Symbol)
            current = by_name.get(s.name)
            if current is None or len(s.assumptions0) > len(current.assumptions0):
                by_name[s.name] = s
    out = []
    for e in exprs:
        mapping = {s: by_name[s.name] for s in e.free_symbols if by_name[s.name] is not s}
        out.append(e.xreplace(mapping) if mapping else e)
    return out

import pytest
import sympy as sp

import mathguard as mg
from mathguard.latex import latex_to_expr, parse_latex


def _eq(latex, plain):
    a, b = parse_latex(latex), mg.parse(plain)
    return sp.simplify(a - b) == 0


@pytest.mark.parametrize("latex, plain", [
    (r"\frac{1}{2} m v_0^2", "1/2 m v0^2"),
    (r"mv^2", "m v^2"),                                   # adjacent letters multiply
    (r"\tfrac12 g t^2", "g t^2 / 2"),
    (r"\sqrt{2gh}", "sqrt(2 g h)"),
    (r"\sqrt[3]{x}", "x^(1/3)"),
    (r"\left( \frac{a}{b} \right)^2", "(a/b)^2"),
    (r"\sin^2\theta + \cos^2\theta", "sin(theta)^2 + cos(theta)^2"),
    (r"v_0 \sin\alpha\, t", "v0 sin(alpha) t"),          # \, ends the argument
    (r"\sin 2\alpha", "sin(2 alpha)"),
    (r"E_{kin} + E_{\text{pot}}", "Ekin + Epot"),
    (r"e^{-\lambda t}", "exp(-lambda t)"),
    (r"|x-1|", "Abs(x - 1)"),
    (r"9{,}81", "981/100"),
    (r"60^\circ", "pi/3"),
    (r"a \cdot b \times c", "a b c"),
    (r"v_1'", "v1prime"),
    (r"2\pi\sqrt{\frac{l}{g}}", "2 pi sqrt(l/g)"),
    (r"\ln(2) + \exp(x)", "log(2) + exp(x)"),
])
def test_translation(latex, plain):
    assert _eq(latex, plain), latex_to_expr(latex)


@pytest.mark.parametrize("bad", [r"\int x\,dx", r"\frac{1}{2", r"a = b",
                                 r"\text{hello world}", r"\unknowncommand x"])
def test_rejects(bad):
    with pytest.raises(mg.ParseError):
        parse_latex(bad)


def test_latex_in_json_checks():
    r = mg.verify({"check": "equal", "lhs": r"\frac{(a+b)^2}{2}",
                   "rhs": r"\tfrac12 a^2 + ab + \tfrac12 b^2", "latex": True})
    assert r.ok

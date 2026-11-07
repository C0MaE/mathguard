import pytest

import mathguard as mg
from mathguard import Status


# ---------------------------------------------------------------- equalities

@pytest.mark.parametrize("lhs, rhs", [
    ("sin(x)^2 + cos(x)^2", "1"),
    ("(a+b)^2", "a^2 + 2a b + b^2"),
    ("exp(i_ x)", "exp(i_ x)"),
    ("cosh(x)^2 - sinh(x)^2", "1"),
    ("(x^3 - 1)/(x - 1)", "x^2 + x + 1"),
])
def test_true_identities_are_verified(lhs, rhs):
    v = mg.check_equal(lhs, rhs)
    assert v.status == Status.VERIFIED, v


@pytest.mark.parametrize("lhs, rhs", [
    ("(a+b)^2", "a^2 + b^2"),
    ("sin(2x)", "2 sin(x)"),
    ("sqrt(x^2)", "x"),
])
def test_false_identities_come_with_counterexample(lhs, rhs):
    v = mg.check_equal(lhs, rhs)
    assert v.status == Status.REFUTED
    assert v.counterexample and "lhs" in v.counterexample


def test_assumptions_change_the_answer():
    assert mg.check_equal("sqrt(x^2)", "x").status == Status.REFUTED
    assert mg.check_equal("sqrt(x^2)", "x", {"x": "positive"}).ok
    assert mg.check_equal("log(x y)", "log(x) + log(y)",
                          {"x": "positive", "y": "positive"}).ok


def test_constant_mismatch():
    assert mg.check_equal("2 + 2", "5").status == Status.REFUTED


# ---------------------------------------------------------------- chains

def test_chain_points_at_wrong_step():
    r = mg.check_chain([
        "(x+1)^2 - (x-1)^2",
        "x^2 + 2x + 1 - (x^2 - 2x + 1)",
        "4x + 2",   # <- mistake introduced here
    ])
    assert [v.status for v in r.verdicts] == [Status.VERIFIED, Status.REFUTED]
    assert r.status == Status.REFUTED


def test_chain_needs_two_steps():
    assert mg.check_chain(["x"]).status == Status.ERROR


# ---------------------------------------------------------------- calculus

def test_derivative():
    assert mg.check_derivative("x^2 sin(x)", "2x sin(x) + x^2 cos(x)").ok
    assert mg.check_derivative("x^2 sin(x)", "2x cos(x)").status == Status.REFUTED
    assert mg.check_derivative("x^3", "6x", order=2).ok


def test_derivative_other_variable():
    assert mg.check_derivative("1/2 m v^2", "m v", variable="v").ok


def test_antiderivative_ignores_constant():
    assert mg.check_antiderivative("x exp(x)", "(x - 1) exp(x) + 7").ok
    assert mg.check_antiderivative("x exp(x)", "x exp(x)").status == Status.REFUTED


def test_definite_integral_numeric_and_symbolic():
    assert mg.check_definite_integral("exp(-x^2)", "x", "-oo", "oo", "sqrt(pi)").ok
    assert mg.check_definite_integral("x^2", "x", 0, "a", "a^3/3").ok
    assert mg.check_definite_integral("sin(x)", "x", 0, "pi", 1).status == Status.REFUTED


def test_limits():
    assert mg.check_limit("sin(x)/x", "x", 0, 1).ok
    ke = "(1/sqrt(1 - v^2/c^2) - 1) m c^2"
    assert mg.check_limit(ke, "c", "oo", "1/2 m v^2", {"c": "positive", "v": "positive"}).ok
    assert mg.check_limit(ke, "c", "oo", "m v^2", {"c": "positive", "v": "positive"}).status \
        == Status.REFUTED


# ---------------------------------------------------------------- equations

def test_solutions_complete_and_incomplete():
    assert mg.check_solutions("x^2 - 5x + 6 = 0", "x", ["2", "3"]).ok
    r = mg.check_solutions("x^2 - 5x + 6 = 0", "x", ["2"])
    assert r.status == Status.REFUTED
    assert "missing" in r.verdicts[-1].message


def test_wrong_solution():
    r = mg.check_solutions("x^2 = 4", "x", ["2", "4"], complete=False)
    assert [v.status for v in r.verdicts] == [Status.VERIFIED, Status.REFUTED]


# ---------------------------------------------------------------- numbers

def test_value():
    assert mg.check_value("sqrt(2) pi", 4.44288, rel_tol=1e-5).ok
    assert mg.check_value("exp(pi) - pi", 20).status == Status.REFUTED
    assert mg.check_value("x + 1", 2).status == Status.ERROR


def test_solutions_completeness_respects_positive_variable():
    # t = 0 also solves the equation but is excluded by t > 0
    r = mg.check_solutions("2 c1 t - 3 c2 t^2 = 0", "t", ["2 c1/(3 c2)"],
                        {"c1": "positive", "c2": "positive", "t": "positive"})
    assert r.ok
    r = mg.check_solutions("2 c1 t - 3 c2 t^2 = 0", "t", ["2 c1/(3 c2)"],
                        {"c1": "positive", "c2": "positive"})
    assert r.status.value == "refuted"

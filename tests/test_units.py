from mathguard import Status, check_dimensions, dimension_of

U = {"E": "J", "m": "kg", "c": "m/s", "v": "m/s", "t": "s", "x": "m",
     "a": "m/s^2", "k": "boltzmann_constant", "T": "K"}


def test_consistent_equations():
    assert check_dimensions(U, equation="E = m c^2").ok
    assert check_dimensions(U, equation="x = v t + 1/2 a t^2").ok
    assert check_dimensions(U, equation="E = m c^2 exp(-E/(k T))").ok


def test_inconsistent_equations():
    assert check_dimensions(U, equation="E = m c").status == Status.REFUTED
    v = check_dimensions(U, equation="x = v t + a t")
    assert v.status == Status.REFUTED and "cannot add" in v.message


def test_transcendental_argument_must_be_dimensionless():
    v = check_dimensions(U, equation="E = m c^2 exp(-E)")
    assert v.status == Status.REFUTED and "exp" in v.message


def test_expected_unit():
    assert check_dimensions(U, expression="1/2 m v^2", expected="eV").ok
    assert check_dimensions(U, expression="m v", expected="J").status == Status.REFUTED


def test_physical_constants_and_keywords():
    units = {"G": "gravitational_constant", "M": "kg", "r": "m", "v": "m/s"}
    assert check_dimensions(units, equation="v = sqrt(G M / r)").ok
    d = dimension_of("h c / lambda", {"h": "planck_constant", "c": "speed_of_light",
                                      "lambda": "nm"})
    assert "[mass]" in d and "[time] ** 2" in d


def test_missing_unit_is_an_input_error():
    assert check_dimensions({"m": "kg"}, equation="E = m").status == Status.ERROR

import json
from pathlib import Path

import pytest

import mathguard as mg
from mathguard.api import verify
from mathguard.cli import main

ROOT = Path(__file__).resolve().parents[1]
GRADING = ROOT / "examples" / "grading"
GIVEN = {"h": "1.2 m", "g": "9.81 m/s^2"}


def grade_of(answer, reference, **kw):
    kw.setdefault("steps", False)
    return mg.check_answer(answer, reference, **kw)


# ------------------------------------------------------------------ formulas

def test_equivalent_formula_in_latex_is_correct():
    r = grade_of(r"So $v = \sqrt{\tfrac{10}{7} g h}$.", "v = sqrt(10 g h / 7)")
    assert r.status == mg.Grade.CORRECT
    assert r["v"].extracted.line == 1


def test_wrong_formula_is_wrong():
    r = grade_of("v = sqrt(2 g h)", "v = sqrt(10 g h / 7)")
    assert r.status == mg.Grade.WRONG
    assert "differs" in r["v"].message


def test_unicode_and_underscores_in_plain_text():
    r = grade_of("E = A (R_a − R_i)/(ε₀ r²)", {"E": "A (Ra - Ri)/(eps0 r^2)"})
    assert r.ok


def test_answer_may_use_its_own_earlier_results():
    text = "v = sqrt(10 g h / 7)\n\nThe mean speed is v/2, so t = 2 L / v."
    r = grade_of(text, {"t": "2 L / sqrt(10 g h / 7)"})
    assert r.ok and "inserted v" in r["t"].message


def test_given_numbers_inserted_into_a_formula():
    # c1 = 0.8 m/s^3 and c2 = 0.1 m/s^4 were inserted by the answer
    r = grade_of("a = 1.6 t - 0.3 t^2", {"a": "2 c1 t - 3 c2 t^2"},
                 given={"c1": "0.8 m/s^3", "c2": "0.1 m/s^4"}, units={"t": "s"})
    assert r.ok


def test_result_named_after_a_given_quantity():
    # regression: "Wel = U = 4.95 J" with U given crashed in the comparison
    r = grade_of("Wel = U = 4.95 J", {"Wel": "eps0 A U^2 / (2 d)"},
                 given={"A": "0.01 m^2", "d": "1 mm", "U": "100 V", "eps0": "8.854e-12 F/m"})
    assert r.status == mg.Grade.WRONG


def test_greek_letter_as_plain_label():
    assert grade_of("RESULT\nθ [critical angle] = 41.8 deg", {"theta": "41.81 deg"}).ok


def test_given_symbol_written_after_a_number():
    # "0.3268g" is 0.3268 times g, not grams; "m/s^2" stays a unit even if m and s are variables
    r = grade_of("a = 0.3268g = 3.22 m/s^2", {"a": "g (sin(alpha) - mu cos(alpha))"},
                 given={"g": "9.81 m/s^2", "alpha": "30 deg", "mu": "0.2"},
                 units={"m": "kg", "s": "m"})
    assert r.ok
    # but "2.04 m" is metres even if the task has a mass m
    assert grade_of("h = 2.04 m", {"h": "k d^2 / (2 m g)"}, given={"k": "200 N/m", "d": "10 cm",
                    "m": "50 g", "g": "9.81 m/s^2"}).ok


def test_escaped_asterisk_and_thousands_separator():
    r = grade_of(r"B = 1.006 \* 10^(-3) T", {"B": "4e-5 T"})
    assert r.status == mg.Grade.WRONG and r["B"].extracted.value == pytest.approx(1.006e-3)
    assert grade_of("T = 38,794.8 s", {"T": "38795 s"}).ok


def test_other_variables_are_not_judged():
    r = grade_of("v = sqrt(2 g s sin(alpha))", "v = sqrt(2 g h)")
    assert r.status == mg.Grade.INCONCLUSIVE
    assert "not compared" in r["v"].message


def test_elementary_charge_written_as_e():
    r = grade_of("d = p/(8 e)", {"d": "p/(8 qe)"})
    assert r.ok


# ------------------------------------------------------------------- numbers

def test_number_with_other_unit():
    assert grade_of("Result: v ≈ 14,8 km/h", "v = 4.10 m/s").ok


def test_number_against_formula_reference_uses_given_values():
    r = grade_of(r"$v \approx 4{,}1\,\mathrm{m/s}$", "v = sqrt(10 g h / 7)", given=GIVEN)
    assert r.ok
    r = grade_of(r"$v \approx 2{,}87\,\mathrm{m/s}$", "v = sqrt(10 g h / 7)", given=GIVEN)
    assert r.status == mg.Grade.WRONG


def test_formula_answer_against_number_reference():
    r = grade_of("t = sqrt(2 h / g)", {"t": "0.495 s"}, given=GIVEN)
    assert r.ok


def test_rounding_of_written_digits():
    assert grade_of("v = 4 m/s", "v = 4.1 m/s").ok          # 1 digit: ±13 %
    assert not grade_of("v = 4.0 m/s", "v = 4.1 m/s").ok    # 2 digits: ±1.3 %


def test_wrong_dimension_is_wrong():
    r = grade_of("v = 4.1 m", "v = 4.1 m/s")
    assert r.status == mg.Grade.WRONG and "dimension" in r["v"].message


def test_scientific_notation():
    assert grade_of(r"$E = 1{,}6 \cdot 10^{-19}\,\mathrm{J}$", "E = 1.602e-19 J").ok
    assert grade_of("E = 1.6e-19 J", "E = 1.602e-19 J").ok


def test_temperature_absolute_and_difference():
    assert grade_of("T = 25 °C", "T = 298.15 K").ok
    assert grade_of("dT = 3.5 °C", {"dT": {"value": 3.5, "unit": "K"}}).ok


def test_remark_in_parentheses_after_a_number():
    assert grade_of("kA = exp(-delta T) = 0,45 (0,448)", {"kA": 0.4477}).ok


def test_product_of_variables_is_not_a_unit():
    r = grade_of("dF = 6 m g", {"dF": "6 m g"}, units={"m": "kg", "g": "m/s^2"})
    assert r.ok


# ---------------------------------------------------------------- extraction

def test_last_result_wins_and_boxed_wins():
    text = "First guess v = 3 m/s.\n\nCorrected: v = 4.1 m/s"
    assert grade_of(text, "v = 4.1 m/s").ok
    text = r"$\boxed{v = 4{,}1\,\mathrm{m/s}}$ ... later a check: v = 3 m/s"
    assert grade_of(text, "v = 4.1 m/s").ok


def test_result_section():
    text = "v = 3 m/s is a first estimate.\n\nRESULT\nv [speed] = 4.1 m/s\n\nv = 2 m/s would be too slow."
    assert grade_of(text, "v = 4.1 m/s").ok


def test_name_spellings_and_aliases():
    assert grade_of(r"$\lambda = 0{,}1\,\mathrm{m}$", {"lam": "0.1 m"}).ok
    assert grade_of("v_0 = 3 m/s", {"v0": "3 m/s"}).ok
    assert grade_of("T = 2 s", {"t": {"value": 2, "unit": "s", "aliases": ["T"]}}).ok


def test_missing_quantity():
    r = grade_of("No result here.", "v = 4.1 m/s")
    assert r.status == mg.Grade.MISSING


def test_parts():
    text = "a) $t = \\sqrt{2h/g}$\n\nb) The speed is v = 4.9 m/s.\n\nc) With drag v = 4.1 m/s."
    ref = {"t": {"formula": "sqrt(2 h / g)", "part": "a"},
           "v": {"formula": "sqrt(2 g h)", "unit": "m/s", "part": "b"}}
    r = grade_of(text, ref, given=GIVEN)
    assert r.ok
    assert r["v"].extracted.line == 3


def test_formula_from_earlier_line_is_added():
    text = "$$v = \\sqrt{\\tfrac{10}{7} g h}$$\n\nNumbers: $v \\approx 4{,}10\\,\\mathrm{m/s}$"
    r = grade_of(text, "v = sqrt(10 g h / 7)", given=GIVEN)
    ex = r["v"].extracted
    assert r.ok and ex.formula and ex.value == pytest.approx(4.10) and ex.formula_line == 1


# --------------------------------------------------------------------- steps

def test_steps_point_at_the_error():
    text = (GRADING / "answers" / "model-b" / "rolling.md").read_text(encoding="utf-8")
    task = mg.load_task(GRADING / "tasks" / "rolling.yaml") if _yaml() else None
    if task is None:
        pytest.skip("needs PyYAML")
    r = mg.grade(task, text)
    assert r.status == mg.Grade.WRONG
    assert r.steps is not None and r.steps.first_error.line == 7


def _yaml():
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


# -------------------------------------------------------------- interfaces

def test_report_formats():
    r = mg.check_answer("v = sqrt(2 g h)", "v = sqrt(10 g h / 7)")
    d = r.to_dict()
    assert d["status"] == "wrong" and d["total"] == 1 and d["quantities"][0]["name"] == "v"
    json.dumps(d)
    assert "WRONG" in str(r) and r.to_markdown().startswith("**mathguard: WRONG**")


def test_json_api():
    rep = verify({"check": "answer", "answer": "v = 4.1 m/s", "reference": {"v": "4.1 m/s"}})
    assert rep.ok and rep.verdicts[0].check == "answer:v"
    rep = verify({"check": "answer", "answer": "v = 2 m/s", "reference": "v = 4.1 m/s"})
    assert rep.status == mg.Status.REFUTED


def test_bad_reference_is_an_error():
    rep = verify({"check": "answer", "answer": "v = 1", "reference": {"v": "sqrt(__import__)"}})
    assert rep.status == mg.Status.ERROR


def test_cli_answer(tmp_path, capsys):
    f = tmp_path / "a.md"
    f.write_text("v = 14.8 km/h", encoding="utf-8")
    assert main(["answer", str(f), "--ref", "v = 4.1 m/s"]) == 0
    assert main(["answer", str(f), "--ref", "v = 3 m/s"]) == 1
    f.write_text("nothing", encoding="utf-8")
    assert main(["answer", str(f), "--ref", "v = 3 m/s"]) == 2


@pytest.mark.skipif(not _yaml(), reason="needs PyYAML")
def test_cli_grade_directories(capsys):
    code = main(["grade", str(GRADING / "tasks"), str(GRADING / "answers")])
    out = capsys.readouterr().out
    assert code == 1
    assert "2 answers, 1 fully correct; 2/4 quantities correct" in out


def test_grade_with_benchmark_task_format():
    task = {
        "given": {"h": "1.2 m", "g": "9.81 m/s^2"},
        "auxiliary": {"m": "kg"},
        "wanted": {"v": {"unit": "m/s"}},
        "reference": {"status": "checked",
                      "v": {"path_a": {"formula": "sqrt(10 g h / 7)"}, "value": 4.101,
                            "rel_tol": 1e-4}},
    }
    assert mg.grade(task, "v = 4.1 m/s", steps=False).ok


def test_time_limit_without_setitimer(monkeypatch):
    """Pyodide has SIGALRM but no setitimer; the limit is then skipped."""
    import signal

    from mathguard import _timeout

    monkeypatch.delattr(signal, "setitimer", raising=False)
    assert _timeout.run_with_limit(lambda: 42, 1.0) == 42

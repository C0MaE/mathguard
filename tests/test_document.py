from pathlib import Path

import mathguard as mg
from mathguard.cli import main

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "benchmark" / "responses" / "demo"


def test_identity_chain_points_at_wrong_step():
    r = mg.check_document(r"$$ (a+b)^2 = a^2 + 2ab + b^2 = a^2 + b^2 $$")
    assert r.status == mg.Status.REFUTED
    assert [s.status.value for s in r.steps] == ["verified", "refuted"]


def test_align_continuation_rows_and_line_numbers():
    text = "Text\n\\begin{align}\nx &= (a+b)(a-b) \\\\\n  &= a^2 - b^2\n\\end{align}\n"
    r = mg.check_document(text)
    assert r.ok
    assert r.steps[0].line == 4


def test_definitions_are_inserted():
    text = r"$T = \frac{2 v_0 \sin\alpha}{g}$ and $$x = v_0 \cos\alpha \cdot T = \frac{v_0^2 \sin 2\alpha}{g}$$"
    r = mg.check_document(text)
    assert r.ok and "T" in r.definitions


def test_later_definition_after_use():
    text = r"$$ F = \frac{m v^2}{r} = m \omega^2 r $$ with $v = \omega r$."
    assert mg.check_document(text).ok


def test_numbers_use_written_precision():
    ok = mg.check_document(r"$v = \sqrt{2 \cdot 9{,}81 \cdot 2} \approx 6{,}26\,\mathrm{m/s}$")
    bad = mg.check_document(r"$v = \sqrt{2 \cdot 9{,}81 \cdot 2} \approx 6{,}4\,\mathrm{m/s}$")
    assert ok.ok and bad.status == mg.Status.REFUTED


def test_equation_contradicting_an_earlier_one():
    text = (r"$$ m g h = \frac12 m v^2 $$ "
            r"Damit $v^2 = g h$.")
    r = mg.check_document(text)
    assert r.status == mg.Status.REFUTED
    assert "contradicts line" in r.first_error.verdicts[0].message


def test_new_physics_equation_is_not_judged():
    r = mg.check_document(r"$$ m a = m g \sin\alpha $$")
    assert r.status == mg.Status.INCONCLUSIVE  # nothing to check, no false alarm
    assert r.steps[0].status is None


def test_units_in_every_step():
    text = r"$$ s = v t + \frac12 a t = v t + \frac{a t}{2} $$"
    r = mg.check_document(text, units={"s": "m", "v": "m/s", "a": "m/s^2", "t": "s"})
    dims = [v for st in r.steps for v in st.verdicts if v.check == "dimensions"]
    assert dims and all(v.status == mg.Status.REFUTED for v in dims)


def test_demo_rollen_error_is_found():
    r = mg.check_document((DEMO / "demo-rolling.md").read_text(encoding="utf-8"))
    assert r.status == mg.Status.REFUTED
    assert r.first_error.line == 6


def test_demo_wurf_is_clean():
    r = mg.check_document((DEMO / "demo-projectile.md").read_text(encoding="utf-8"))
    assert r.ok


def test_json_and_cli(capsys, tmp_path):
    rep = mg.verify({"check": "document", "text": r"$$ (x+1)^2 = x^2 + 2x + 1 $$"})
    assert rep.ok
    f = tmp_path / "s.md"
    f.write_text(r"$$ (x+1)^2 = x^2 + 2x + 1 = x^2 + 1 $$", encoding="utf-8")
    assert main(["doc", str(f)]) == 1
    assert "first error in line 1" in capsys.readouterr().out

"""mathguard as an Inspect AI scorer."""
import asyncio

import pytest

pytest.importorskip("inspect_ai")

from inspect_ai.model import ModelName, ModelOutput  # noqa: E402
from inspect_ai.scorer import Target  # noqa: E402
from inspect_ai.solver import TaskState  # noqa: E402

from mathguard.inspect_scorer import mathguard_scorer, open_bench, task_dataset  # noqa: E402


def score(answer, target="", metadata=None, **kw):
    state = TaskState(model=ModelName("mockllm/model"), sample_id=1, epoch=1, input="?",
                      messages=[], output=ModelOutput.from_content("mockllm/model", answer),
                      metadata=metadata or {})
    return asyncio.run(mathguard_scorer(**kw)(state, Target(target)))


def test_target_as_reference():
    s = score(r"So $v \approx 4{,}1\,\mathrm{m/s}$.", "v = sqrt(10 g h / 7)",
              {"given": {"h": "1.2 m", "g": "9.81 m/s^2"}})
    assert s.value == "C" and s.metadata["status"] == "correct"
    assert score("v = 14.8 km/h", "v = 4.1 m/s").value == "C"


def test_wrong_missing_inconclusive():
    s = score("v = 2 m/s", "v = 4.1 m/s")
    assert s.value == "I" and "WRONG" in s.explanation and s.answer.startswith("v =")
    assert score("I don't know.", "v = 4.1 m/s").value == "N"
    other_vars = "v = sqrt(2 g s sin(alpha))"
    assert score(other_vars, "v = sqrt(2 g h)").value == "I"
    with pytest.raises(ValueError):
        mathguard_scorer(inconclusive="maybe")


def test_open_bench_dataset_and_task():
    task = open_bench()
    assert len(task.dataset) >= 20
    sample = next(s for s in task.dataset if s.id == "ob-mech-02")
    assert "RESULT" in sample.input and sample.metadata["topic"] == "Atwood machine"
    answer = "a = (m1 - m2) g / (m1 + m2) = 1.96 m/s^2\nF = 2 m1 m2 g / (m1 + m2) = 23.5 N"
    assert score(answer, metadata=sample.metadata).value == "C"
    assert score("a = 1.96 m/s^2\nF = 30 N", metadata=sample.metadata).value == "I"


def test_task_dataset_from_files(tmp_path):
    f = tmp_path / "t.yaml"
    f.write_text("statement: How fast?\nwanted: {v: {unit: m/s}}\n"
                 "reference: {v: {path_a: {formula: '3'}, value: 3}}\n", encoding="utf-8")
    ds = task_dataset(tmp_path)
    assert len(ds) == 1 and ds[0].id == "t" and "v = <formula> = <value> m/s" in ds[0].input

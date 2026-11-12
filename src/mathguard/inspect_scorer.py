"""mathguard as a scorer for Inspect AI (https://inspect.aisi.org.uk).

Grades the final answer of a model with :func:`mathguard.check_answer`:
formulas are compared symbolically, numbers with unit conversion and a
rounding-aware tolerance. Install with ``pip install "mathguard[inspect]"``.

Two ways to give the reference:

* ``Sample(input=..., target="v = sqrt(2 g h)", metadata={"given": {"h": "1.2 m"}})``
  -- the target is the reference; ``given``, ``units``, ``assumptions`` and
  ``rel_tol`` in the metadata are passed on.
* ``Sample(..., metadata={"mathguard_task": task})`` -- a whole task (the
  format of :func:`mathguard.grade`, e.g. a file of the open benchmark).

``task_dataset`` turns task files into samples, and ``open_bench`` is a
ready-made Inspect task for the open benchmark::

    inspect eval mathguard/open_bench --model openai/gpt-4o-mini
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from pathlib import Path
from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import MemoryDataset, Sample
    from inspect_ai.scorer import (
        CORRECT,
        INCORRECT,
        NOANSWER,
        PARTIAL,
        Score,
        Target,
        accuracy,
        scorer,
        stderr,
    )
    from inspect_ai.solver import TaskState, generate
except ImportError as exc:  # pragma: no cover
    raise ImportError('The Inspect scorer needs Inspect AI: pip install "mathguard[inspect]"') from exc

from .answer import AnswerReport, Grade, check_answer, grade, load_task

__all__ = ["mathguard_scorer", "task_dataset", "build_prompt", "open_bench"]

_VALUE = {Grade.CORRECT: CORRECT, Grade.WRONG: INCORRECT, Grade.MISSING: NOANSWER}

PROMPT_TEMPLATE = """\
Solve the following physics problem. Show your work step by step.

{statement}
End your answer with exactly this block (one line per requested quantity,
formula in the symbols of the problem, numerical value in the given unit):

RESULT
{result}
"""


def _grade_sample(answer: str, target: Target, metadata: dict[str, Any], steps: bool,
                  rel_tol: float) -> AnswerReport:
    task_spec = metadata.get("mathguard_task")
    if task_spec:
        return grade(task_spec, answer, steps=steps)
    reference = target.text if len(target.target) <= 1 else "\n".join(target.target)
    return check_answer(answer, reference, given=metadata.get("given"),
                        units=metadata.get("units"), assumptions=metadata.get("assumptions"),
                        rel_tol=float(metadata.get("rel_tol", rel_tol)), steps=steps)


@scorer(metrics=[accuracy(), stderr()])
def mathguard_scorer(steps: bool = False, rel_tol: float = 0.01, inconclusive: str = "incorrect"):
    """Score the model's final answer with mathguard.

    Args:
        steps: also check the calculation steps of the answer (slower); the
            result is in the score metadata, it does not change the grade.
        rel_tol: minimum relative tolerance for numbers (the rounding of the
            written digits can allow more).
        inconclusive: how to count answers mathguard cannot decide (e.g. a
            formula in other variables): "incorrect" (default) or "partial"
            (counts the share of quantities that were graded correct).
    """
    if inconclusive not in ("incorrect", "partial"):
        raise ValueError("inconclusive must be 'incorrect' or 'partial'")

    async def score(state: TaskState, target: Target) -> Score:
        answer = state.output.completion if state.output else ""
        rep = await asyncio.to_thread(_grade_sample, answer, target, dict(state.metadata or {}),
                                      steps, rel_tol)
        status = rep.status
        if status in _VALUE:
            value: Any = _VALUE[status]
        elif inconclusive == "partial":
            value = PARTIAL if rep.score > 0 else INCORRECT
        else:
            value = INCORRECT
        found = [f"{r.name} = {r.extracted.text}" for r in rep.results if r.extracted]
        return Score(value=value, answer="; ".join(found) or None,
                     explanation=rep.to_markdown(), metadata=rep.to_dict())

    return score


def build_prompt(spec: dict[str, Any]) -> str:
    """The benchmark prompt: the statement plus a RESULT block for every wanted quantity."""
    lines = []
    for name, w in spec["wanted"].items():
        label = f"{name} [{w['description']}]" if w.get("description") else name
        if w.get("symbolic_only"):
            lines.append(f"{label} = <formula>")
        else:
            lines.append(f"{label} = <formula> = <value> {w['unit']}")
    return PROMPT_TEMPLATE.format(statement=spec["statement"].rstrip() + "\n",
                                  result="\n".join(lines))


def task_dataset(paths: str | Path | Iterable[str | Path]) -> MemoryDataset:
    """Samples from benchmark task files (a file, a directory or a list of files)."""
    if isinstance(paths, (str, Path)):
        p = Path(paths)
        files = sorted(p.glob("*.yaml")) + sorted(p.glob("*.json")) if p.is_dir() else [p]
    else:
        files = [Path(x) for x in paths]
    samples = []
    for f in files:
        spec = load_task(f)
        if spec.get("demo"):
            continue
        samples.append(Sample(
            id=spec["id"], input=build_prompt(spec),
            target=[f"{k} = {(spec['reference'][k].get('path_a') or {}).get('formula', '')}"
                    for k in spec["wanted"]],
            metadata={"mathguard_task": spec, "subject": spec.get("subject"),
                      "topic": spec.get("topic")}))
    return MemoryDataset(samples, name=files[0].parent.name if files else "mathguard")


def _open_bench_dir() -> Path:
    from importlib.resources import files

    return Path(str(files("mathguard.open_bench") / "tasks"))


@task
def open_bench(tasks_dir: str | None = None, steps: bool = False) -> Task:
    """The mathguard open benchmark (24 physics exercises, CC BY 4.0)."""
    directory = Path(tasks_dir) if tasks_dir else _open_bench_dir()
    return Task(dataset=task_dataset(directory), solver=generate(),
                scorer=mathguard_scorer(steps=steps))

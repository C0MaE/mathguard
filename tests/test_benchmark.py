"""Smoke test for the benchmark script with the demo tasks."""

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("yaml")

BENCH = Path(__file__).resolve().parent.parent / "benchmark" / "bench.py"


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("bench", BENCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_demo_references_are_consistent(bench):
    tasks = bench.load_tasks(include_demo=True)
    assert {"demo-projectile", "demo-rolling"} <= set(tasks)
    for t in (tasks["demo-projectile"], tasks["demo-rolling"]):
        assert all(level != "error" for level, _ in bench.validate_task(t))


def test_wrong_second_route_is_caught(bench):
    t = bench.load_tasks(include_demo=True)["demo-projectile"]
    t["reference"]["R"]["path_b"]["formula"] = "v0^2 sin(alpha) / g"
    assert any(level == "error" for level, _ in bench.validate_task(t))


def test_demo_error_is_localised(bench):
    t = bench.load_tasks(include_demo=True)["demo-rolling"]
    ann = bench.load_yaml(bench.ANNOTATIONS / "demo" / "demo-rolling.yaml")
    row = bench.evaluate_one(t, ann, bench.DEFAULT_NUM_TOL)
    assert not row["correct"] and row["flagged"]
    assert row["refuted_steps"] == ["2"]
    assert row["errors"][0]["located"]


def test_correct_demo_answer_is_not_flagged(bench):
    t = bench.load_tasks(include_demo=True)["demo-projectile"]
    ann = bench.load_yaml(bench.ANNOTATIONS / "demo" / "demo-projectile.yaml")
    row = bench.evaluate_one(t, ann, bench.DEFAULT_NUM_TOL)
    assert row["correct"] and not row["flagged"]

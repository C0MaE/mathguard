"""Every reference solution in the open benchmark must validate."""
import importlib.util
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
TASKS = sorted((ROOT / "open-bench" / "tasks").glob("*.yaml"))


def _bench():
    spec = importlib.util.spec_from_file_location("bench", ROOT / "benchmark" / "bench.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_open_bench_has_tasks():
    assert len(TASKS) >= 20


@pytest.mark.parametrize("path", TASKS, ids=lambda p: p.stem)
def test_reference_validates(path):
    bench = _bench()
    task = bench.load_yaml(path)
    assert task["id"] == path.stem
    problems = [m for level, m in bench.validate_task(task) if level != "ok"]
    assert not problems, problems

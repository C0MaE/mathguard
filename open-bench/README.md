# mathguard open benchmark

24 physics exercises at first-year university level, written for this repository and
released under [CC BY 4.0](LICENSE). Anyone can rerun the numbers, add a model or use the
tasks for another checker.

Each task has a statement (with all given values and units), the wanted quantities and a
reference solution with two independent solution paths. `bench.py validate` checks that both
paths agree symbolically, that the result has the right unit and that the given values yield
the stated number.

| Area | Tasks |
|---|---|
| Mechanics | 9 |
| Electromagnetism | 5 |
| Thermodynamics | 4 |
| Optics and waves | 4 |
| Modern physics | 2 |

Results for three models, with all answers and annotations: [RESULTS.md](RESULTS.md).

## Usage

```bash
pip install -e ".[dev,bench]"

python benchmark/bench.py --root open-bench validate   # check every reference
python benchmark/bench.py --root open-bench list       # overview table
python benchmark/bench.py --root open-bench prompts    # prompts into open-bench/results/prompts/
```

Model answers go to `open-bench/responses/<model>/<id>.md`, then `evaluate` and `report` work
as described in [benchmark/README.md](../benchmark/README.md). The task format is the same.

Grading a single answer with the answer checker:

```python
import mathguard as mg

task = mg.load_task("open-bench/tasks/ob-mech-02.yaml")
print(mg.grade(task, "a = (m1 - m2) g / (m1 + m2) = 1.96 m/s^2\nF = 23.5 N"))
```

With [Inspect AI](https://inspect.aisi.org.uk) (`pip install "mathguard[inspect]"`) the whole set
runs against any model, graded by mathguard:

```bash
inspect eval mathguard/open_bench --model anthropic/claude-haiku-5-5
```

## Why a second task set

The main benchmark uses exercises from university problem sets. Their texts are copyrighted,
so only aggregated results can be published. This set can be shared completely: tasks,
prompts, model answers and annotations.

## Citing

Please cite mathguard (see [CITATION.cff](../CITATION.cff)) and mention "mathguard open
benchmark" with the version you used.

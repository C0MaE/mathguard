# Benchmark: does mathguard find real AI mistakes?

The goal is an honest number: a model solves about 30 physics exercises "as usual".
We count the mistakes it makes and the share of them that mathguard finds,
broken down by error type.

## Workflow

```bash
pip install -e ".[dev,bench]"

python benchmark/bench.py new sheet03-ex2          # 1. create a task, fill it in
python benchmark/bench.py validate                # 2. check the reference (path A = path B, unit, number)
python benchmark/bench.py prompts                 # 3. prompts into results/prompts/
#    save the model answer unchanged: responses/<model>/<id>.md
python benchmark/bench.py annotate <model> <id>   # 4. create and fill in the annotation
python benchmark/bench.py evaluate                # 5. grade and run mathguard
python benchmark/bench.py report                  # 6. results/report.md
```

`benchmark/run_ollama.py` sends all prompts to a local Ollama model and stores the answers.

The two `demo-*` tasks were written for this repository and only show what the files
look like. They only count with `--demo` (`evaluate --demo`, `report --demo`).

## Task set

The benchmark uses 35 exercises from university physics problem sets (Physics I and II).
`python benchmark/bench.py list` prints an overview. Selected were exercises with an
unambiguous final result that are fully described without a figure; where a figure would be
needed, the geometry is spelled out in the statement.

The problem texts are copyrighted and **not part of this repository**. Task files, prompts,
model answers and annotations for them are excluded in `.gitignore` and kept privately.
Only aggregated results are published.

The field `author_discrepancy` documents where the reference differs from the author's own
solution. Such tasks are set to `status: disputed` until a decision is made.

## Files

| Path | Content |
|---|---|
| `tasks/<id>.yaml` | problem statement, given quantities with units, wanted quantities, reference solution |
| `responses/<model>/<id>.md` | raw model answer, unchanged |
| `annotations/<model>/<id>.yaml` | final result, errors found by hand, extracted checks |
| `error_types.yaml` | error categories, with a prior estimate of whether mathguard can find them |
| `results/` | generated: prompts, `<model>.json`, `report.md` |
| `migrate_schema.py` | renames keys of files written with the old (German) schema |

Only `statement` and `wanted` go into the prompt. The model never sees the reference.

## Reference solution

Every wanted quantity needs two independent solution paths (`path_a`, `path_b`), e.g.
energy conservation and a force balance. `validate` checks that

- path A and path B are symbolically equal (`check_equal`),
- optional `steps` form a correct chain and end at `formula`,
- the formula has the unit of the wanted quantity,
- inserting the given values yields `value` (tolerance `rel_tol`),
- optional `extra_checks` (any mathguard checks, e.g. an integral) hold.

Formulas without variables count as numbers in SI base units. If two paths only agree in the
physical range (e.g. $\sqrt{v^2} = v$ only for $v > 0$), `numeric_match_only: true` compares
the paths at the given values. `answer_tol` overrides the 1 % tolerance used for grading
model answers, e.g. for a refractive index $n \approx 1$.

`status: disputed` marks cases that still need a decision. Only `checked` counts as done.

## Grading an answer

**Correct or wrong** is decided by the reference: formula symbolically equal and
value within 1 % (`--num-tol`). This grading uses mathguard only as a tool;
it is not what is being measured.

**Measured** is whether mathguard finds something without the reference:

- the checks from the annotation (calculations from the answer, each with a `step`),
- automatically: the unit of the result formula, and whether the answer's own formula and
  its own value agree.

An answer counts as **flagged** if at least one check is `refuted`. An error counts as
**located** if a refuted check has the same `step`.

The report also lists refuted checks without an annotated error (missing annotation
or false alarm) and checks with `error`/`inconclusive` (hints where the parser falls short).

## Avoiding bias

As long as checks are transcribed from the answer by hand, the person transcribing often
already knows where the mistake is. That would inflate the hit rate. Therefore:

1. **Extract all checks first, then annotate errors.** Every calculation step of the answer
   gets a check, not only the suspicious ones.
2. Ideally the checks are extracted by someone who does not know the reference (or by a second
   model using `mathguard prompt` as instructions).
3. `mathguard doc` (LaTeX/Markdown import) is meant to automate the extraction and remove
   this bias entirely.

Errors in the physical approach (`approach`, `interpretation`) cannot be found by mathguard
by construction. They are counted anyway, so it is clear which share of all errors is
within reach at all.

## Choosing tasks

Suitable are exercises with an unambiguous final result (formula and/or number) that can be
written in mathguard syntax. Unsuitable are sketches, pure reasoning, reading off diagrams,
or exercises whose result is a piecewise function. Sub-exercises get their own files
(`sheet03-ex2b`).

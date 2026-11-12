# mathguard

[![PyPI](https://img.shields.io/pypi/v/mathguard)](https://pypi.org/project/mathguard/)
[![Python](https://img.shields.io/pypi/pyversions/mathguard)](https://pypi.org/project/mathguard/)
[![tests](https://github.com/C0MaE/mathguard/actions/workflows/tests.yml/badge.svg)](https://github.com/C0MaE/mathguard/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24147172.svg)](https://doi.org/10.5281/zenodo.24147172)

<!-- mcp-name: io.github.C0MaE/mathguard -->

**Verify mathematical claims — especially the ones language models make.**

LLMs are good at setting up calculations and surprisingly bad at carrying them
out reliably. `mathguard` is a small verification layer built on SymPy and Pint:

* **Grade answers against a reference** — formulas symbolically, numbers with
  unit conversion and rounding, for physics exercises and model evaluations.
* **Find the faulty step** in a worked solution written in Markdown/LaTeX.
* **Check single claims** (identities, derivatives, integrals, units) with a
  concrete counterexample when they are wrong.

**[Try it in your browser](https://c0mae.github.io/mathguard/)**, no install needed.

![mathguard doc finds the line where a worked solution goes wrong](https://raw.githubusercontent.com/C0MaE/mathguard/main/docs/demo.gif)

```python
>>> import mathguard as mg
>>> print(mg.check_chain([
...     "(x+1)^2 - (x-1)^2",
...     "x^2 + 2x + 1 - (x^2 - 2x + 1)",
...     "4x + 2",
... ]))
✔ [verified] step 1 → 2: (x+1)^2 - (x-1)^2 = x^2 + 2x + 1 - (x^2 - 2x + 1)
✘ [refuted] step 2 → 3: x^2 + 2x + 1 - (x^2 - 2x + 1) = 4x + 2 is false
    counterexample: x = 0.6067920837, lhs = 2.427168335, rhs = 4.427168335

Overall: REFUTED
```

Or grade a model's answer against a reference result in one call:

```python
>>> print(mg.check_answer("v = sqrt(g h) = 3.43 m/s", "v = sqrt(2 g h)",
...                       given={"h": "1.2 m", "g": "9.81 m/s^2"}))
mathguard answer check: 0/1 correct

✘ v (line 1): wrong — formula sqrt(g h) differs from the reference sqrt(2 g h); value 3.43 m/s differs from 4.85222 m/s by 29.3% (±1 %)

Overall: WRONG
```

### Grade answers against a reference (new in 0.3)

A task file holds the reference results and the known values:

```yaml
# examples/grading/tasks/rolling.yaml
given: {h: 1.2 m, L: 3 m, g: 9.81 m/s^2}
units: {m: kg, r: m}
reference:
  v: {formula: sqrt(10 g h / 7), unit: m/s}
  t: {formula: 2 L / sqrt(10 g h / 7), unit: s, aliases: [T]}
```

mathguard finds the final result for every quantity in each answer (plain text,
Markdown or LaTeX) and compares it with the reference:

```bash
mathguard grade examples/grading/tasks examples/grading/answers
```

```text
✔ examples/grading/answers/model-a/rolling.md  2/2  correct
✘ examples/grading/answers/model-b/rolling.md  0/2  wrong
    ✘ v: formula from line 7; formula \sqrt{\tfrac{7 g h}{10}} differs from the reference sqrt(10 g h / 7); value 2.87 m/s differs from 4.10087 m/s by 30.0% (±1 %)
    ✘ t: inserted v (line 7) from the answer; formula \frac{2L}{v} differs from the reference 2 L / sqrt(10 g h / 7); value 2.09 s differs from 1.4631 s by 42.8% (±1 %)
    working: first error in line 7: v^2 = \tfrac{7}{10} g h

2 answers, 1 fully correct; 2/4 quantities correct
```

Answer A wrote `v ≈ 14.8 km/h` and `T = 2 L / v`; both count as correct, because
units are converted and the answer's own `v` is inserted. For answer B the step
check also shows where the calculation went wrong.

### Check a whole answer (new in 0.2)

Paste a complete worked solution in Markdown/LaTeX and get a report per step:

```bash
mathguard doc solution.md
```

```text
· line 4: m g h = \tfrac12 m v^2 + \tfrac12 I \omega^2  [skipped]
    note: new equation, not derived from earlier ones (as an identity it would be false)
✔ line 4: \tfrac12 m v^2 + \tfrac12 I \omega^2 = \tfrac12 m v^2 + \tfrac15 m v^2  [verified]
    note: holds after inserting I, omega, v
✔ line 4: \tfrac12 m v^2 + \tfrac15 m v^2 = \tfrac{7}{10} m v^2  [verified]
✘ line 6: v^2 = \tfrac{7}{10} g h  [refuted]
    line 6: contradicts line 4: here v = sqrt(70)*sqrt(g)*sqrt(h)/10, but line 4 gives v = sqrt(70)*sqrt(g)*sqrt(h)/7
✔ line 6: v = \sqrt{\tfrac{7 g h}{10}}  [verified]
✔ line 8: \sqrt{0.7 \cdot 9.81 \cdot 1.2}\,\mathrm{m/s} \approx 2.87\,\mathrm{m/s}  [verified]

Overall: REFUTED (first error in line 6)
```

## What it checks

| Check | Example | How |
|---|---|---|
| `check_equal` | `sin(x)^2 + cos(x)^2 = 1` | symbolic simplification, then random numerical testing |
| `check_chain` | a derivation, step by step | `check_equal` on every consecutive pair; points at the faulty step |
| `check_derivative` | `d/dx x^2 sin(x)` | differentiates and compares |
| `check_antiderivative` | `∫ x eˣ dx = (x−1) eˣ` | differentiates the claim (constants of integration are ignored) |
| `check_definite_integral` | `∫ e^(−x²) dx over ℝ = √π` | 30-digit quadrature, or symbolic if parameters remain |
| `check_solutions` | `x² − 5x + 6 = 0 → x ∈ {2, 3}` | substitutes each claim and checks no real solution is missing |
| `check_value` | `√2·π ≈ 4.44288` | high-precision evaluation with tolerance |
| `check_limit` | relativistic → classical limit | `sympy.limit` |
| `check_answer` | final results against a reference | finds the results in the text, compares formulas symbolically and numbers with Pint |
| `check_document` | a whole Markdown/LaTeX solution | finds every formula chain, checks rewritings, compares new equations with earlier ones, recomputes numbers |
| `check_dimensions` | `E = m c²` with units | dimensional analysis with [Pint](https://pint.readthedocs.io) |

### Honest statuses

| Status | Meaning |
|---|---|
| `verified` | the CAS reduced the claim to an identity (or evaluated it to tolerance) |
| `likely` | no symbolic proof, but many random points agree — strong evidence, **not** a proof |
| `refuted` | a concrete counterexample or contradiction was found |
| `inconclusive` | could not decide |
| `error` | the input could not be parsed |

`verified` means "a computer algebra system confirmed it", not "formally proven".
For machine-checked proofs, look at [Lean 4](https://lean-lang.org) and Mathlib.

## Installation

```bash
pip install mathguard
```

For development:

```bash
git clone https://github.com/C0MaE/mathguard && cd mathguard
pip install -e ".[dev]"
pytest
ruff check src tests
```

## Usage

### Python

```python
import mathguard as mg

mg.check_equal("sqrt(x^2)", "x")                      # refuted: fails for x < 0
mg.check_equal("sqrt(x^2)", "x", {"x": "positive"})   # verified

mg.check_derivative("1/2 m v^2", "m v", variable="v")
mg.check_antiderivative("1/x", "ln(x)")
mg.check_definite_integral("exp(-x^2)", "x", "-oo", "oo", "sqrt(pi)")
mg.check_solutions("x^2 - 5x + 6 = 0", "x", ["2"])    # refuted: 3 is missing

mg.check_limit("(1/sqrt(1 - v^2/c^2) - 1) m c^2", "c", "oo", "1/2 m v^2",
               {"c": "positive", "v": "positive"})    # verified

mg.check_dimensions({"x": "m", "v": "m/s", "a": "m/s^2", "t": "s"},
                    equation="x = v t + a t")
# refuted: cannot add 'a*t' [[length] / [time]] and 't*v' [[length]]
```

Every check returns a `Verdict` (or a `Report` for multi-part checks) with
`.status`, `.ok`, `.message`, `.counterexample` and `.to_dict()`.

### Whole solutions and LaTeX

```python
report = mg.check_document(open("solution.md").read(),
                           units={"v0": "m/s", "g": "m/s^2", "T": "s"})
print(report)              # one line per step, first error highlighted
report.to_markdown()       # for people
report.to_dict()           # for programs and LLMs

mg.parse_latex(r"\frac{1}{2} m v_0^2")   # -> m*v0**2/2
```

How a document is read:

* Formulas are taken from `$...$`, `$$...$$`, `\[...\]`, `\(...\)` and
  `align`/`equation`/`gather` environments; rows starting with `&=` continue
  the previous row.
* In a chain `a = b = c` every link is checked as an identity.
* A chain that starts with a single name (`T = \frac{2 v_0 \sin\alpha}{g}`)
  defines that name. Later steps that only hold after inserting definitions are
  accepted, and the report says which ones were used. Definitions written after
  their use (`… with $U_0 = Q_0/C$`) count for rewritings, never to justify an
  equation.
* An equation that is not an identity (`v^2 = \tfrac{7}{10} g h`) is compared
  with earlier equations: it either **follows** from one of them, **contradicts**
  one (both solved for the same variable give different results), or is reported
  as a **new equation** that is not judged. New physics laws are therefore never
  flagged as errors.
* Numbers with units (`\approx 35{,}3\,\mathrm{m}`) are recomputed and
  compared with the precision that was written.
* Variables are taken to be positive (physics convention); pass
  `positive=False` or `--real` to switch this off.
* LaTeX conventions apply: `mv^2` is `m*v^2`, `v_0` is the variable `v0`,
  `E_{kin}` is `Ekin`, `v'` is `vprime`, `60^\circ` is `pi/3`, `9{,}81` is `9.81`.

### Grading answers

```python
r = mg.check_answer(
    open("answer.md").read(),
    {"v": "sqrt(10 g h / 7)", "t": {"value": 1.46, "unit": "s", "aliases": ["T"]}},
    given={"h": "1.2 m", "g": "9.81 m/s^2", "L": "3 m"},
)
r.status            # Grade.CORRECT / WRONG / MISSING / INCONCLUSIVE
r.score             # share of correct quantities
r["v"].extracted    # what was read from the answer (line, formula, value, unit)
r.steps             # step check of the working (check_document), if it has formulas

mg.grade("task.yaml", answer_text)   # same, with a task file
```

* **Finding the result.** For each quantity mathguard takes the last line
  `name = …` (also `name [description] = …`, `x(t) = …`, `$v_0 = …$`).
  A `\boxed{}` result or a block under a heading such as `Result` / `Ergebnis`
  wins. Name spellings are matched loosely (`v_0` = `v0`, `\lambda` = `lam`,
  `\varepsilon_0` = `eps0`); `aliases` adds more names, and `part: b` only looks
  inside the answer's part `b)`.
* **Formulas** are compared with `check_equal` (variables positive). If the
  answer uses its own earlier results (`t = 2 L / v`), they are inserted. If it
  inserted given numbers (`1.6 t` for `2 c1 t`), the given values are inserted on
  both sides. A formula in other variables than the reference is not judged.
* **Numbers** are converted to the reference unit. The tolerance is the larger of
  `rel_tol` (default 1 %) and half a unit in the last written digit, so `4 m/s`
  matches `4.1 m/s` but `4.0 m/s` does not. A formula reference is turned into a
  number with the `given` values, and so is a formula answer for a number
  reference. A wrong dimension (`4.1 m` for a speed) is wrong.
* **Grades:** `correct` if every comparison agrees, `wrong` if one disagrees,
  `missing` if no result was found, `inconclusive` if nothing could be compared.

Task files (YAML or JSON) have `reference`, and optionally `given`, `units`,
`assumptions` and `rel_tol`. Each reference entry is a string (`"sqrt(2 g h)"`,
`"4.1 m/s"`) or a mapping with `formula`, `value`, `unit`, `rel_tol`, `aliases`,
`part`. Tasks of the benchmark format (`wanted` + `reference` with `path_a`) work
as well.

### JSON (for LLM tool calls)

```python
mg.verify([
    {"check": "equal", "lhs": "(a+b)^2", "rhs": "a^2 + 2 a b + b^2"},
    {"check": "dimensions", "equation": "E = m c^2",
     "units": {"E": "J", "m": "kg", "c": "speed_of_light"}},
]).to_dict()
```

`mg.LLM_INSTRUCTIONS` contains a ready-made description of the format that you
can paste into a system prompt.

### Command line

```bash
mathguard equal "sin(x)^2 + cos(x)^2" "1"
mathguard equal "sqrt(x^2)" "x" --assume x=positive
mathguard chain "(x+1)^2" "x^2 + 2x + 1"
mathguard dims "E = m c^2" --unit E=J --unit m=kg --unit c=m/s
mathguard check examples/checks.json
mathguard doc solution.md --unit v0=m/s --unit g=m/s^2   # whole solution
mathguard answer answer.md --ref "v = sqrt(10 g h / 7)" --given h="1.2 m" --given g="9.81 m/s^2"
mathguard grade task.yaml answer.md   # one task, one or more answers
mathguard grade tasks/ answers/       # answers matched to tasks by file name
mathguard prompt                      # print the LLM instructions
```

Exit codes: `0` all good (or all correct), `1` something was refuted (or wrong),
`2` inconclusive, missing or input error — so it can be used in CI. `--json`
goes before the command (`mathguard --json grade …`).

### MCP server (Claude Desktop, Claude Code, …)

**Claude Desktop, one click:** download
[`mathguard.mcpb`](https://github.com/C0MaE/mathguard/releases/latest/download/mathguard.mcpb)
from the latest release and open it (or drag it into *Settings → Extensions*).
Claude Desktop installs mathguard from PyPI with its bundled `uv`; no Python setup needed.

For other clients:

```bash
pip install mathguard
```

Register `mathguard-mcp` as a stdio server in your client. Example config:

```json
{
  "mcpServers": {
    "mathguard": { "command": "mathguard-mcp" }
  }
}
```

The server exposes `check_answer` (final results against a reference),
`check_solution` (a whole Markdown/LaTeX answer),
`verify_math`, `check_identity`, `check_derivation` and `check_units`, plus the
LLM instructions as server instructions.

### Agent skill (Claude Code, Cursor, Copilot, Codex, …)

[`skills/mathguard/`](https://github.com/C0MaE/mathguard/blob/main/skills/mathguard/SKILL.md) is an
[Agent Skill](https://agentskills.io): it tells a coding agent when to check
maths with mathguard, which tool to use, and how to act on the result. It uses
the MCP server when it is connected and falls back to the command line
otherwise.

```bash
npx skills add C0MaE/mathguard        # or copy skills/mathguard/ into your agent's skills folder
claude mcp add mathguard -- uvx mathguard mcp
```

Setup for other agents (Cursor, VS Code/Copilot, Codex, Claude Desktop, …) is in
[skills/mathguard/references/setup.md](https://github.com/C0MaE/mathguard/blob/main/skills/mathguard/references/setup.md).

### Inspect AI scorer

For model evaluations with [Inspect AI](https://inspect.aisi.org.uk),
`mathguard_scorer()` grades the final answer like `check_answer`: formulas
symbolically, numbers with units and a rounding-aware tolerance.

```bash
pip install "mathguard[inspect]"
inspect eval mathguard/open_bench --model openai/gpt-4o-mini   # the open benchmark, 24 physics tasks
```

```python
from inspect_ai import Task
from inspect_ai.dataset import Sample
from inspect_ai.solver import generate
from mathguard.inspect_scorer import mathguard_scorer

Task(
    dataset=[Sample(input="A ball rolls down a height h ... speed at the bottom?",
                    target="v = sqrt(10 g h / 7)",
                    metadata={"given": {"h": "1.2 m", "g": "9.81 m/s^2"}})],
    solver=generate(),
    scorer=mathguard_scorer(),
)
```

The target is the reference; `given`, `units`, `assumptions` and `rel_tol` in
the sample metadata are passed on. A whole task file goes into
`metadata={"mathguard_task": ...}`, and `task_dataset(path)` builds samples from
task files. Answers mathguard cannot decide count as incorrect, or as partial
with `mathguard_scorer(inconclusive="partial")`. The grading report is in the
score's explanation and metadata.

## Expression syntax

* Powers: `x^2` or `x**2`. Implicit multiplication: `2x`, `m c^2`, `x(y+1)`.
* **Multi-letter names are one variable** (`v0`, `dt`, `lambda`, `omega`).
  Write products of single letters with a space or `*`: `2 a b`, not `2ab`.
  mathguard warns when it looks like you meant a product.
* Functions: `sin cos tan exp log ln sqrt Abs sinh cosh tanh asin acos atan erf gamma …`
  — only when followed by `(`. On its own, `gamma` is a variable (Lorentz factor).
* Constants: `pi`, `e` (Euler), `oo`/`inf`. `E` and `I` are ordinary variables,
  because physicists use them for energy and current.
* Variables are **real** by default. Assumptions: `positive`, `negative`,
  `nonnegative`, `nonpositive`, `integer`, `nonzero`, `complex`.

## Security

Expressions are parsed with SymPy, whose parser uses `eval` internally. Because
inputs may come from a language model or a web page, mathguard only accepts a
whitelist of characters, rejects `__`, attribute access and dangerous names,
limits input length and evaluates with an empty builtins namespace. Still:
treat it like any parser of untrusted input and don't expose it to the internet
without a sandbox.

## Limitations

* **It checks computations, not models.** A correctly computed answer to the
  wrong equation is still wrong.
* Deciding whether two expressions are equal is undecidable in general
  (Richardson's theorem). When simplification fails, mathguard falls back to
  random numerical testing and reports `likely`, not `verified`.
* Numerical testing samples real values in roughly `[-20, 20]`; identities that
  only fail in exotic regions can slip through.
* Dimensional analysis sees the expression after SymPy's automatic
  simplification, so `E - E + m c` is checked as `m c`.
* `simplify` is given a time limit (Unix, main thread only).
* `check_document` only reads LaTeX formulas; plain-text maths (`v = 6 m/s t`) is
  not picked up yet. Integrals, sums, limits and derivatives written as
  `\frac{d}{dx}` inside a document are skipped.
* A new equation that does not follow from earlier ones is not judged, so an
  error in setting up a physical law is not found (see the first point).
  `check_answer` finds such errors only through the reference.
* `check_answer` reads results, it does not understand the text. It needs a line
  `name = …` for each quantity; results only given in words are reported as
  `missing`. If an answer uses one name for several things (`\eta` in parts a and
  c), the last one is taken unless the task sets `part`. In plain text, `e` is
  Euler's number unless the task calls the elementary charge `qe`.

## How it works

1. Parse both sides safely into SymPy expressions (shared symbols, assumptions applied).
2. Try `expand`, `cancel`, `trigsimp`, `simplify` on `lhs − rhs`. Zero → `verified`.
3. Otherwise evaluate both sides at 24 random points with 30-digit precision,
   respecting assumptions. Any mismatch → `refuted` with the point as counterexample.
   All match → `likely`.

## Benchmark

`benchmark/` measures how many real mistakes of a language model in physics
exercises mathguard finds, split by error type. See [benchmark/README.md](https://github.com/C0MaE/mathguard/blob/main/benchmark/README.md).

First results ([benchmark/RESULTS.md](https://github.com/C0MaE/mathguard/blob/main/benchmark/RESULTS.md)): of 37 calculation
errors (algebra, numbers, units and the like) in the answers of three models,
mathguard located 27 at the exact step (73 %), with no false alarms on 58
correct answers. Most real errors were a wrong physical approach, which
mathguard cannot see by design.

`check_answer` was compared with hand grading on 291 final results (35 physics
exercises, answers of Claude Haiku, qwen3 8B and llama3.2 3B). It reached a
verdict for 216 of them, and 213 of these agree with the hand grading (98.6 %);
of the hand-graded correct results it recognised 156 of 182 as correct. The
other results were reported as `missing` or `inconclusive`, mostly because the
answer gave no result for that quantity or wrote it in other variables.

Those exercises come from university problem sets and cannot be published.
[`open-bench/`](https://github.com/C0MaE/mathguard/blob/main/open-bench/README.md) is a
second set of 24 physics exercises written for this repository under CC BY 4.0, with
checked reference solutions, so results on it can be reproduced and shared in full.
On it ([open-bench/RESULTS.md](https://github.com/C0MaE/mathguard/blob/main/open-bench/RESULTS.md)),
mathguard located 16 of 17 calculation errors of llama3.2 3B at the exact step, with no false
alarms on 52 correct answers of three models, and the answer grader agreed with the hand grading on
every quantity it decided (74 of 75).

## Contributing

Reports of wrong verdicts are the most welcome contribution. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Citing

If you use mathguard in research or teaching, please cite it. GitHub shows the
citation under "Cite this repository" (from [CITATION.cff](CITATION.cff)).
Releases are archived on Zenodo: [doi:10.5281/zenodo.24147172](https://doi.org/10.5281/zenodo.24147172).

## License

MIT

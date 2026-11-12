# Open benchmark: results (12 Nov 2026)

Three models solved the 24 exercises of the open benchmark without tools. Every final result
was compared with the reference solution (two independent paths, checked with SymPy). Then we
measured how many of the errors mathguard finds **without** seeing the reference.

Unlike the [main benchmark](../benchmark/RESULTS.md), everything here is public: the
[tasks](tasks/), the raw [model answers](responses/) and the hand [annotations](annotations/).
`python benchmark/bench.py --root open-bench evaluate && python benchmark/bench.py --root open-bench report`
reproduces the numbers.

## Overview

| Model | Answers fully correct | Wrong answers flagged by mathguard | False alarms on correct answers |
|---|---|---|---|
| Claude Haiku | 24/24 | – | 0/24 |
| qwen3:8b (thinking mode) | 18/24 | 0/6 | 0/18 |
| llama3.2:3b | 10/24 | 11/14 | 0/10 |

"Flagged" means at least one mathguard check on the answer was refuted (a calculation step from the
annotation, or one of the automatic checks of the final result: its unit, and whether the answer's own
formula gives the stated number). "Fully correct" means every quantity asked for matches the reference
(formula symbolically equal, number within 1 % or the rounding of the stated digits).

All six wrong answers of qwen3:8b are empty: the model spent the whole 8000-token limit thinking and
never wrote a reply, so there was nothing to check.

## Errors by type (llama3.2:3b)

Each wrong step was annotated by hand with one error type. "Localised" means mathguard refuted a check
on exactly that step.

| Error type | Expected to be detectable | Count | Localised |
|---|---|---|---|
| Wrong numeric value | yes | 14 | 13 (93 %) |
| Algebra (rearranging) | yes | 2 | 2 (100 %) |
| Sign | yes | 1 | 1 (100 %) |
| Units or dimensions | partly | 2 | 1 (50 %) |
| Wrong physical approach | no | 9 | 0 |
| Problem misunderstood | no | 1 | 0 |

Calculation errors (numbers, algebra, signs) were found at the exact step in 16 of 17 cases. A wrong
physical approach (simple instead of physical pendulum, wrong Doppler formula, energy conserved in an
inelastic collision) cannot be seen from the calculation alone, but 7 of these 9 answers were still
flagged because they also contained a calculation error. The one numeric error not found
(`ob-mech-09`) is a result line that does not match the line before it, with no calculation in between.

## Grading final answers

`check_answer` (the grader behind `mathguard answer`, the MCP tool and the Inspect scorer) was compared
with the hand grading on all 75 final quantities. It graded 53 as correct, 15 as wrong and 6 as
missing (the empty answers), all in line with the hand grading, and left one undecided. That
answer (`llama3.2:3b/ob-opt-01`) writes the image distance as `b = 1/f - 1/do = 1/30 cm` and
gives the right value only on the next line under another name (`di = 30 cm`).

Running the benchmark also showed four ways the grader misread answers; they are fixed in this release:
a Greek letter as a plain-text label (`θ = 41.8 deg`), a given symbol directly after a number
(`0.3268g` meant $0.3268\,g$, not grams), Markdown-escaped multiplication (`1.006 \* 10^(-3) T`) and
thousands separators (`38,794.8 s`).

## Setup and limits

- Prompt: the task statement plus a `RESULT` block to fill in (see `bench.py prompts`). No tools,
  one answer per task, no retries.
- Claude Haiku answered through Claude Code; qwen3:8b and llama3.2:3b ran locally with Ollama
  (temperature 0.2, at most 8000 tokens).
- 24 tasks is a small set, and for a strong model it is easy: Haiku solved all of them. Harder
  multi-step tasks are the next addition.
- Annotations were made by one person and checked against mathguard's output; where mathguard refuted
  a step that had no annotated error, the step was looked at again (four extra numeric errors were
  found that way and annotated).

# Benchmark results (7 Nov 2026)

Three models each solved the same 35 physics exercises (university first- and second-year level,
mechanics, thermodynamics, optics, electromagnetism), with no tools. Every final result was compared with a
reference solution that was derived along two independent paths and checked with SymPy.
Then we measured how many of the errors mathguard finds **without** seeing the reference.

The exercise texts, prompts, model answers and annotations stay private. This page only contains aggregate numbers.

## Overview

| Model | Answers fully correct | Wrong answers flagged by mathguard | False alarms on correct answers |
|---|---|---|---|
| Claude Haiku | 34/35 | 0/1 | 0/34 |
| qwen3:8b (thinking mode) | 24/35 | 3/11 | 0/24 |
| llama3.2:3b | 0/35 | 16/35 | – |

"Flagged" means at least one mathguard check on the answer was refuted. "Fully correct" means every quantity
asked for matches the reference (formula symbolically equal, number within 1 % or the rounding of the stated digits).

## Errors by type

Each wrong step was annotated by hand with one error type. "Localised" means mathguard refuted a check on
exactly that step.

| Error type | Expected to be detectable | Count | Localised |
|---|---|---|---|
| Algebra (rearranging) | yes | 7 | 7 (100 %) |
| Wrong numeric value | yes | 16 | 13 (81 %) |
| Units or dimensions | partly | 9 | 7 (78 %) |
| Calculus (derivative, integral) | yes | 2 | 0 |
| Missing or wrong factor | yes | 2 | 0 |
| Sign | yes | 1 | 0 |
| **All error types in reach** | | **37** | **27 (73 %)** |
| Wrong physical approach | no | 42 | out of reach |
| Misread task | no | 4 | out of reach |
| Other (e.g. endless repetition, missing result) | no | 9 | out of reach |

Haiku's only error was a wrong geometric approach (missing factor 2 from the light path), which is out of reach
by construction.

## What this shows

1. **mathguard finds most of the errors it is built for.** Of the 37 calculation errors (algebra, numbers, units
   and the like), it pins down 27 to the exact step. Algebra slips and wrong numbers are found almost always.
2. **No false alarms.** On the 58 correct answers of Haiku and qwen3, mathguard refuted no check at all.
3. **Most real errors are physics errors, not calculation errors.** 55 of the 92 errors annotated for qwen3 and llama3.2 are a wrong
   approach, a misread task or a missing result. mathguard cannot see those. Strong models make almost only this kind.
4. **mathguard needs the working.** In thinking mode, qwen3 wrote only the final result block for 22 of 35 answers.
   Then the only checks left are the unit of the result formula and whether the formula and the number agree.
   Both calculus errors were missed this way.
5. **Small models fail differently.** llama3.2:3b got no exercise fully right, repeated itself endlessly in 5
   answers and often mixed units. All 9 answers with a unit error were flagged.

## Limits

- The checks were transcribed by hand from the answers, by someone who knew the reference. This can inflate the
  hit rate. Automatic extraction (LaTeX/Markdown import, `mathguard doc`) is the next step to remove this bias.
- 35 exercises and three models are a small sample. The localisation rates above have wide uncertainty
  (for 27 of 37, roughly 56 % to 86 % at 95 %).
- Answers that are numerically within 1 % count as correct, even when the formula or arithmetic had a small slip.

## Next steps

- Ask for LaTeX formulas in the prompt and evaluate the answers with `check_document`, so the checks are no
  longer transcribed by hand.
- Inject known errors (sign, factor 2, units, wrong derivative) into correct solutions to get a larger,
  controlled sample per error type.

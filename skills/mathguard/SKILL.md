---
name: mathguard
description: Verify mathematical claims with a computer algebra system before presenting them. Use when writing or reviewing a calculation, derivation, worked solution, physics exercise or formula; when checking identities, derivatives, integrals, limits, equation solutions, numerical values or physical units; when grading answers (from students or language models) against a reference solution; or when the user asks to double-check, verify or find the error in some maths.
license: MIT
compatibility: Needs Python 3.10+ and either the mathguard MCP server or the mathguard command (uv/uvx recommended). See references/setup.md.
metadata:
  homepage: https://github.com/C0MaE/mathguard
  version: "0.3.0"
---

# mathguard: check the maths before you state it

Language models set up calculations well and carry them out unreliably: a lost
factor of 2, a sign, a wrong derivative, a unit that does not add up. mathguard
checks such claims with SymPy and Pint and answers with an honest status and,
when a claim is wrong, a concrete counterexample.

## When to use it

Use mathguard whenever correctness of maths matters and the claim is more than
mental arithmetic:

- **Before presenting your own calculation**: algebra, a derivation, calculus,
  solving an equation, a physics result with units, a final number.
- **When reviewing someone else's maths**: a homework solution, a paper excerpt,
  an LLM answer, a formula in code or docs. Find the first wrong step.
- **When grading answers against a reference**: exercises, exams, model
  evaluations.
- **When the user asks** to verify, double-check, or find the mistake.

Skip it for trivial arithmetic, purely conceptual questions, and proofs that
are not calculations (mathguard checks computations, not arguments).

## Tools

If the `mathguard` MCP server is connected, use its tools. Otherwise use the
command line (see "Without the MCP server" below). If neither is available,
tell the user and point them to `references/setup.md`.

| Task | MCP tool | CLI |
|---|---|---|
| Whole worked solution in Markdown/LaTeX | `check_solution` | `mathguard doc file.md` |
| Final results against a reference | `check_answer` | `mathguard answer file.md --ref "v = ..."` |
| Derivation step by step | `check_derivation` | `mathguard chain "a" "b" "c"` |
| One identity `lhs = rhs` | `check_identity` | `mathguard equal "lhs" "rhs"` |
| Dimensions of an equation | `check_units` | `mathguard dims "E = m c^2" --unit E=J ...` |
| Several checks at once, or derivative, integral, limit, solutions, value | `verify_math` | `mathguard check checks.json` |

The JSON format of `verify_math` (all check types and fields) is in
`references/checks.md`. Read it before using derivative, integral, limit,
solutions or value checks.

## Workflow

1. **Write the claim in checkable form.** Prefer one Markdown answer with LaTeX
   formulas (`$...$`, `$$...$$`, `align`) and check it as a whole with
   `check_solution`. For a single step or identity use the smaller tools.
2. **Pass units for physics.** Give `units` such as `{"v0": "m/s", "g": "m/s^2",
   "m": "kg"}` so every step is also checked for dimensions.
3. **Pass assumptions** when the maths relies on them, e.g.
   `{"x": "positive"}` for `sqrt(x^2) = x`. `check_solution` and
   `check_answer` already treat variables as positive; the other tools treat
   them as real.
4. **Read the status of every result**, not just the overall one:

   | Status | What to do |
   |---|---|
   | `verified` | Confirmed by computer algebra. Present it. |
   | `likely` | Many random numerical tests agree, no symbolic proof. Present it, and say "numerically checked" if it matters. |
   | `refuted` | Wrong. Use the counterexample and message to find the mistake, fix it, check again. Never present a refuted step. |
   | `inconclusive` | Not decided. Do not claim it was verified. Simplify, split it into smaller steps or check it another way. |
   | `error` | Input could not be parsed. Fix the syntax (see below) and retry. |

5. **Loop until clean**, then answer. When you report to the user, say what was
   checked and how ("all steps verified with mathguard", "step 3 was wrong:
   counterexample x = 0.6 ...").

## Reading the reports

- `check_solution` returns `status`, `first_error_line` and a list of `steps`
  with `line`, `latex`, `status` and `results` (each with `message` and maybe
  `counterexample`). Fix the step at `first_error_line` first; later errors
  often follow from it.
- A step marked **"new equation"** (`skipped`) is a physical law or a
  setup equation that does not follow from earlier lines. mathguard does not
  judge these. Check them yourself: an error in setting up the physics is not
  found by mathguard.
- An equation that **"contradicts line N"** gives a different value for a
  variable than an earlier line. One of the two lines is wrong.
- `check_answer` returns `status` (`correct`, `wrong`, `missing`,
  `inconclusive`), `score` and per quantity the `grade`, what was `extracted`
  from the answer (line, formula, value, unit) and the comparison `results`.
  `missing` means no line `name = ...` was found for that quantity, not that
  the answer is wrong.

## Expression syntax (plain-text inputs)

- Powers `x^2` or `x**2`; implicit multiplication `2x`, `m c^2`, `x(y+1)`.
- **Multi-letter names are one variable**: `v0`, `dt`, `omega`. Write products
  of letters with a space or `*`: `2 a b`, not `2ab`.
- Functions only with parentheses: `sin(x)`, `exp(x)`, `ln(x)`, `sqrt(x)`,
  `Abs(x)`. Constants `pi`, `e` (Euler), `oo`.
- `E` and `I` are ordinary variables (energy, current), not Euler's number or
  the imaginary unit.
- In LaTeX (`check_solution`, `check_answer`, or `"latex": true`), adjacent
  letters are products (`mv^2` is `m*v^2`), `v_0` is the variable `v0`,
  `9{,}81` is `9.81`, `60^\circ` is `pi/3`.

## Without the MCP server

Run the CLI with `uvx`, which needs no prior install:

```bash
uvx mathguard equal "sin(x)^2 + cos(x)^2" "1"
uvx mathguard --json doc solution.md --unit v0=m/s --unit g=m/s^2
```

If `mathguard` is installed (`pip install mathguard`),
call it directly. Put `--json` before the subcommand for machine-readable
output. Exit codes: `0` all good, `1` something refuted or wrong, `2`
inconclusive, missing or input error. `mathguard prompt` prints the full JSON
check format.

## Limits

- It checks computations, not models: a correct calculation with the wrong
  physical law is still wrong.
- `likely` is strong numerical evidence, not a proof. For formal proofs use a
  proof assistant such as Lean.
- `check_solution` reads LaTeX formulas only. Integrals, sums and limits inside
  a document are skipped; check those with `verify_math`.
- Inputs go through SymPy's parser behind a whitelist. Do not expose the
  server to untrusted users without a sandbox.

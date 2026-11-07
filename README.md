# mathguard

**Verify mathematical claims — especially the ones language models make.**

LLMs are good at setting up calculations and surprisingly bad at carrying them
out reliably. `mathguard` is a small verification layer: the model (or you)
states each claim as a structured check, and a computer algebra system decides
whether it holds. Wrong claims come back with a concrete counterexample, so the
mistake can be found and fixed.

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
pip install git+https://github.com/C0MaE/mathguard
# with the MCP server for AI assistants:
pip install "mathguard[mcp] @ git+https://github.com/C0MaE/mathguard"
```

For development:

```bash
git clone https://github.com/C0MaE/mathguard && cd mathguard
pip install -e ".[dev,mcp]"
pytest
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
mathguard prompt                      # print the LLM instructions
```

Exit codes: `0` all good, `1` something was refuted, `2` inconclusive or input error —
so it can be used in CI to check worked solutions.

### MCP server (Claude Desktop, Claude Code, …)

```bash
pip install "mathguard[mcp]"
```

Register `mathguard-mcp` as a stdio server in your client. Example config:

```json
{
  "mcpServers": {
    "mathguard": { "command": "mathguard-mcp" }
  }
}
```

The server exposes `check_solution` (a whole Markdown/LaTeX answer),
`verify_math`, `check_identity`, `check_derivation` and `check_units`, plus the
LLM instructions as server instructions.

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

## How it works

1. Parse both sides safely into SymPy expressions (shared symbols, assumptions applied).
2. Try `expand`, `cancel`, `trigsimp`, `simplify` on `lhs − rhs`. Zero → `verified`.
3. Otherwise evaluate both sides at 24 random points with 30-digit precision,
   respecting assumptions. Any mismatch → `refuted` with the point as counterexample.
   All match → `likely`.

## Benchmark

`benchmark/` measures how many real mistakes of a language model in physics
exercises mathguard finds, split by error type. See [benchmark/README.md](benchmark/README.md).

## License

MIT

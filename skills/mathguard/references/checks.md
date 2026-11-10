# mathguard check reference

`verify_math` (MCP), `mathguard check file.json` (CLI) and `mathguard.verify()`
(Python) take one check object, a list of them, or `{"checks": [...]}`. Every
check has a `"check"` field and may have an `"id"` that is copied into its
results. Fields marked *optional* can be left out.

`assumptions` (optional everywhere it appears) maps variables to `positive`,
`negative`, `nonnegative`, `nonpositive`, `integer`, `nonzero` or `complex`.
Without it, variables are real.

## Algebra

```json
{"check": "equal", "lhs": "(a+b)^2", "rhs": "a^2 + 2 a b + b^2"}
{"check": "equal", "lhs": "\\frac{1}{2} m v_0^2", "rhs": "\\frac{m v_0^2}{2}", "latex": true}
{"check": "chain", "steps": ["(x+1)^2 - (x-1)^2", "x^2 + 2x + 1 - (x^2 - 2x + 1)", "4x"]}
```

`chain` checks every consecutive pair and reports the first wrong step.
`latex: true` (optional) reads `lhs`/`rhs`/`steps` as LaTeX, so all of them
must then be written in LaTeX.

## Calculus

```json
{"check": "derivative", "function": "x^2 sin(x)", "claimed": "2x sin(x) + x^2 cos(x)", "variable": "x"}
{"check": "derivative", "function": "x^4", "claimed": "12 x^2", "variable": "x", "order": 2}
{"check": "antiderivative", "integrand": "x exp(x)", "claimed": "(x-1) exp(x)", "variable": "x"}
{"check": "definite_integral", "integrand": "exp(-x^2)", "variable": "x", "lower": "-oo", "upper": "oo", "claimed": "sqrt(pi)"}
{"check": "limit", "expression": "sin(x)/x", "variable": "x", "point": "0", "claimed": "1"}
```

- `variable` defaults to `x` (not for `limit`, where it is required).
- `antiderivative` ignores the constant of integration.
- `definite_integral` has optional `rel_tol` (default `1e-8`); with free
  parameters it is checked symbolically.
- `limit` has optional `direction`: `"+"`, `"-"` or `"+-"` (default).

## Equations and numbers

```json
{"check": "solutions", "equation": "x^2 - 5x + 6 = 0", "variable": "x", "claimed": ["2", "3"]}
{"check": "value", "expression": "sqrt(2) pi", "claimed": 4.44288, "rel_tol": 1e-5}
```

- `solutions` checks each claimed solution and, unless `"complete": false`,
  that no real solution is missing.
- `value` has `rel_tol` (default `1e-9`) and `abs_tol` (default `0`). Set
  `rel_tol` to match the digits that were written.

## Units

```json
{"check": "dimensions", "equation": "E = m c^2", "units": {"E": "J", "m": "kg", "c": "m/s"}}
{"check": "dimensions", "expression": "1/2 m v^2", "expected": "J", "units": {"m": "kg", "v": "m/s"}}
```

Units are Pint names: `m`, `s`, `kg`, `N`, `J`, `W`, `V`, `A`, `C`, `F`,
`ohm`, `T`, `Pa`, `m/s^2`, `speed_of_light`, ... Instead of `equation` you can
give `lhs` and `rhs`, or `expression` with `expected`.

## Whole texts

```json
{"check": "document", "text": "<Markdown answer with $...$ LaTeX>", "units": {"v0": "m/s", "g": "m/s^2"}}
{"check": "answer", "answer": "<finished answer>", "reference": {"v": "sqrt(10 g h / 7)"}, "given": {"h": "1.2 m", "g": "9.81 m/s^2"}}
```

- `document` (same as the MCP tool `check_solution`): every formula chain is
  checked; variables count as positive unless `"positive": false`.
- `answer` (same as the MCP tool `check_answer`): `reference` maps each wanted
  quantity to a formula (`"sqrt(2 g h)"`), a value with unit (`"4.1 m/s"`) or
  an object with `formula`, `value`, `unit`, `rel_tol`, `aliases` (other names
  the answer may use) and `part` (only look inside part `b)` etc.). `given`
  holds known values so formulas can be turned into numbers, `units` the units
  of other variables, `rel_tol` the tolerance (default `0.01`). Numbers count as
  correct within the tolerance or the rounding of the written digits.

## Result shape

```json
{
  "status": "refuted",
  "ok": false,
  "results": [
    {"check": "equal", "status": "refuted",
     "message": "(a + b)**2 = a**2 + b**2 is false",
     "method": "numerical counterexample",
     "counterexample": {"a": "0.6067920837", "b": "0.0531411310", "lhs": "...", "rhs": "..."}}
  ]
}
```

The overall `status` is the worst single status. `ok` is true only when every
result is `verified` or `likely`.

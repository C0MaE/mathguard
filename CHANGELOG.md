# Changelog

## 0.2.0

* New: `check_document` / `mathguard doc` checks a whole Markdown/LaTeX solution
  step by step, with line numbers and the first error highlighted.
* New: LaTeX input (`parse_latex`, `latex_to_expr`, `"latex": true` in JSON checks).
* New: equations are compared with earlier ones (follows / contradicts / new).
* New: numbers with units are recomputed with the precision that was written.
* New: dimension check for every step when units are given.
* New: MCP tool `check_solution`, JSON check `document`.
* Fix: `check_solutions` respects sign assumptions of the solution variable.
* Benchmark: `benchmark/bench.py` with reference solutions, annotations, error types and report;
  `benchmark/run_ollama.py` for local models.

## 0.1.0

* First version: identities, derivation chains, calculus checks, solutions,
  values, limits, dimensional analysis, CLI, JSON API, MCP server.

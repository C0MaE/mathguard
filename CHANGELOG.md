# Changelog

## 0.3.0

* New: `check_answer` grades the final results of an answer against a reference:
  finds `name = …` results in plain text, Markdown and LaTeX (boxed results and
  "Result" blocks first), compares formulas symbolically and numbers with unit
  conversion and a rounding-aware tolerance. Answers may use their own earlier
  results or insert given numbers.
* New: task files (YAML/JSON) with `reference`, `given`, `units`; `grade`, `load_task`.
* New: `mathguard answer` and `mathguard grade` (single files or directories).
* New: MCP tool `check_answer`, JSON check `answer`.
* Example tasks and answers in `examples/grading/`.
* New: Agent Skill in `skills/mathguard/` (SKILL.md, JSON check reference,
  setup for Claude Code, Cursor, VS Code/Copilot, Codex and Claude Desktop).
  Runs the MCP server or the command line through `uvx`, no manual install.
* Benchmark: first results in `benchmark/RESULTS.md` (aggregate numbers only).
* Packaging: published on PyPI (`pip install mathguard`); PyYAML is now a
  regular dependency, so YAML task files work after a plain install.

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

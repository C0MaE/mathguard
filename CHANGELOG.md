# Changelog

## Unreleased

* Fix: the command line no longer fails on consoles that cannot print ✔/✘
  (e.g. a redirected Windows console with cp1252); it writes UTF-8 there.
* The package is marked as typed (`py.typed`), with classifiers for the
  supported Python versions.
* CI runs on Linux, macOS and Windows with Python 3.10 to 3.13, checks the code
  with Ruff and builds and installs the wheel.
* A demo GIF in the README.
* Issue templates (wrong verdict, bug, feature), a pull request template and
  `CONTRIBUTING.md`.

## 0.3.1

* New: `mathguard mcp` starts the MCP server (same as `mathguard-mcp`), so
  `uvx mathguard mcp` runs it without extra options.
* The MCP SDK is now a regular dependency; `mathguard[mcp]` still works.
* Listed in the MCP Registry as `io.github.C0MaE/mathguard` (`server.json`),
  published automatically with each release.

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

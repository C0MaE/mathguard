# Changelog

## Unreleased

* Open benchmark results (`open-bench/RESULTS.md`) with all model answers and
  annotations: Claude Haiku, qwen3:8b and llama3.2:3b.
* Fix: the answer grader now reads Greek letters as plain-text labels (`θ = 41.8 deg`),
  a given symbol right after a number (`0.3268g`), Markdown-escaped `\*` and
  thousands separators before a decimal point (`38,794.8 s`); it no longer crashes
  when a result is written as a given quantity (`Wel = U = 4.95 J`).
* Inspect AI scorer: `mathguard.inspect_scorer.mathguard_scorer()` grades final
  answers in Inspect evaluations; `inspect eval mathguard/open_bench` runs the
  open benchmark, whose task files now ship with the package. Extra `inspect`.
* Open benchmark: 24 physics exercises written for this repository, licensed
  CC BY 4.0, with checked two-path reference solutions (`open-bench/`).
  `bench.py --root open-bench ...` runs the benchmark tools on it.
* Zenodo DOI (10.5281/zenodo.24147172, all versions) in the README and `CITATION.cff`.

## 0.3.3

* `CITATION.cff` and `.zenodo.json`, so the repository can be cited and releases
  can be archived on Zenodo.
* Fix: the command line no longer fails on consoles that cannot print ✔/✘
  (e.g. a redirected Windows console with cp1252); it writes UTF-8 there.
* The package is marked as typed (`py.typed`), with classifiers for the
  supported Python versions.
* CI runs on Linux, macOS and Windows with Python 3.10 to 3.13, checks the code
  with Ruff and builds and installs the wheel.
* A demo GIF in the README.
* Issue templates (wrong verdict, bug, feature), a pull request template and
  `CONTRIBUTING.md`.

## 0.3.2

* Package metadata and license list the author as C0MaE.

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

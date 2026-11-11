# Contributing to mathguard

Thanks for helping. Reports of wrong verdicts are the most valuable contribution:
mathguard is only useful if `verified` and `correct` can be trusted.

## Reporting a wrong verdict

Open an issue with the "Wrong verdict" template. Include the smallest input that
shows the problem, what mathguard said (`mathguard --json …` output is best) and
why it is wrong. A counterexample is ideal.

## Development setup

```bash
git clone https://github.com/C0MaE/mathguard && cd mathguard
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check src tests
```

CI runs the tests on Linux, macOS and Windows with Python 3.10 to 3.13.

## Guidelines

* **Honest statuses first.** When a check cannot decide, return `inconclusive`
  (or `likely` for numerical evidence), never `verified`. A false `verified` is a
  serious bug; a false `inconclusive` is a missing feature.
* **Every fix gets a test.** A wrong verdict that was fixed gets a regression
  test with the input from the issue.
* **Keep the parser safe.** Inputs come from language models and web pages. Do
  not widen the character whitelist or the allowed names without a test in
  `tests/test_api_and_safety.py`.
* **User-visible changes** go into `CHANGELOG.md` under "Unreleased".
* Code, docs and commit messages are in English.

## Benchmark

`benchmark/` contains the tools and two demo tasks. The real exercise texts,
model answers and annotations are not public, so the published results are
aggregate numbers only. Please do not add exercise texts you are not allowed to
share.

## Releases

Maintainers publish a release by creating a GitHub release `vX.Y.Z`; the
`publish` workflow uploads it to PyPI and updates the MCP Registry entry.

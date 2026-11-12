---
title: mathguard
emoji: ✔️
colorFrom: indigo
colorTo: green
sdk: static
app_file: index.html
pinned: false
license: mit
short_description: Verify the maths in LLM answers with SymPy and Pint
---

# mathguard demo

Grade an answer against a reference result (formulas symbolically, numbers with
unit conversion and rounding) or check a worked solution step by step.
Deterministic, no LLM involved. The page loads Python in the browser with
[Pyodide](https://pyodide.org), so it needs no server.

Source and docs: https://github.com/C0MaE/mathguard

To deploy, create a Hugging Face Space with the *Static* SDK and upload
`index.html` and this `README.md` (its header configures the Space).

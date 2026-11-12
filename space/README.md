---
title: mathguard
emoji: ✔️
colorFrom: indigo
colorTo: green
sdk: gradio
sdk_version: 6.31.0
app_file: app.py
pinned: false
license: mit
short_description: Verify the maths in LLM answers with SymPy and Pint
---

# mathguard demo

Grade an answer against a reference result (formulas symbolically, numbers with
unit conversion and rounding) or check a worked solution step by step.
Deterministic, no LLM involved.

Source and docs: https://github.com/C0MaE/mathguard

To deploy, create a Gradio Space on Hugging Face and upload `app.py`,
`requirements.txt` and this `README.md` (its header configures the Space).

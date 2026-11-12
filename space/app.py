"""mathguard demo: grade an answer against a reference, or check a worked solution step by step."""
from __future__ import annotations

import gradio as gr

import mathguard as mg

ROLLING_ANSWER = r"""Energy conservation including the rotation, with $I = \tfrac{2}{5} m r^2$ and $\omega = v/r$:

$$ m g h = \tfrac12 m v^2 + \tfrac12 I \omega^2 = \tfrac12 m v^2 + \tfrac15 m v^2 = \tfrac{7}{10} m v^2 $$

Solving for the speed:

$$ v^2 = \tfrac{7}{10} g h \quad\Rightarrow\quad v = \sqrt{\tfrac{7 g h}{10}} $$

With numbers: $v = \sqrt{0.7 \cdot 9.81 \cdot 1.2}\,\mathrm{m/s} \approx 2.87\,\mathrm{m/s}$.

The time follows from the mean speed: $t = \frac{2L}{v} \approx 2.09\,\mathrm{s}$.
"""

ROLLING_CORRECT = """Energy conservation with the rotational energy of the sphere (I = 2/5 m r^2):

m g h = 1/2 m v^2 + 1/2 I ω^2 = 7/10 m v^2, so v = √(10 g h / 7).

The speed grows linearly along the slope, so the mean speed is v/2 and
T = 2 L / v.

Result: v ≈ 14.8 km/h, T = 1.46 s.
"""

FALL_ANSWER = """Energy conservation: m g h = 1/2 m v^2, so
v = sqrt(g h) = 3.43 m/s
"""

DOC_EXAMPLE = r"""We simplify the expression step by step:

$$ (x+1)^2 - (x-1)^2 = x^2 + 2x + 1 - (x^2 - 2x + 1) = 4x + 2 $$
"""


def _pairs(text: str) -> dict[str, str]:
    """Lines like `h = 1.2 m` or `h: 1.2 m` -> {"h": "1.2 m"}."""
    out = {}
    for line in (text or "").splitlines():
        line = line.split("#", 1)[0].strip().rstrip(",")
        if not line:
            continue
        for sep in ("=", ":"):
            if sep in line:
                key, value = line.split(sep, 1)
                out[key.strip()] = value.strip()
                break
        else:
            raise gr.Error(f"Cannot read '{line}': write one 'name = value' per line.")
    return out


def grade_answer(answer: str, reference: str, given: str, units: str, rel_tol: float) -> str:
    if not answer.strip() or not reference.strip():
        raise gr.Error("Please enter an answer and a reference.")
    try:
        rep = mg.check_answer(answer, reference, given=_pairs(given) or None,
                              units=_pairs(units) or None, rel_tol=rel_tol / 100)
    except Exception as exc:  # show parse problems instead of a stack trace
        raise gr.Error(f"{type(exc).__name__}: {exc}") from exc
    return rep.to_markdown()


def check_solution(text: str, units: str) -> str:
    if not text.strip():
        raise gr.Error("Please paste a worked solution.")
    try:
        rep = mg.check_document(text, units=_pairs(units) or None)
    except Exception as exc:
        raise gr.Error(f"{type(exc).__name__}: {exc}") from exc
    return rep.to_markdown()


INTRO = f"""# mathguard {mg.__version__ if hasattr(mg, '__version__') else ''}
Verify the maths in an answer, deterministically with SymPy and Pint, no LLM involved.
Formulas are compared symbolically, numbers with unit conversion and rounding.
[GitHub](https://github.com/C0MaE/mathguard) · `pip install mathguard` ·
[open benchmark](https://github.com/C0MaE/mathguard/tree/main/open-bench)
"""

with gr.Blocks(title="mathguard") as demo:
    gr.Markdown(INTRO)
    with gr.Tab("Grade an answer"):
        with gr.Row():
            with gr.Column():
                answer = gr.Textbox(label="Answer (plain text, Markdown or LaTeX)", lines=12)
                reference = gr.Textbox(label="Reference (one result per line)", lines=2,
                                       placeholder="v = sqrt(2 g h)")
                with gr.Row():
                    given = gr.Textbox(label="Known values", lines=3, placeholder="h = 1.2 m\ng = 9.81 m/s^2")
                    units = gr.Textbox(label="Units of symbols without value", lines=3,
                                       placeholder="m = kg")
                rel_tol = gr.Slider(0.1, 10, value=1, step=0.1, label="Minimum tolerance for numbers (%)")
                btn = gr.Button("Grade", variant="primary")
            out = gr.Markdown()
        btn.click(grade_answer, [answer, reference, given, units, rel_tol], out)
        gr.Examples(
            examples=[
                [ROLLING_ANSWER, "v = sqrt(10 g h / 7)\nt = 2 L / sqrt(10 g h / 7)",
                 "h = 1.2 m\nL = 3 m\ng = 9.81 m/s^2", "m = kg\nr = m", 1],
                [ROLLING_CORRECT, "v = sqrt(10 g h / 7)\nT = 2 L / sqrt(10 g h / 7)",
                 "h = 1.2 m\nL = 3 m\ng = 9.81 m/s^2", "m = kg\nr = m", 1],
                [FALL_ANSWER, "v = sqrt(2 g h)", "h = 1.2 m\ng = 9.81 m/s^2", "m = kg", 1],
            ],
            inputs=[answer, reference, given, units, rel_tol],
            label="Examples (rolling sphere: wrong, then right; free fall: wrong)",
        )
    with gr.Tab("Check a worked solution"):
        with gr.Row():
            with gr.Column():
                doc = gr.Textbox(label="Worked solution (Markdown with LaTeX)", lines=14)
                doc_units = gr.Textbox(label="Units of symbols (optional)", lines=2, placeholder="m = kg")
                doc_btn = gr.Button("Check every step", variant="primary")
            doc_out = gr.Markdown()
        doc_btn.click(check_solution, [doc, doc_units], doc_out)
        gr.Examples(examples=[[DOC_EXAMPLE, ""], [ROLLING_ANSWER, "m = kg\nr = m"]],
                    inputs=[doc, doc_units])

if __name__ == "__main__":
    demo.launch()

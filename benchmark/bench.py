"""Benchmark: how many real AI mistakes in physics exercises does mathguard find?

Run from the repository root:

    python benchmark/bench.py validate            # check tasks and reference solutions
    python benchmark/bench.py prompts             # generate prompts for the model
    python benchmark/bench.py evaluate            # grade answers, run mathguard
    python benchmark/bench.py report              # results by error type
    python benchmark/bench.py list                # overview of the tasks as a Markdown table
    python benchmark/bench.py new <id>            # template for a new task
    python benchmark/bench.py annotate <model> <id>   # template for an annotation

Demo tasks (``demo: true``) only count with ``--demo``.
Requires ``pyyaml`` (``pip install -e ".[bench]"``).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import sympy as sp
import yaml

import mathguard as mg
from mathguard.cli import _utf8_output
from mathguard.api import verify
from mathguard.parsing import ParseError, parse
from mathguard.units import _ureg
from mathguard.verdict import Status

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "tasks"
RESPONSES = ROOT / "responses"
ANNOTATIONS = ROOT / "annotations"
RESULTS = ROOT / "results"
ERROR_TYPES = yaml.safe_load((ROOT / "error_types.yaml").read_text(encoding="utf-8"))

DEFAULT_NUM_TOL = 0.01  # model answers round; within 1 % counts as correct

PROMPT_TEMPLATE = """\
Solve the following physics problem. Show your work step by step.

{statement}
End your answer with exactly this block (one line per requested quantity,
formula in the symbols of the problem, numerical value in the given unit):

RESULT
{result}
"""


# --------------------------------------------------------------------------- I/O

def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_tasks(include_demo: bool, only: str | None = None) -> dict[str, dict[str, Any]]:
    tasks = {}
    for path in sorted(TASKS.glob("*.yaml")):
        t = load_yaml(path)
        t.setdefault("id", path.stem)
        if t["id"] != path.stem:
            sys.exit(f"{path.name}: id '{t['id']}' does not match the file name")
        if only and t["id"] != only:
            continue
        if t.get("demo") and not include_demo and not only:
            continue
        tasks[t["id"]] = t
    return tasks


# -------------------------------------------------------------------------- helpers

def unit_table(task: dict[str, Any]) -> dict[str, str]:
    """Unit of every variable for the dimensional analysis."""
    ureg = _ureg()
    units = {k: str(ureg.Quantity(v).units) for k, v in (task.get("given") or {}).items()}
    units.update(task.get("auxiliary") or {})
    return units


def evaluate_formula(formula: str, task: dict[str, Any], unit: str) -> tuple[float | None, str]:
    """Insert the given values into a formula, result in ``unit``."""
    ureg = _ureg()
    try:
        expr = parse(formula, task.get("assumptions"))
    except ParseError as exc:
        return None, f"formula not readable: {exc}"
    values = {}
    for name, q in (task.get("given") or {}).items():
        values[name] = ureg.Quantity(q).to_base_units().magnitude
    subs = {s: values[s.name] for s in expr.free_symbols if s.name in values}
    rest = sorted(s.name for s in expr.free_symbols if s.name not in values)
    if rest:
        return None, f"variables without a value: {', '.join(rest)}"
    try:
        si_value = complex(sp.N(expr.subs(subs), 30))
    except (TypeError, ValueError) as exc:
        return None, f"cannot be evaluated: {exc}"
    if abs(si_value.imag) > 1e-12 * max(1.0, abs(si_value.real)):
        return None, f"value is complex: {si_value}"
    base = ureg.Quantity(1.0, unit).to_base_units().units
    return float(ureg.Quantity(si_value.real, base).to(unit).magnitude), ""


def is_pure_number(formula: str, task: dict[str, Any]) -> bool:
    """Formulas without variables are numbers in SI base units (no dimension check)."""
    try:
        return not parse(formula, task.get("assumptions")).free_symbols
    except ParseError:
        return False


def rounding_tol(given: Any) -> float:
    """Half a unit of the last given digit, relative to the value ("1.7e-5" -> 0.03)."""
    text = str(given).strip().lower().replace(",", ".")
    mant, _, _ = text.partition("e")
    digits = mant.lstrip("+-").replace(".", "").lstrip("0")
    try:
        value = float(text)
    except ValueError:
        return 0.0
    if not digits or value == 0:
        return 0.0
    decimals = len(mant.partition(".")[2])
    exp = int(text.partition("e")[2] or 0)
    return 0.5 * 10 ** (exp - decimals) / abs(value)


def rel_close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-300)


def status_of(verdict) -> str:
    return verdict.status.value


# ------------------------------------------------------------------------ validate

def validate_task(t: dict[str, Any]) -> list[tuple[str, str]]:
    """Return a list of (level, message); level is ok, warning or error."""
    out: list[tuple[str, str]] = []
    for key in ("statement", "wanted", "reference"):
        if not t.get(key):
            out.append(("error", f"field '{key}' is missing"))
    if any(s == "error" for s, _ in out):
        return out
    ref = t["reference"]
    assume = t.get("assumptions")
    units = unit_table(t)
    if ref.get("status") == "disputed":
        out.append(("warning", "reference is marked as disputed, needs a decision"))
    elif ref.get("status") != "checked":
        out.append(("warning", f"reference status '{ref.get('status')}', not checked yet"))

    for name, spec in t["wanted"].items():
        r = ref.get(name)
        if not r:
            out.append(("error", f"{name}: no reference solution"))
            continue
        a, b = (r.get("path_a") or {}), (r.get("path_b") or {})
        if not a.get("formula"):
            out.append(("error", f"{name}: path_a.formula is missing"))
            continue
        if not b.get("formula"):
            out.append(("warning", f"{name}: second solution path (path_b) is missing"))
        elif r.get("numeric_match_only"):
            # paths that only agree in the physical range (e.g. square root of v^2)
            va, ma = evaluate_formula(a["formula"], t, spec["unit"])
            vb, mb = evaluate_formula(b["formula"], t, spec["unit"])
            ok = va is not None and vb is not None and rel_close(va, vb, 1e-9)
            out.append(("ok" if ok else "error", f"{name}: path A = path B at the given "
                        f"values [{'verified' if ok else 'refuted'}] {ma or ''}{mb or ''}"))
        else:
            v = mg.check_equal(a["formula"], b["formula"], assume)
            level = "ok" if v.ok else "error"
            out.append((level, f"{name}: path A = path B [{status_of(v)}]"))
        for label, way in (("A", a), ("B", b)):
            steps = way.get("steps")
            if steps:
                rep = mg.check_chain(steps, assume)
                out.append(("ok" if rep.ok else "error",
                            f"{name}: steps in path {label} [{rep.status.value}]"))
                last = mg.check_equal(steps[-1], way["formula"], assume)
                if not last.ok:
                    out.append(("error", f"{name}: last step in path {label} ≠ formula"))
        for i, spec_check in enumerate(r.get("extra_checks") or [], 1):
            rep = verify(spec_check)
            out.append(("ok" if rep.ok else "error",
                        f"{name}: extra check {i} ({spec_check.get('check')}) "
                        f"[{rep.status.value}]"))
        if is_pure_number(a["formula"], t):
            out.append(("ok", f"{name}: pure number in SI, no unit check"))
        else:
            dims = mg.check_dimensions(units, expression=a["formula"], expected=spec["unit"])
            out.append(("ok" if dims.ok else "error", f"{name}: unit {spec['unit']} "
                        f"[{status_of(dims)}]"))
        if r.get("value") is not None:
            val, msg = evaluate_formula(a["formula"], t, spec["unit"])
            if val is None:
                out.append(("error", f"{name}: {msg}"))
            else:
                tol = float(r.get("rel_tol", 1e-3))
                ok = rel_close(val, float(r["value"]), tol)
                out.append(("ok" if ok else "error",
                            f"{name}: value {r['value']} (formula gives {val:.6g})"))
        elif not spec.get("symbolic_only"):
            out.append(("warning", f"{name}: no value in the reference"))
    return out


def cmd_validate(args) -> int:
    tasks = load_tasks(include_demo=True, only=args.task)
    if not tasks:
        print("No tasks found.")
        return 1
    n_err = 0
    icon = {"ok": "✔", "warning": "?", "error": "✘"}
    for tid, t in tasks.items():
        print(f"\n{tid}{'  (demo)' if t.get('demo') else ''}")
        for level, msg in validate_task(t):
            n_err += level == "error"
            print(f"  {icon[level]} {msg}")
    print(f"\n{len(tasks)} task(s), {n_err} error(s)")
    return 1 if n_err else 0


# ------------------------------------------------------------------------- prompts

def build_prompt(t: dict[str, Any]) -> str:
    lines = []
    for name, spec in t["wanted"].items():
        label = f"{name} [{spec['description']}]" if spec.get("description") else name
        if spec.get("symbolic_only"):
            lines.append(f"{label} = <formula>")
        else:
            lines.append(f"{label} = <formula> = <value> {spec['unit']}")
    return PROMPT_TEMPLATE.format(statement=t["statement"].rstrip() + "\n", result="\n".join(lines))


def cmd_prompts(args) -> int:
    tasks = load_tasks(args.demo, args.task)
    target = RESULTS / "prompts"
    target.mkdir(parents=True, exist_ok=True)
    for tid, t in tasks.items():
        (target / f"{tid}.md").write_text(build_prompt(t), encoding="utf-8")
    print(f"{len(tasks)} prompt(s) in {target.relative_to(ROOT.parent)}")
    return 0


# ------------------------------------------------------------------------ evaluate

def grade(t: dict[str, Any], final: dict[str, Any], num_tol: float) -> dict[str, Any]:
    """Grade the model's final result against the reference (only used for scoring)."""
    out: dict[str, Any] = {}
    for name, spec in t["wanted"].items():
        r = t["reference"][name]
        given = (final or {}).get(name) or {}
        res: dict[str, Any] = {"formula": None, "value": None}
        if given.get("formula") and not is_pure_number(r["path_a"]["formula"], t):
            v = mg.check_equal(given["formula"], r["path_a"]["formula"], t.get("assumptions"))
            res["formula"] = v.ok if v.status in (Status.VERIFIED, Status.LIKELY,
                                                  Status.REFUTED) else None
        if given.get("value") is not None and r.get("value") is not None:
            tol = max(float(r.get("answer_tol", num_tol)), rounding_tol(given["value"]))
            res["value"] = rel_close(float(given["value"]), float(r["value"]), tol)
        known = [x for x in res.values() if x is not None]
        res["correct"] = bool(known) and all(known)
        out[name] = res
    return out


def auto_checks(t: dict[str, Any], final: dict[str, Any]) -> list[dict[str, Any]]:
    """Checks mathguard can set up by itself, without the reference solution."""
    out = []
    units = unit_table(t)
    for name, spec in t["wanted"].items():
        given = (final or {}).get(name) or {}
        if given.get("formula") and not is_pure_number(given["formula"], t):
            v = mg.check_dimensions(units, expression=given["formula"], expected=spec["unit"])
            out.append({"step": "final", "check": f"auto:units:{name}",
                        "status": status_of(v), "message": v.message})
        if given.get("formula"):
            if given.get("value") is not None:
                val, msg = evaluate_formula(given["formula"], t, spec["unit"])
                if val is None:
                    out.append({"step": "final", "check": f"auto:consistency:{name}",
                                "status": "inconclusive", "message": msg})
                else:
                    tol = max(DEFAULT_NUM_TOL, rounding_tol(given["value"]))
                    ok = rel_close(val, float(given["value"]), tol)
                    out.append({"step": "final", "check": f"auto:consistency:{name}",
                                "status": "verified" if ok else "refuted",
                                "message": f"own formula gives {val:.6g} {spec['unit']}, "
                                           f"stated {given['value']}"})
    return out


def run_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in checks or []:
        spec = {k: v for k, v in c.items() if k != "step"}
        for v in verify(spec).verdicts:
            out.append({"step": c.get("step"), "check": v.check,
                        "status": status_of(v), "message": v.message,
                        **({"counterexample": v.counterexample} if v.counterexample else {})})
    return out


def evaluate_one(t: dict[str, Any], ann: dict[str, Any], num_tol: float) -> dict[str, Any]:
    final = ann.get("final") or {}
    graded = grade(t, final, num_tol)
    verdicts = run_checks(ann.get("checks")) + auto_checks(t, final)
    refuted_steps = sorted({str(v["step"]) for v in verdicts if v["status"] == "refuted"})
    errors = ann.get("errors") or []
    korrekt = all(g["correct"] for g in graded.values())
    warnings = []
    for e in errors:
        if e.get("type") not in ERROR_TYPES:
            warnings.append(f"unknown error type '{e.get('type')}'")
    if not korrekt and not errors:
        warnings.append("final result wrong, but no error annotated")
    return {
        "task": t["id"], "demo": bool(t.get("demo")),
        "correct": korrekt, "grading": graded,
        "errors": [{**e, "located": str(e.get("step")) in refuted_steps} for e in errors],
        "flagged": bool(refuted_steps), "refuted_steps": refuted_steps,
        "checks": verdicts, "warnings": warnings,
    }


def cmd_evaluate(args) -> int:
    tasks = load_tasks(args.demo)
    models = [args.model] if args.model else sorted(p.name for p in ANNOTATIONS.iterdir()
                                                   if p.is_dir())
    RESULTS.mkdir(exist_ok=True)
    for model in models:
        rows = []
        for path in sorted((ANNOTATIONS / model).glob("*.yaml")):
            ann = load_yaml(path)
            tid = ann.get("task", path.stem)
            if tid not in tasks:
                continue
            if not (RESPONSES / model / f"{tid}.md").exists():
                print(f"  ? {model}/{tid}: raw answer missing in responses/")
            row = evaluate_one(tasks[tid], ann, args.num_tol)
            rows.append(row)
            flag = "flagged" if row["flagged"] else "not flagged"
            print(f"  {model}/{tid}: {'correct' if row['correct'] else 'wrong'}, "
                  f"mathguard {flag}" + "".join(f"\n    ! {w}" for w in row["warnings"]))
        (RESULTS / f"{model}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
        print(f"{model}: {len(rows)} answer(s) → results/{model}.json")
    return 0


# -------------------------------------------------------------------------- report

def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.0f} %)" if b else "–"


def cmd_report(args) -> int:
    lines = ["# mathguard benchmark: results", ""]
    files = sorted(RESULTS.glob("*.json"))
    if not files:
        print("No results, run 'evaluate' first.")
        return 1
    for f in files:
        rows = [r for r in json.loads(f.read_text(encoding="utf-8"))
                if args.demo or not r["demo"]]
        model = f.stem
        lines += [f"## Model: {model}", ""]
        if not rows:
            lines += ["No answers (demo tasks only with `--demo`).", ""]
            continue
        wrong = [r for r in rows if not r["correct"]]
        right = [r for r in rows if r["correct"]]
        lines += [
            "| Metric | Value |", "|---|---|",
            f"| Answers | {len(rows)} |",
            f"| Final result correct | {pct(len(right), len(rows))} |",
            f"| Wrong answers flagged by mathguard | "
            f"{pct(sum(r['flagged'] for r in wrong), len(wrong))} |",
            f"| Correct answers flagged anyway (false alarm) | "
            f"{pct(sum(r['flagged'] for r in right), len(right))} |",
            "",
            "### By error type", "",
            "| Error type | detectable | count | step located | answer flagged |",
            "|---|---|---|---|---|",
        ]
        by_type: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
        for r in rows:
            for e in r["errors"]:
                by_type[e.get("type", "other")].append((e, r))
        for art, info in ERROR_TYPES.items():
            items = by_type.get(art, [])
            if not items:
                continue
            lines.append(f"| {info['name']} | {info['detectable']} | {len(items)} | "
                         f"{pct(sum(e['located'] for e, _ in items), len(items))} | "
                         f"{pct(sum(r['flagged'] for _, r in items), len(items))} |")
        lines.append("")

        missed = [(r["task"], e) for r in rows for e in r["errors"] if not r["flagged"]]
        if missed:
            lines += ["### Errors not found", ""]
            lines += [f"- `{tid}` step {e.get('step')}: {e.get('type')}, {e.get('note', '')}"
                      for tid, e in missed]
            lines.append("")

        annotated = {(r["task"], str(e.get("step"))) for r in rows for e in r["errors"]}
        unexplained = [(r["task"], v) for r in rows for v in r["checks"]
                       if v["status"] == "refuted" and (r["task"], str(v["step"])) not in annotated]
        if unexplained:
            lines += ["### Refuted checks without an annotated error (review!)", "",
                      "Either an annotation is missing or mathguard is wrong.", ""]
            lines += [f"- `{tid}` step {v['step']}: {v['message']}" for tid, v in unexplained]
            lines.append("")

        broken = [(r["task"], v) for r in rows for v in r["checks"]
                  if v["status"] in ("error", "inconclusive")]
        if broken:
            lines += ["### Checks with error/inconclusive", ""]
            lines += [f"- `{tid}` step {v['step']} ({v['check']}): {v['message']}"
                      for tid, v in broken]
            lines.append("")

        statuses = Counter(v["status"] for r in rows for v in r["checks"])
        lines += ["### All checks by status", "",
                  ", ".join(f"{k}: {n}" for k, n in sorted(statuses.items())), ""]

    out = RESULTS / "report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"→ {out.relative_to(ROOT.parent)}")
    return 0


# --------------------------------------------------------------------------- list

def cmd_list(args) -> int:
    tasks = load_tasks(args.demo)
    lines = ["| Task | Source | Topic | wanted | Reference | Status |", "|---|---|---|---|---|---|"]
    for tid, t in tasks.items():
        q = t.get("source") or {}
        src = f"{(q.get('course') or '').split(' (')[0]} sheet {q.get('sheet')}, ex. {q.get('exercise')}"
        if q.get("part"):
            src += f" ({q['part']})"
        ref = t["reference"]
        vals = []
        for name, spec in t["wanted"].items():
            r = ref.get(name) or {}
            if r.get("value") is not None:
                vals.append(f"{name} = {float(r['value']):.5g} {spec['unit']}")
            else:
                vals.append(f"{name} = `{r.get('path_a', {}).get('formula')}`")
        status = ref.get("status", "")
        if ref.get("author_discrepancy"):
            status += " (differs from the author's own solution)"
        lines.append(f"| `{tid}` | {src} | {t.get('topic', '')} | {', '.join(t['wanted'])} | "
                     f"{'; '.join(vals)} | {status} |")
    print("\n".join(lines))
    return 0


# ---------------------------------------------------------------------- templates

NEW_TASK = """\
id: {id}
source: {{sheet: null, exercise: null, part: null}}   # e.g. sheet: 3, exercise: 2, part: b
subject: null
topic: null

statement: |
  Problem text as on the sheet, formulas in LaTeX ($...$).

given:              # variable: "value unit" (Pint notation)
  v0: "20 m/s"

auxiliary: {{}}       # variables without a value, only for units: m: "kg"
assumptions: {{v0: positive}}

wanted:
  x:
    description: null
    unit: m

reference:
  status: open      # open | checked | disputed
  checked_by: null
  x:
    path_a:
      description: null
      steps: []     # optional: derivation as a chain of equal expressions
      formula: null
    path_b:
      description: null
      formula: null
    value: null
    rel_tol: 1.0e-3
"""

NEW_ANNOTATION = """\
task: {id}
model: {model}
final:
{final}
errors: []          # e.g. - {{type: factor, step: 2, note: "..."}}  (types: error_types.yaml)
checks: []          # calculations from the answer as mathguard checks, each with a `step`
"""


def cmd_new(args) -> int:
    path = TASKS / f"{args.id}.yaml"
    if path.exists():
        sys.exit(f"{path} already exists")
    path.write_text(NEW_TASK.format(id=args.id), encoding="utf-8")
    print(f"created: {path.relative_to(ROOT.parent)}")
    return 0


def cmd_annotate(args) -> int:
    t = load_tasks(True, args.id).get(args.id)
    if t is None:
        sys.exit(f"task '{args.id}' not found")
    path = ANNOTATIONS / args.model / f"{args.id}.yaml"
    if path.exists():
        sys.exit(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    final = "\n".join(f"  {n}: {{formula: null, value: null}}" for n in t["wanted"])
    path.write_text(NEW_ANNOTATION.format(id=args.id, model=args.model, final=final),
                    encoding="utf-8")
    print(f"created: {path.relative_to(ROOT.parent)}")
    return 0


# ---------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    p = argparse.ArgumentParser(prog="bench", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("validate"); s.add_argument("--task")
    s = sub.add_parser("prompts"); s.add_argument("--task"); s.add_argument("--demo", action="store_true")
    s = sub.add_parser("evaluate"); s.add_argument("--model"); s.add_argument("--demo", action="store_true")
    s.add_argument("--num-tol", type=float, default=DEFAULT_NUM_TOL)
    s = sub.add_parser("report"); s.add_argument("--demo", action="store_true")
    s = sub.add_parser("list"); s.add_argument("--demo", action="store_true")
    s = sub.add_parser("new"); s.add_argument("id")
    s = sub.add_parser("annotate"); s.add_argument("model"); s.add_argument("id")
    args = p.parse_args(argv)
    return {"validate": cmd_validate, "prompts": cmd_prompts, "evaluate": cmd_evaluate,
            "report": cmd_report, "list": cmd_list, "new": cmd_new, "annotate": cmd_annotate}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

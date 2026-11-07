"""Command line interface.

    mathguard equal "sin(x)^2 + cos(x)^2" "1"
    mathguard equal "sqrt(x^2)" "x" --assume x=positive
    mathguard chain "(x+1)^2" "x^2 + 2x + 1"
    mathguard dims "E = m c^2" --unit E=J --unit m=kg --unit c=m/s
    mathguard check checks.json          # file with JSON checks ("-" for stdin)
    mathguard doc solution.md --unit v0=m/s   # check a whole Markdown/LaTeX solution
    mathguard answer answer.md --ref "v = sqrt(10 g h / 7)" --given h="1.2 m" --given g="9.81 m/s^2"
    mathguard grade task.yaml answer.md       # grade answers against a task file
    mathguard grade tasks/ answers/           # many tasks, answers matched by file name
    mathguard prompt                     # print instructions for an LLM

Exit code: 0 if everything is verified/likely (or correct), 1 if something was
refuted (or wrong), 2 for inconclusive or missing results and input errors.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .api import LLM_INSTRUCTIONS, verify
from .checks import check_chain, check_equal
from .units import check_dimensions
from .verdict import Report, Status


def _pairs(items: list[str] | None, what: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--{what} expects NAME=VALUE, got '{item}'")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _emit(report: Report, as_json: bool) -> int:
    if as_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report)
    if report.status == Status.REFUTED:
        return 1
    return 0 if report.ok else 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mathguard",
                                description="Verify mathematical claims, e.g. from LLMs.")
    p.add_argument("--version", action="version", version=f"mathguard {__version__}")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("equal", help="check lhs == rhs")
    pe.add_argument("lhs")
    pe.add_argument("rhs")
    pe.add_argument("--assume", action="append", metavar="VAR=TAG",
                    help="e.g. x=positive (repeatable)")

    pc = sub.add_parser("chain", help="check a derivation step by step")
    pc.add_argument("steps", nargs="+")
    pc.add_argument("--assume", action="append", metavar="VAR=TAG")

    pd = sub.add_parser("dims", help="check dimensional consistency of an equation")
    pd.add_argument("equation")
    pd.add_argument("--unit", action="append", metavar="VAR=UNIT", required=True,
                    help="e.g. v=m/s or c=speed_of_light (repeatable)")

    pf = sub.add_parser("check", help="run JSON checks from a file or stdin")
    pf.add_argument("file", help="path to a JSON file, or - for stdin")

    pdoc = sub.add_parser("doc", help="check every formula chain in a Markdown/LaTeX file")
    pdoc.add_argument("file", help="path to a .md/.tex file, or - for stdin")
    pdoc.add_argument("--unit", action="append", metavar="VAR=UNIT",
                      help="units of variables, switches on dimension checks (repeatable)")
    pdoc.add_argument("--assume", action="append", metavar="VAR=TAG")
    pdoc.add_argument("--real", action="store_true",
                      help="treat variables as real instead of positive")
    pdoc.add_argument("--markdown", action="store_true", help="print the report as Markdown")

    pa = sub.add_parser("answer", help="grade the final result of an answer against a reference")
    pa.add_argument("file", help="path to the answer (.md/.tex/.txt), or - for stdin")
    pa.add_argument("--ref", action="append", required=True, metavar="NAME=REFERENCE",
                    help='e.g. "v = sqrt(10 g h / 7)" or "v = 4.10 m/s" (repeatable)')
    pa.add_argument("--given", action="append", metavar="VAR=VALUE",
                    help='known values, e.g. h="1.2 m" (repeatable)')
    pa.add_argument("--unit", action="append", metavar="VAR=UNIT",
                    help="units of further variables (repeatable)")
    pa.add_argument("--assume", action="append", metavar="VAR=TAG")
    pa.add_argument("--tol", type=float, default=None,
                    help="relative tolerance for numbers (default 0.01)")
    pa.add_argument("--no-steps", action="store_true", help="do not check the working")
    pa.add_argument("--markdown", action="store_true", help="print the report as Markdown")

    pg = sub.add_parser("grade", help="grade answers against task files")
    pg.add_argument("task", help="task file (.yaml/.json) or a directory of task files")
    pg.add_argument("answers", nargs="+",
                    help="answer files or directories; with a task directory, answers are "
                         "matched to tasks by file name (p1.md -> p1.yaml)")
    pg.add_argument("--no-steps", action="store_true", help="do not check the working")
    pg.add_argument("--verbose", "-v", action="store_true", help="show every quantity")

    sub.add_parser("prompt", help="print instructions to paste into an LLM system prompt")

    args = p.parse_args(argv)

    if args.cmd == "prompt":
        print(LLM_INSTRUCTIONS)
        return 0
    if args.cmd == "equal":
        return _emit(Report([check_equal(args.lhs, args.rhs, _pairs(args.assume, "assume"))]),
                     args.json)
    if args.cmd == "chain":
        return _emit(check_chain(args.steps, _pairs(args.assume, "assume")), args.json)
    if args.cmd == "dims":
        v = check_dimensions(_pairs(args.unit, "unit"), equation=args.equation)
        return _emit(Report([v]), args.json)
    if args.cmd == "check":
        text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        return _emit(verify(text), args.json)
    if args.cmd == "doc":
        from .document import check_document
        text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        rep = check_document(text, units=_pairs(args.unit, "unit") or None,
                             assumptions=_pairs(args.assume, "assume"),
                             positive=not args.real)
        if args.json:
            print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(rep.to_markdown() if args.markdown else rep)
        if rep.status == Status.REFUTED:
            return 1
        return 0 if rep.ok else 2
    if args.cmd == "answer":
        from .answer import DEFAULT_REL_TOL, check_answer
        text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        ref = "; ".join(args.ref)
        rep = check_answer(text, ref, given=_pairs(args.given, "given") or None,
                           units=_pairs(args.unit, "unit") or None,
                           assumptions=_pairs(args.assume, "assume") or None,
                           rel_tol=DEFAULT_REL_TOL if args.tol is None else args.tol,
                           steps=not args.no_steps)
        if args.json:
            print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(rep.to_markdown() if args.markdown else rep)
        return _grade_exit([rep])
    if args.cmd == "grade":
        return _grade_cmd(args)
    return 2  # pragma: no cover


def _grade_exit(reports) -> int:
    from .answer import Grade
    statuses = [r.status for r in reports]
    if Grade.WRONG in statuses:
        return 1
    return 0 if statuses and all(s == Grade.CORRECT for s in statuses) else 2


_TASK_SUFFIXES = (".yaml", ".yml", ".json")
_ANSWER_SUFFIXES = (".md", ".txt", ".tex", ".markdown")


def _grade_cmd(args) -> int:
    from pathlib import Path

    from .answer import grade, load_task

    task_path = Path(args.task)
    if task_path.is_dir():
        tasks = {p.stem: p for p in sorted(task_path.iterdir()) if p.suffix in _TASK_SUFFIXES}
    else:
        tasks = {None: task_path}
    answers: list[Path] = []
    for a in args.answers:
        ap = Path(a)
        if ap.is_dir():
            answers.extend(sorted(p for p in ap.rglob("*") if p.suffix in _ANSWER_SUFFIXES))
        else:
            answers.append(ap)
    rows, reports, skipped = [], [], []
    loaded: dict = {}
    for ap in answers:
        key = None if None in tasks else ap.stem
        if key not in tasks:
            skipped.append(ap)
            continue
        if key not in loaded:
            loaded[key] = load_task(tasks[key])
        rep = grade(loaded[key], ap.read_text(encoding="utf-8"), steps=not args.no_steps)
        reports.append(rep)
        rows.append((ap, loaded[key].get("id", key), rep))
    if args.json:
        print(json.dumps([{"answer": str(ap), "task": tid, **rep.to_dict()}
                          for ap, tid, rep in rows], ensure_ascii=False, indent=2))
    else:
        from .answer import _ICON
        width = max([len(str(ap)) for ap, _, _ in rows] + [6])
        for ap, tid, rep in rows:
            correct = sum(r.ok for r in rep.results)
            print(f"{_ICON[rep.status]} {str(ap):<{width}}  {correct}/{len(rep.results)}  "
                  f"{rep.status.value}")
            if args.verbose or not rep.ok:
                for r in rep.results:
                    if args.verbose or not r.ok:
                        print(f"    {_ICON[r.grade]} {r.name}: {r.message}")
                first = rep.steps.first_error if rep.steps is not None else None
                if first is not None and not rep.ok:
                    print(f"    working: first error in line {first.line}: {first.latex}")
        n_q = sum(len(rep.results) for rep in reports)
        n_ok = sum(r.ok for rep in reports for r in rep.results)
        full = sum(rep.ok for rep in reports)
        print(f"\n{len(reports)} answers, {full} fully correct; "
              f"{n_ok}/{n_q} quantities correct")
        for ap in skipped:
            print(f"skipped {ap}: no task with this name", file=sys.stderr)
    return _grade_exit(reports)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

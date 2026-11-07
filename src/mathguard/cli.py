"""Command line interface.

    mathguard equal "sin(x)^2 + cos(x)^2" "1"
    mathguard equal "sqrt(x^2)" "x" --assume x=positive
    mathguard chain "(x+1)^2" "x^2 + 2x + 1"
    mathguard dims "E = m c^2" --unit E=J --unit m=kg --unit c=m/s
    mathguard check checks.json          # file with JSON checks ("-" for stdin)
    mathguard doc solution.md --unit v0=m/s   # check a whole Markdown/LaTeX solution
    mathguard prompt                     # print instructions for an LLM

Exit code: 0 if everything is verified/likely, 1 if something was refuted,
2 for inconclusive results or input errors.
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
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

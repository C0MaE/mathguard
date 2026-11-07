"""Rename the keys of task and annotation files from the old German schema to English.

    python benchmark/migrate_schema.py FILE_OR_DIR [...]

Works line by line, so comments and layout are kept. Files that already use the
English schema are left unchanged. Only keys (and a few enum values) are renamed;
free text such as the problem statement or notes is not translated.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

KEYS = {
    "quelle": "source", "blatt": "sheet", "teil": "part", "kurs": "course",
    "fach": "subject", "thema": "topic", "gegeben": "given", "hilfsgroessen": "auxiliary",
    "annahmen": "assumptions", "gesucht": "wanted", "beschreibung": "description",
    "einheit": "unit", "nur_symbolisch": "symbolic_only", "referenz": "reference",
    "pruefer": "checked_by", "weg_a": "path_a", "weg_b": "path_b", "schritte": "steps",
    "formel": "formula", "zahlenwert": "value", "gleich_nur_numerisch": "numeric_match_only",
    "pruefungen": "extra_checks", "toleranz_antwort": "answer_tol",
    "abweichung_jannis": "author_discrepancy", "modell": "model", "endergebnis": "final",
    "fehler": "errors", "art": "type", "schritt": "step", "notiz": "note",
}
STATUS = {"offen": "open", "geprueft": "checked", "strittig": "disputed"}
ERROR_TYPES = {
    "vorzeichen": "sign", "faktor": "factor", "analysis": "calculus", "einheit": "units",
    "numerik": "numeric", "loesungsmenge": "solution_set", "grenzfall": "limiting_case",
    "ansatz": "approach", "sonstiges": "other",
}

_KEY = re.compile(r"(^|[\s{,\-])(" + "|".join(sorted(KEYS, key=len, reverse=True)) + r")(?=:)")


def migrate_line(line: str) -> str:
    # top-level problem text vs. exercise number inside `quelle: {...}`
    line = re.sub(r"^aufgabe(?=:)", "statement", line)
    line = re.sub(r"([{,]\s*)aufgabe(?=:)", r"\1exercise", line)
    line = re.sub(r"^(\s+)aufgabe(?=:)", r"\1exercise", line)
    line = _KEY.sub(lambda m: m.group(1) + KEYS[m.group(2)], line)
    line = re.sub(r"(\bstatus:\s*)(offen|geprueft|strittig)\b",
                  lambda m: m.group(1) + STATUS[m.group(2)], line)
    line = re.sub(r"(\btype:\s*)(\w+)",
                  lambda m: m.group(1) + ERROR_TYPES.get(m.group(2), m.group(2)), line)
    return line


def migrate_file(path: Path) -> bool:
    old = path.read_text(encoding="utf-8")
    new = "".join(migrate_line(line) for line in old.splitlines(keepends=True))
    if new != old:
        path.write_text(new, encoding="utf-8")
    return new != old


def main(argv: list[str]) -> int:
    if not argv:
        sys.exit(__doc__)
    files = []
    for arg in map(Path, argv):
        files += sorted(arg.rglob("*.yaml")) if arg.is_dir() else [arg]
    changed = [f for f in files if migrate_file(f)]
    for f in changed:
        print(f"migrated: {f}")
    print(f"{len(changed)} of {len(files)} file(s) changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

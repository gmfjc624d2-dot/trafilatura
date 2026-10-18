"""Write the five byte-exact fixtures of this repair and their file identities.

  python build_fixtures.py build   # writes fixtures/n*.html and fixtures/files.json
  python build_fixtures.py check   # rebuilds in memory, compares bytes (exit 1 if different)

N1 and N2 are the two public synthetic inputs supplied with the request, written character for
character as given between the code fences: UTF-8, LF line ends, no final newline (the fences
hold none). N3-N5 are original synthetic pages of this increment (Apache-2.0): N3 is encoded in
windows-1252 and declares it; N4 and N5 are a minimal pair that differ only by a stray end tag
outside the unit. Python 3.12 standard library only.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

N1_LATE = (
    '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><dl class="py function"><dt class="sig sig-object py" id="pkg.late">late()</dt><dd>First line of description.\n'
    "Second line of description.\n"
    "</span>\n"
    "Third line of description.\n"
    "</dd></dl></body></html>"
)
N2_TARGET = (
    '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><!--<dt class="sig sig-object py" id="pkg.target">target()</dt><dd><p>A</p></dd>-->'
    '<dl class="py function"><dt class="sig sig-object py" id="pkg.target">target()</dt><dd><p>&#65;</p></dd></dl></body></html>'
)


def page(charset, title, unit, after):
    return (
        f'<!DOCTYPE html>\n<html>\n<head>\n<meta charset="{charset}">\n<title>{title}</title>\n</head>\n<body>\n'
        f'<dl class="py function">\n{unit}</dl>\n{after}</body>\n</html>\n'
    )


N3_LEGACY = page(
    "windows-1252",
    "pkg legacy",
    '<dt class="sig sig-object py" id="pkg.legacy">legacy()</dt>\n<dd><p>Café costs 5 €, “quoted”. MARK-LEGACY-DESC</p></dd>\n',
    "<p>Closing paragraph. MARK-LEGACY-TAIL</p>\n",
)
N4_OUTSIDE = page(
    "utf-8",
    "pkg outside",
    '<dt class="sig sig-object py" id="pkg.inside">inside()</dt>\n<dd><p>Clean description. MARK-INSIDE-DESC</p></dd>\n',
    "<p>Footer text with a stray end tag.</span> MARK-OUTSIDE-FOOTER</p>\n",
)
N5_CLEAN = page(
    "utf-8",
    "pkg clean",
    '<dt class="sig sig-object py" id="pkg.clean">clean()</dt>\n<dd><p>Clean description. MARK-CLEAN-DESC</p></dd>\n',
    "<p>Footer text. MARK-CLEAN-FOOTER</p>\n",
)

FIXTURE_TEXTS = {
    "n1_late_diagnostic.html": (N1_LATE, "utf-8"),
    "n2_comment_match.html": (N2_TARGET, "utf-8"),
    "n3_windows1252.html": (N3_LEGACY, "cp1252"),
    "n4_outside_diagnostic.html": (N4_OUTSIDE, "utf-8"),
    "n5_clean_control.html": (N5_CLEAN, "utf-8"),
}


def build():
    files = {FIXTURES / name: text.encode(codec) for name, (text, codec) in FIXTURE_TEXTS.items()}
    meta = {
        "note": "identities of the retained fixture bytes, written by scripts/build_fixtures.py before any repaired code existed",
        "files": {
            f"fixtures/{p.name}": {
                "bytes": len(d),
                "sha256": hashlib.sha256(d).hexdigest(),
                "encoding_written": FIXTURE_TEXTS[p.name][1],
                "final_newline": d.endswith(b"\n"),
            }
            for p, d in files.items()
        },
    }
    files[FIXTURES / "files.json"] = (json.dumps(meta, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return files


def main():
    files = build()
    if sys.argv[1] == "build":
        FIXTURES.mkdir(exist_ok=True)
        for path, data in files.items():
            path.write_bytes(data)
            print(f"wrote {path.relative_to(ROOT).as_posix()} {len(data)} bytes sha256={hashlib.sha256(data).hexdigest()}")
        return 0
    differ = [p.relative_to(ROOT).as_posix() for p, d in files.items() if not p.exists() or p.read_bytes() != d]
    print("check: " + ("identical" if not differ else f"DIFFERS: {differ}"))
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())

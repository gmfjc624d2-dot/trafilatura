"""Write the one new fixture, a clean long Sphinx unit, and print its expected unit text identity.

  python build_witness.py build   # writes fixtures/w1_long_clean.html
  python build_witness.py check   # rebuilds in memory, compares bytes (exit 1 if different)

The expected unit text is computed here from the paragraph list, never by a parser:
"long()¶" + "\n" (the dt tail) + the paragraphs joined by "\n" (the p tails inside the dd); the
dd's own final tail is excluded. The unit is meant to be well-formed HTML (no parser diagnostics
predicted) and long enough that anchor_unit.py's 2048-byte context check makes both
representations REVIEW_OVER_BUDGET. Python 3.12 standard library only.
"""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "w1_long_clean.html"
PARAGRAPHS = [f"Paragraph {i:02d} of the long description of pkg.long. MARK-LONG-{i:02d}" for i in range(1, 37)]


def page():
    body = "\n".join(f"<p>{p}</p>" for p in PARAGRAPHS)
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>pkg long</title>\n</head>\n<body>\n'
        '<dl class="py function">\n'
        '<dt class="sig sig-object py" id="pkg.long">long()<a class="headerlink" href="#pkg.long">¶</a></dt>\n'
        f"<dd>{body}</dd>\n</dl>\n<p>Closing paragraph. MARK-LONG-TAIL</p>\n</body>\n</html>\n"
    ).encode()


def expected_text():
    return "long()¶" + "\n" + "\n".join(PARAGRAPHS)


def main():
    data, text = page(), expected_text().encode("utf-8")
    print(f"fixture {FIXTURE.relative_to(ROOT).as_posix()}: {len(data)} bytes sha256={hashlib.sha256(data).hexdigest()}")
    print(f"expected unit text: {len(text)} UTF-8 bytes sha256={hashlib.sha256(text).hexdigest()}")
    if sys.argv[1] == "build":
        FIXTURE.write_bytes(data)
        return 0
    same = FIXTURE.exists() and FIXTURE.read_bytes() == data
    print("check: " + ("identical" if same else "DIFFERS"))
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())

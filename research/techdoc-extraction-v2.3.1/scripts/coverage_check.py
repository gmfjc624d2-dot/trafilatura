"""POST-HOC detector for text lost by main-content selection (REPORT.md section 6).

Lists the text blocks of a page (p, li, pre, headings, table cells...) whose words do not all
occur in extract()'s output. It flags boilerplate as well as lost content: the caller reviews
the list. It detects, it does not fix.

Usage: python coverage_check.py FIXTURE_DIR
"""

import json
import re
import sys
from pathlib import Path

from trafilatura import extract, load_html

BLOCKS = ("p", "li", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "dd", "dt", "blockquote")


def words(s):
    return re.findall(r"\w+", s)


def missing_blocks(page, url, min_words=6):
    "Text blocks of the page whose words do not all occur in the extraction."
    out = set(words(extract(page, url=url) or ""))
    tree = load_html(page)
    blocks = (" ".join(" ".join(el.itertext()).split()) for el in tree.iter(BLOCKS))
    return [b for b in blocks if len(words(b)) >= min_words and not set(words(b)) <= out]


def main():
    fixture_dir = Path(sys.argv[1])
    expectations = json.loads((fixture_dir / "expectations.json").read_text(encoding="utf-8"))
    for name, fixture in expectations["fixtures"].items():
        flagged = missing_blocks((fixture_dir / name).read_bytes(), fixture["url"])
        print(f"{name}: {len(flagged)} block(s) not in extract()")
        for block in flagged:
            print("    ", block[:140])
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Sanity-check the pre-registered expectations against the fixture sources only.

Does not run trafilatura. For every requirement it checks that the expected link target
equals urljoin(document base URL, href), and that the anchor/href, statement, code and
table row actually exist in the fixture as parsed by lxml.html.

Usage: python check_expectations.py FIXTURE_DIR   (exit code 1 on any problem)
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from lxml import html


def tokens(text):
    return re.findall(r"\w+", text)


def contains(seq, sub):
    return any(seq[i : i + len(sub)] == sub for i in range(len(seq) - len(sub) + 1))


def main():
    fixture_dir = Path(sys.argv[1])
    expectations = json.loads((fixture_dir / "expectations.json").read_text(encoding="utf-8"))
    problems = 0
    for name, fixture in expectations["fixtures"].items():
        tree = html.fromstring((fixture_dir / name).read_bytes())
        base_el = next((b for b in tree.iter("base") if b.get("href") is not None), None)
        base = urljoin(fixture["url"], base_el.get("href").strip()) if base_el is not None else fixture["url"]
        anchors = {re.sub(r"\s+", " ", a.text_content()).strip(): a.get("href") for a in tree.iter("a")}
        text = " ".join(tree.itertext())  # separate adjacent blocks, as R1 does for XML
        rows = [[re.sub(r"\s+", " ", c.text_content()).strip() for c in tr if c.tag in ("td", "th")] for tr in tree.iter("tr")]
        for req in fixture["requirements"]:
            issue = None
            if req["type"] == "link":
                if urljoin(base, req["href"]) != req["target"]:
                    issue = f"target != urljoin(base, href) = {urljoin(base, req['href'])}"
                elif anchors.get(req["anchor"]) != req["href"]:
                    issue = f"anchor/href not in fixture (found {anchors.get(req['anchor'])})"
            elif req["type"] == "statement" and not contains(tokens(text), tokens(req["text"])):
                issue = "statement not in fixture"
            elif req["type"] in ("code_chars", "code_marked") and req["code"] not in text:
                issue = "code not in fixture"
            elif req["type"] == "code_block" and req["block"] not in text:
                issue = "code block not in fixture"
            elif req["type"] == "table_row" and req["cells"] not in rows:
                issue = f"row not in fixture (rows: {rows})"
            if issue:
                problems += 1
                print(f"PROBLEM {name} {req['id']}: {issue}")
        print(f"{name}: base={base} requirements={len(fixture['requirements'])}")
    print(f"problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

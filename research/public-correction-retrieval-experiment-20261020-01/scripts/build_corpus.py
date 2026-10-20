"""Write the synthetic public corpus and its manifest, or check that they are unchanged.

  python build_corpus.py build   # writes corpus/records/R01.txt ... R12.txt and corpus/corpus.json
  python build_corpus.py check   # rebuilds in memory and compares bytes (exit 1 if different)

Every record is invented for this experiment. A record file is its paragraphs joined by a blank
line, plus a final LF. A passage is one paragraph, and its locator is
`corpus/records/<id>.txt#p<n>` with its UTF-8 byte range and sha256.

The manifest holds only identity and declaration metadata: record id, issuer, declared date, the
identifiers the record itself issues, and the passages. It holds no relation, role or status. The
evaluation annotations live in fixtures/expectations.json and are never read by discovery.
Standard library only; Python 3.9+.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LB, CC = "Library Board", "City Council"
RECORDS = [
    ("R01", LB, "2019-03-12", [], [
        "Library Board. Minutes of the meeting of 12 March 2019.",
        "Item 4. A member proposes moving the reading room to the north building. The proposal is referred to the next meeting without a vote.",
    ]),
    ("R02", LB, "2019-05-14", ["14/2019"], [
        "Library Board. Minutes of the meeting of 14 May 2019.",
        "Item 3. Agreement 14/2019. The Library Board approves moving the reading room to the north building.",
        "Clause 1. The reading room moves to the north building on 2 September 2019.",
        "Clause 2. The reading room opens from 9:00 to 20:00.",
    ]),
    ("R03", LB, "2019-08-26", [], [
        "Library Board. Notice of 26 August 2019.",
        "In implementation of agreement 14/2019, the reading room is closed from 2 to 6 September 2019 while furniture is moved.",
    ]),
    ("R04", LB, "2019-11-19", [], [
        "Library Board. Minutes of the meeting of 19 November 2019.",
        "Item 5. Clause 2 of agreement 14/2019 is amended to read: the reading room opens from 10:00 to 18:00. All other clauses remain unchanged.",
    ]),
    ("R05", LB, "2020-01-10", [], [
        "Library Board. Notice of 10 January 2020.",
        "This notice does NOT revoke agreement 14/2019. Holiday opening hours for the reading room are published separately.",
    ]),
    ("R06", CC, "2019-06-20", ["14/2019"], [
        "City Council. Minutes of the plenary session of 20 June 2019.",
        "Agreement 14/2019. The City Council approves resurfacing the market square.",
    ]),
    ("R07", LB, "2020-02-11", [], [
        "Library Board. Minutes of the meeting of 11 February 2020.",
        "Item 2. Agreement 14/2019 is left without effect.",
    ]),
    ("R08", LB, "2020-02-25", [], [
        "Library Board. Payments of 25 February 2020.",
        "Invoice 14-2019 for bookbinding services is paid.",
    ]),
    ("R09", LB, "2020-03-10", [], [
        "Library Board. Minutes of the meeting of 10 March 2020.",
        "Item 1. As provided in agreement 22/2019, the reading room keeps its catalogue terminals.",
    ]),
    ("R10", LB, "2019-12-03", ["114/2019"], [
        "Library Board. Minutes of the meeting of 3 December 2019.",
        "Item 2. Agreement 114/2019. The Library Board approves a loan period of three weeks.",
    ]),
    ("R11", LB, "2021-06-15", ["3/2021"], [
        "Library Board. Minutes of the meeting of 15 June 2021.",
        "Item 6. Agreement 3/2021. The Library Board approves the purchase of new shelving for the archive.",
    ]),
    ("R12", LB, "2020-01-28", [], [
        "Library Board. Minutes of the meeting of 28 January 2020.",
        "Item 4. The move of the reading room to the north building is suspended until further notice.",
    ]),
]  # fmt: skip
SCOPE = (
    "exactly the 12 synthetic records listed here, and nothing else; declared dates are the records' own "
    "declarations, not verified; this list is the whole corpus searched, and it is not claimed to be complete "
    "for any real body or period"
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def build():
    "The record files' bytes and the manifest, in memory."
    files, records = {}, []
    for record_id, issuer, date, issues, paragraphs in RECORDS:
        rel = f"corpus/records/{record_id}.txt"
        data = ("\n\n".join(paragraphs) + "\n").encode("utf-8")
        passages, start = [], 0
        for n, paragraph in enumerate(paragraphs):
            raw = paragraph.encode("utf-8")
            passages.append({"n": n, "byte_start": start, "byte_end": start + len(raw), "sha256": sha256(raw)})
            start += len(raw) + 2
        files[rel] = data
        records.append(
            {
                "record_id": record_id,
                "file": rel,
                "bytes": len(data),
                "sha256": sha256(data),
                "issuer": issuer,
                "declared_date": date,
                "issues_identifiers": issues,
                "passages": passages,
            }
        )
    manifest = {"schema": 1, "corpus_id": "synthetic-library-board-2019-2021", "declared_scope": SCOPE, "records": records}
    files["corpus/corpus.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    return files


def main():
    files = build()
    for rel, data in files.items():
        print(f"{rel}: {len(data)} bytes sha256={sha256(data)}")
    if sys.argv[1] == "build":
        for rel, data in files.items():
            (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / rel).write_bytes(data)
        return 0
    same = all((ROOT / rel).exists() and (ROOT / rel).read_bytes() == data for rel, data in files.items())
    print("check: " + ("identical" if same else "DIFFERS"))
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())

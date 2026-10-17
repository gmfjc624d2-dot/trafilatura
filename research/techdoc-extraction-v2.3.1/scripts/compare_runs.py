"""Compare two result directories written by run_all.py (or the individual scripts).

Usage: python compare_runs.py BEFORE_DIR AFTER_DIR [--expect-identical]
Prints, mechanically and without interpretation:
- link_resolution.json: per case and path, verdict before -> after
- public_corpus_links_as-is.json: totals and per-page strict mismatches before -> after
- matrix_summary.json: per requirement FAIL count before -> after, raw outputs that changed
Exit code 1 if any requirement or link case got worse (or, with --expect-identical, if any
verdict, mismatch count or raw output differs at all).
"""

import json
import sys
from pathlib import Path


def load(directory, name):
    path = Path(directory) / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_outputs(directory):
    path = Path(directory) / "matrix_outputs.jsonl"
    if not path.exists():
        return {}
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        key = (r["fixture"], r["mode"], r["include_links"], r["include_tables"], r["include_formatting"], r["output_format"])
        records[key] = r
    return records


def main():
    before, after = sys.argv[1], sys.argv[2]
    identical = "--expect-identical" in sys.argv
    worse = differ = 0

    a, b = load(before, "link_resolution.json"), load(after, "link_resolution.json")
    if a and b:
        print("== link_resolution.json (case: path verdict before -> after)")
        cases_b = {r["case"]: r for r in b["results"]}
        for ra in a["results"]:
            rb = cases_b[ra["case"]]
            for path, va in ra["verdicts"].items():
                vb = rb["verdicts"][path]
                if va != vb:
                    differ += 1
                    worse += va == "PASS"
                    print(f"  {ra['case']:32} {path:24} {va} -> {vb}")
                elif identical and ra["observed"][path] != rb["observed"][path]:
                    differ += 1
                    print(f"  {ra['case']:32} {path:24} same verdict, observed changed")
        print(f"  failing cases: {a['failing_cases']} -> {b['failing_cases']}")

    a, b = load(before, "public_corpus_links_as-is.json"), load(after, "public_corpus_links_as-is.json")
    if a and b:
        print("== public_corpus_links_as-is.json (strict mismatches / targets)")
        for mode in ("default", "fast"):
            ta, tb = a["totals"][mode], b["totals"][mode]
            print(
                f"  {mode}: {ta['mismatches']}/{ta['targets']} on {ta['pages_with_mismatch']} pages -> "
                f"{tb['mismatches']}/{tb['targets']} on {tb['pages_with_mismatch']} pages"
            )
        pages_b = {p["file"]: p for p in b["pages"]}
        for pa in a["pages"]:
            pb = pages_b[pa["file"]]
            for mode in ("default", "fast"):
                ma, mb = pa[mode]["mismatches"], pb[mode]["mismatches"]
                if ma != mb or (identical and pa[mode] != pb[mode]):
                    differ += 1
                    worse += mb > ma
                    print(
                        f"  {pa['file']} {mode}: {ma}/{pa[mode]['targets']} -> {mb}/{pb[mode]['targets']} {pb[mode]['examples'][:2]}"
                    )

    a, b = load(before, "matrix_summary.json"), load(after, "matrix_summary.json")
    if a and b:
        print(f"== matrix_summary.json losses: {a['losses_total']} -> {b['losses_total']}")
        for key, sa in a["requirements"].items():
            sb = b["requirements"][key]
            if sa != sb:
                differ += 1
                worse += sb["FAIL"] > sa["FAIL"]
                print(f"  {key:58} FAIL {sa['FAIL']:3} -> {sb['FAIL']:3}  PASS {sa['PASS']:3} -> {sb['PASS']:3}")
        oa, ob = load_outputs(before), load_outputs(after)
        changed = [k for k in oa if k in ob and oa[k]["output"] != ob[k]["output"]]
        print(f"  raw outputs changed: {len(changed)} of {len(oa)}")
        by_fixture = {}
        for k in changed:
            by_fixture[k[0]] = by_fixture.get(k[0], 0) + 1
        for fixture, count in sorted(by_fixture.items()):
            print(f"    {fixture}: {count}")
        if identical:
            differ += len(changed)

    print(f"\nworse: {worse}, differences: {differ}")
    return 1 if worse or (identical and differ) else 0


if __name__ == "__main__":
    sys.exit(main())

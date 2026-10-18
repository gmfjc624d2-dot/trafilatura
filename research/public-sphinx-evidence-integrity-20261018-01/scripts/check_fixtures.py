"""Validate the pre-registration against retained bytes only (no HTML parser), write byte_facts.json.

Checks: fixture identities (fixtures/files.json), the pinned inputs of the previous increment,
that the baseline copies are byte-identical to the files they copy, that the context template
and budget are unchanged, that every marker and anchor id is in the fixture bytes, and that the
text_replace mutation target occurs exactly once. Records byte facts the predictions refer to:
line numbers of tokens, and the [start, end) byte regions N2.comment_copy, N2.live_unit,
N3.live_unit, N4.live_unit, N5.live_unit. These are literal byte searches made to state
predictions, not node-to-source alignments. Python 3.12 standard library only. Exit 1 on any problem.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def line_of(data, offset):
    return data.count(b"\n", 0, offset) + 1


def unit_region(data, dt_start):
    "From a live dt start to the end of the first '</dd>' after it."
    end = data.index(b"</dd>", dt_start) + len(b"</dd>")
    return {"byte_start": dt_start, "byte_end": end, "sha256": sha256(data[dt_start:end])}


def find_all(data, needle):
    out, pos = [], data.find(needle)
    while pos >= 0:
        out.append(pos)
        pos = data.find(needle, pos + 1)
    return out


def main():
    exp = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
    files = json.loads((ROOT / "fixtures" / "files.json").read_text(encoding="utf-8"))["files"]
    old_root = (ROOT / exp["old_inputs"]["root"]).resolve()
    problems = []
    for rel, meta in files.items():
        data = (ROOT / rel).read_bytes()
        if (len(data), sha256(data)) != (meta["bytes"], meta["sha256"]):
            problems.append(f"{rel}: identity differs from files.json")
    for rel, digest in exp["old_inputs"]["sha256"].items():
        if sha256((old_root / rel).read_bytes()) != digest:
            problems.append(f"old input {rel}: sha256 differs from the pin")
    for copy, original in exp["baseline_copies"].items():
        if (ROOT / copy).read_bytes() != (old_root / original).read_bytes():
            problems.append(f"{copy} is not byte-identical to the previous {original}")
    old_exp = json.loads((old_root / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
    if (exp["context_template"], exp["budget_bytes"]) != (old_exp["context_template"], old_exp["budget_bytes"]):
        problems.append("context template or budget differs from the previous pre-registration")

    raw = {c["id"]: (ROOT / c["file"]).read_bytes() for c in exp["new_cases"]}
    facts = {"note": "literal byte facts for stating predictions; not node-to-source alignments", "cases": {}, "regions": {}}
    for case in exp["new_cases"]:
        data = raw[case["id"]]
        codec = files[case["file"]]["encoding_written"]
        markers = case["requirements"].get("must_include", []) + case["requirements"].get("must_exclude", [])
        problems.extend(f"{case['id']}: marker {m!r} not in the bytes" for m in markers if m.encode(codec) not in data)
        facts["cases"][case["id"]] = {
            "file": case["file"],
            "bytes": len(data),
            "lines": data.count(b"\n") + (0 if data.endswith(b"\n") else 1),
            "final_newline": data.endswith(b"\n"),
            "anchor_id_attribute_byte_count": data.count(f'id="{case["anchor"]}"'.encode(codec)),
        }

    n1 = raw["N1"]
    facts["cases"]["N1"]["token_lines"] = {
        tok: line_of(n1, n1.index(tok.encode())) for tok in ("<dt ", "<dd>", "</span>", "Third line", "</dd>")
    }
    n2 = raw["N2"]
    comment = {"byte_start": n2.index(b"<!--"), "byte_end": n2.index(b"-->") + 3}
    serial = exp["new_cases"][1]["baseline_prediction"]["dom_serialization"].encode("utf-8")
    occurrences = find_all(n2, serial)
    if len(occurrences) != 1:
        problems.append(f"N2: predicted serialization occurs {len(occurrences)} times")
    else:
        start = occurrences[0]
        facts["regions"]["N2.comment_copy"] = {"byte_start": start, "byte_end": start + len(serial), "sha256": sha256(serial)}
    dts = find_all(n2, b'<dt class="sig sig-object py" id="pkg.target">')
    inside = [p for p in dts if comment["byte_start"] < p < comment["byte_end"]]
    live = [p for p in dts if p not in inside]
    facts["cases"]["N2"].update(
        {
            "comment": comment,
            "predicted_serialization_offsets": occurrences,
            "predicted_serialization_inside_comment": [comment["byte_start"] < p < comment["byte_end"] for p in occurrences],
            "dt_offsets_inside_comment": inside,
            "dt_offsets_outside_comment": live,
        }
    )
    if len(live) != 1 or len(inside) != 1:
        problems.append("N2: expected one commented and one live dt")
    else:
        facts["regions"]["N2.live_unit"] = unit_region(n2, live[0])
    for cid, anchor in (("N3", "pkg.legacy"), ("N4", "pkg.inside"), ("N5", "pkg.clean")):
        data = raw[cid]
        facts["regions"][f"{cid}.live_unit"] = unit_region(
            data, data.index(f'<dt class="sig sig-object py" id="{anchor}">'.encode())
        )
    n3 = raw["N3"]
    r = facts["regions"]["N3.live_unit"]
    region = n3[r["byte_start"] : r["byte_end"]]
    facts["cases"]["N3"]["live_unit_cp1252_bytes"] = len(region)
    facts["cases"]["N3"]["live_unit_utf8_bytes"] = len(region.decode("cp1252").encode("utf-8"))
    facts["cases"]["N3"]["declares"] = '<meta charset="windows-1252">' if b'<meta charset="windows-1252">' in n3 else None
    n4 = raw["N4"]
    facts["cases"]["N4"]["token_lines"] = {tok: line_of(n4, n4.index(tok.encode())) for tok in ("<dt ", "<dd>", "</span>")}
    facts["cases"]["N5"]["has_stray_span"] = b"</span>" in raw["N5"]
    for cid, fact in facts["cases"].items():
        wanted = 2 if cid == "N2" else 1
        if fact["anchor_id_attribute_byte_count"] != wanted:
            problems.append(f"{cid}: id attribute occurs {fact['anchor_id_attribute_byte_count']} times, expected {wanted}")
    for m in exp["mutation_controls"]["mutations"]:
        for op in m["ops"]:
            if op["op"] == "text_replace":
                text = (old_root / "results/run1-linux-py3.12/results.json").read_text(encoding="utf-8")
                if text.count(op["old"]) != 1:
                    problems.append(f"{m['id']}: text_replace target occurs {text.count(op['old'])} times")
    (ROOT / "fixtures" / "byte_facts.json").write_text(
        json.dumps(facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(facts, indent=2, ensure_ascii=False))
    for p in problems:
        print("PROBLEM", p)
    print(
        f"new cases: {len(exp['new_cases'])}, mutations: {len(exp['mutation_controls']['mutations'])}, problems: {len(problems)}"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

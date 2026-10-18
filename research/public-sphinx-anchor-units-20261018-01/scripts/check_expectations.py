"""Validate the pre-registered expectations against the retained bytes only (no HTML parser).

For every case: the file exists, the exact `id="<anchor>"` byte count fits the expected reason,
each marker occurs in the file, and where a raw region is named, must_include markers lie
inside it and must_exclude markers occur only outside it. Derives the public page's region from
the literal rule in expectations.json. Writes fixtures/expectations_resolved.json.
Python 3.12 standard library only. Exit code 1 on any problem.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINNED = {
    "source/numpy-2.5/numpy.where.html": "ee9fb008cbdfa6371e548559f477f5a672d2563627b9efe5213b184bd1f80f48",
    "source/numpy-2.5/LICENSE.txt": "1be1df33863f97a7bc1c4d67980bd6c69c9a6fef0a5ee76e6ad6cb91e56e8491",
}
EXPECTED_ID_COUNT = {"MISSING_ID": 0, "ID_NORMALIZATION_MISMATCH": 0, "DUPLICATE_ID": 2}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def public_region(data):
    start = data.find(b'<dt class="sig sig-object py" id="numpy.where">')
    end_marker = data.find(b"</dd></dl>", start)
    if start < 0 or end_marker < 0:
        return None
    end = end_marker + len(b"</dd>")
    return {
        "file": "source/numpy-2.5/numpy.where.html",
        "byte_start": start,
        "byte_end": end,
        "sha256": sha256(data[start:end]),
    }


def main():
    exp = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
    regions = json.loads((ROOT / "fixtures" / "regions.json").read_text(encoding="utf-8"))["regions"]
    problems = []
    for path, digest in PINNED.items():
        if sha256((ROOT / path).read_bytes()) != digest:
            problems.append(f"{path}: sha256 differs from the pinned value")
    numpy_bytes = (ROOT / "source/numpy-2.5/numpy.where.html").read_bytes()
    regions["public:numpy.where"] = public_region(numpy_bytes)
    resolved = []
    for case in exp["cases"]:
        data = (ROOT / case["file"]).read_bytes()
        count = data.count(f'id="{case["anchor"]}"'.encode())
        reasons = [] if case["structural"] == "OK" else case["structural"]
        wanted = next((EXPECTED_ID_COUNT[r] for r in reasons if r in EXPECTED_ID_COUNT), 1)
        if count != wanted:
            problems.append(f"{case['id']}: id occurs {count} times in the bytes, expected {wanted}")
        problems.extend(
            f"{case['id']}: marker {marker!r} not in {case['file']}"
            for marker in case.get("must_include", []) + case.get("must_exclude", [])
            if marker.encode("utf-8") not in data
        )
        region = regions.get(case.get("raw_region")) if case.get("raw_region") else None
        if case.get("raw_region") and region is None:
            problems.append(f"{case['id']}: raw region {case['raw_region']} not found")
        if region:
            inside = data[region["byte_start"] : region["byte_end"]]
            outside = data[: region["byte_start"]] + b"\x00" + data[region["byte_end"] :]
            problems.extend(
                f"{case['id']}: must_include {m!r} not inside the raw region"
                for m in case.get("must_include", [])
                if m.encode("utf-8") not in inside
            )
            problems.extend(
                f"{case['id']}: must_exclude {m!r} occurs inside the raw region"
                for m in case.get("must_exclude", [])
                if m.encode("utf-8") in inside
            )
            problems.extend(
                f"{case['id']}: must_exclude {m!r} has no occurrence outside the raw region"
                for m in case.get("must_exclude", [])
                if m.encode("utf-8") not in outside
            )
        resolved.append({"case": case["id"], "anchor_id_byte_count": count, "raw_region": region})
        print(
            f"{case['id']} {case['anchor']!r:42} id-count={count} region={region and [region['byte_start'], region['byte_end']]}"
        )
    if regions["public:numpy.where"]:
        r = regions["public:numpy.where"]
        tail = numpy_bytes[r["byte_start"] :]
        if tail.count(b"</dd></dl>") < 1:
            problems.append("public region end marker missing")
    out = {
        "note": "derived from bytes only, before any selection code ran",
        "cases": resolved,
        "public_region": regions["public:numpy.where"],
    }
    (ROOT / "fixtures" / "expectations_resolved.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    for p in problems:
        print("PROBLEM", p)
    print(f"cases: {len(exp['cases'])}, problems: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

"""Verify the retained wheels from their bytes, not from a registry hash alone (standard library only).

Usage: python verify_wheels.py
For each wheel in wheels/WHEELS.json: file sha256 and size; zip integrity; every RECORD entry's
hash and size against the member bytes, and no member outside RECORD; METADATA name, version,
license and Requires-Dist; WHEEL purelib flag and tags; no native or compiled members; the
license notices' sha256; and that wheels/requirements.lock pins exactly these files. Nothing is
installed or imported. Exit 1 on any problem.
"""

import base64
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = (".so", ".pyd", ".dylib", ".dll", ".pyc", ".pyo")


def check_wheel(spec):
    problems = []
    data = (ROOT / "wheels" / spec["filename"]).read_bytes()
    if (hashlib.sha256(data).hexdigest(), len(data)) != (spec["sha256"], spec["bytes"]):
        problems.append("file sha256/size differs from WHEELS.json")
    if spec["registry"]["sha256"] != spec["sha256"] or spec["registry"]["size"] != spec["bytes"]:
        problems.append("registry record and file identity disagree")
    z = zipfile.ZipFile(io.BytesIO(data))
    if z.testzip() is not None:
        problems.append("zip CRC failure")
    names = z.namelist()
    dist_info = {n.split("/")[0] for n in names if n.split("/")[0].endswith(".dist-info")}
    if len(dist_info) != 1:
        return [*problems, f"dist-info directories: {sorted(dist_info)}"], {"filename": spec["filename"]}
    di = dist_info.pop()
    rows = list(csv.reader(io.StringIO(z.read(f"{di}/RECORD").decode("utf-8"))))
    hashed = 0
    for path, digest, size in rows:
        if not digest:
            if path != f"{di}/RECORD":
                problems.append(f"RECORD entry without hash: {path}")
            continue
        algo, _, expected = digest.partition("=")
        member = z.read(path)
        got = base64.urlsafe_b64encode(hashlib.new(algo, member).digest()).rstrip(b"=").decode()
        hashed += 1
        if got != expected or (size and int(size) != len(member)):
            problems.append(f"RECORD mismatch: {path}")
    if set(names) != {r[0] for r in rows}:
        problems.append(f"members outside RECORD: {sorted(set(names) ^ {r[0] for r in rows})}")
    if len(rows) != spec["record_entries"]:
        problems.append("RECORD entry count differs from WHEELS.json")
    head = z.read(f"{di}/METADATA").decode("utf-8").split("\n\n")[0].splitlines()

    def field(name):
        return [line.split(": ", 1)[1] for line in head if line.startswith(f"{name}:")]

    meta = spec["metadata"]
    observed = {
        "name": field("Name")[0],
        "version": field("Version")[0],
        "license": (field("License") or [None])[0],
        "requires_python": (field("Requires-Python") or [None])[0],
        "requires_dist": field("Requires-Dist"),
    }
    if observed != meta:
        problems.append(f"METADATA differs: {observed}")
    wheel = z.read(f"{di}/WHEEL").decode("utf-8").splitlines()
    tags = [line.split(": ", 1)[1] for line in wheel if line.startswith("Tag:")]
    if "Root-Is-Purelib: true" not in wheel or tags != spec["wheel"]["tags"] or not spec["wheel"]["root_is_purelib"]:
        problems.append(f"WHEEL differs: {tags}")
    native = [n for n in names if n.endswith(NATIVE)]
    if native:
        problems.append(f"native or compiled members: {native}")
    problems += [
        f"license notice differs: {lic['path']}"
        for lic in spec["licenses"]
        if hashlib.sha256((ROOT / lic["path"]).read_bytes()).hexdigest() != lic["sha256"]
    ]
    return problems, {"filename": spec["filename"], "record_hashes_checked": hashed, "members": len(names), **observed}


def main():
    manifest = json.loads((ROOT / "wheels" / "WHEELS.json").read_text(encoding="utf-8"))
    lock = (ROOT / "wheels" / "requirements.lock").read_text(encoding="utf-8")
    pins = re.findall(r"^([A-Za-z0-9_.-]+)==(\S+) \\\n\s+--hash=sha256:([0-9a-f]{64})$", lock, re.MULTILINE)
    expected = [(w["metadata"]["name"], w["metadata"]["version"], w["sha256"]) for w in manifest["wheels"]]
    problems = [] if pins == expected else [f"requirements.lock pins {pins}, manifest has {expected}"]
    on_disk = sorted(p.name for p in (ROOT / "wheels").glob("*.whl"))
    if on_disk != sorted(w["filename"] for w in manifest["wheels"]):
        problems.append(f"wheel files on disk: {on_disk}")
    for spec in manifest["wheels"]:
        found, summary = check_wheel(spec)
        problems += [f"{spec['filename']}: {p}" for p in found]
        print(json.dumps(summary))
    for p in problems:
        print("PROBLEM", p)
    print(f"wheels: {len(manifest['wheels'])}, problems: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

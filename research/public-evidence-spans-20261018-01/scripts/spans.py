"""Shared span helpers: passage index, block format and byte accounting (Python 3.12 stdlib).

The assembled context is a concatenation of blocks, one per whole passage:

    "[{n}] {fixture} {byte_start}-{byte_end} sha256:{first 12 hex}\\n" + passage + "\\n\\n"

Every byte of every label and separator counts against the budget. A passage is either
included whole or not at all: nothing is ever truncated.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET_BYTES = 2048
SEPARATOR = "\n\n"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_passages(root=ROOT):
    "Passages by id, each with its text read back from the fixture bytes and verified."
    index = json.loads((root / "fixtures" / "passages.json").read_text(encoding="utf-8"))
    files = {key: (root / meta["file"]).read_bytes() for key, meta in index["fixtures"].items()}
    for key, meta in index["fixtures"].items():
        if sha256(files[key]) != meta["sha256"]:
            raise ValueError(f"fixture {meta['file']} does not match its recorded sha256")
    keys = {meta["file"]: key for key, meta in index["fixtures"].items()}
    passages = {}
    for entry in index["passages"]:
        key = keys[entry["fixture"]]
        raw = files[key][entry["byte_start"] : entry["byte_end"]]
        if sha256(raw) != entry["sha256"]:
            raise ValueError(f"{entry['id']}: bytes at its offsets do not match its sha256")
        passages[entry["id"]] = {**entry, "fixture_key": key, "text": raw.decode("utf-8")}
    return passages


def label(n, passage):
    return f"[{n}] {passage['fixture_key']} {passage['byte_start']}-{passage['byte_end']} sha256:{passage['sha256'][:12]}\n"


def block(n, passage):
    return label(n, passage) + passage["text"] + SEPARATOR


def block_bytes(n, passage):
    return len(block(n, passage).encode("utf-8"))


def context_bytes(passages):
    "Bytes of the context made of these passages, numbered 1..k in the given order."
    return sum(block_bytes(n, p) for n, p in enumerate(passages, 1))

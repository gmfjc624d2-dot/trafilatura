#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Controlled label-swap run for request public-pdf-order-erratum-20261104-01.

Question: if two text labels are exchanged in an otherwise complete pypdf layout
debug trace while all numeric fields stay in place, what do the final
comparator's ``counts_match``, ``runs_with_tx_mismatch`` and per-row
``text_matches_run`` report?

Every controlled input is read exactly once into a buffer. The buffers are
hashed, a STARTED receipt is written and fsynced, and only then is the
comparator compiled from its retained source buffer and evaluated on the
retained input buffers. A RESULT receipt linked to STARTED is always written,
on failure too. Nothing re-opens the code or inputs after STARTED.

Launch through the bootstrap so the executed runner bytes are the hashed bytes
(the bootstrap reads this file once and executes that same buffer):

    python3 -I -c 'import sys;p=sys.argv[1];b=open(p,"rb").read();sys.argv=sys.argv[1:];exec(compile(b,p,"exec"),{"__name__":"__main__","__file__":p,"__builtins__":__builtins__,"RUNNER_BUFFER":b})' erratum_label_swap.py --out runs/erratum_20261104_label_swap
"""

from __future__ import annotations

import argparse
import ast
import copy
import datetime
import hashlib
import json
import os
import platform
import sys
import time
import traceback
import uuid
import warnings
from pathlib import Path
from typing import Any

REQUEST_ID = "public-pdf-order-erratum-20261104-01"
BOOTSTRAP = (
    'import sys;p=sys.argv[1];b=open(p,"rb").read();sys.argv=sys.argv[1:];'
    'exec(compile(b,p,"exec"),{"__name__":"__main__","__file__":p,'
    '"__builtins__":__builtins__,"RUNNER_BUFFER":b})'
)
FIXTURE = "D"
SWAP = (4, 5)  # D.r4 ' move the crate more than ' <-> D.r5 '12 cm.'
LABEL_KEYS = ("value", "text", "_raw_chars")
INPUTS = {
    "comparator_source": "order_compare.py",
    "trace_original": "runs/run3_final_ABCD/raw/D.pypdf_layout_debug.dir/tjs.json",
    "manifest": "fixtures/manifest.json",
    "run3_recorded_comparison": "runs/run3_final_ABCD/comparison.json",
}
SELECTED_FUNCTION = "compare_layout_tjs"
TRANSFORM_FUNCTION = "swap_text_labels"


def describe(path: str, data: bytes) -> dict[str, Any]:
    blob = hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()
    return {"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "git_blob_sha1": blob}


def function_segment(source: bytes, name: str) -> dict[str, Any]:
    text = source.decode("utf-8")
    node = next(n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.FunctionDef) and n.name == name)
    seg = ast.get_source_segment(text, node) or ""
    return {
        "name": name,
        "lines": [node.lineno, node.end_lineno],
        "segment_sha256": hashlib.sha256(seg.encode("utf-8")).hexdigest(),
    }


def swap_text_labels(records: list[dict[str, Any]], i: int, j: int, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Exchange the label fields of records i and j; every other field stays in place."""
    out = copy.deepcopy(records)
    for key in keys:
        out[i][key], out[j][key] = records[j][key], records[i][key]
    return out


def field_differences(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        keys = list(dict.fromkeys([*a, *b]))
        return [d for k in keys for d in field_differences(a.get(k), b.get(k), f"{path}.{k}")]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for idx, (x, y) in enumerate(zip(a, b, strict=True)) for d in field_differences(x, y, f"{path}[{idx}]")]
    return [] if a == b else [path or "."]


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


def write_synced(path: Path, data: bytes) -> None:
    with path.open("xb") as fh:  # never overwrite an existing record
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def encode(obj: Any) -> bytes:
    return (json.dumps(obj, indent=1, ensure_ascii=True) + "\n").encode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    mono_start = time.monotonic_ns()
    nonce = uuid.uuid4().hex
    modules_at_start = sorted(sys.modules)

    runner_buffer = globals().get("RUNNER_BUFFER")
    if isinstance(runner_buffer, bytes):
        runner_source = "bootstrap buffer: the bytes executed by this process"
    else:
        runner_buffer = Path(__file__).read_bytes()
        runner_source = "re-read of __file__ (not shown to equal the executed bytes)"

    # Each controlled input is opened exactly once, here.
    buffers = {key: Path(rel).read_bytes() for key, rel in INPUTS.items()}

    # Transform (in memory) and the variant's bytes.
    original_records = json.loads(buffers["trace_original"])
    serializer = "json.dumps(records, indent=2)"
    roundtrip_identical = json.dumps(original_records, indent=2).encode("utf-8") == buffers["trace_original"]
    variant_records = swap_text_labels(original_records, *SWAP, LABEL_KEYS)
    buffers["trace_variant"] = json.dumps(variant_records, indent=2).encode("utf-8")
    changed_fields = field_differences(original_records, variant_records)
    numeric_fields_unchanged = all(
        original_records[k][f] == variant_records[k][f]
        for k in range(len(original_records))
        for f in original_records[k]
        if f not in LABEL_KEYS
    )

    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "inputs").mkdir()
    preserved = {
        "trace_original": args.out / "inputs" / "D.tjs.original.json",
        "trace_variant": args.out / "inputs" / "D.tjs.variant_labels_r4_r5_swapped.json",
    }
    for key, path in preserved.items():
        write_synced(path, buffers[key])

    started = {
        "receipt_type": "STARTED",
        "request_id": REQUEST_ID,
        "receipt_id": uuid.uuid4().hex,
        "process_nonce": nonce,
        "started_at_utc": now_utc(),
        "interpreter": {
            "version": sys.version,
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
            "isolated_flag": bool(sys.flags.isolated),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "command": {
            "orig_argv": sys.orig_argv,
            "bootstrap_matches_documented": BOOTSTRAP in sys.orig_argv,
            "cwd_name": Path.cwd().name,
        },
        "runner": {
            **describe("erratum_label_swap.py", runner_buffer),
            "buffer_source": runner_source,
            "transform": function_segment(runner_buffer, TRANSFORM_FUNCTION),
        },
        "controlled_code": {
            **describe(INPUTS["comparator_source"], buffers["comparator_source"]),
            "selected_function": function_segment(buffers["comparator_source"], SELECTED_FUNCTION),
            "evaluated_from": "compile() of the retained buffer; the module file is not imported",
        },
        "inputs": {
            "trace_original": describe(INPUTS["trace_original"], buffers["trace_original"]),
            "trace_variant": {
                **describe("(generated in memory)", buffers["trace_variant"]),
                "preserved_copy": str(preserved["trace_variant"]),
            },
            "trace_original_preserved_copy": str(preserved["trace_original"]),
            "manifest": describe(INPUTS["manifest"], buffers["manifest"]),
            "run3_recorded_comparison": describe(INPUTS["run3_recorded_comparison"], buffers["run3_recorded_comparison"]),
        },
        "transform": {
            "function": TRANSFORM_FUNCTION,
            "fixture": FIXTURE,
            "swap_indexes": list(SWAP),
            "label_keys": list(LABEL_KEYS),
            "serializer": serializer,
            "serializer_reproduces_original_bytes": roundtrip_identical,
            "changed_fields": changed_fields,
            "numeric_and_other_fields_unchanged": numeric_fields_unchanged,
        },
        "planned_calls": [
            f"{SELECTED_FUNCTION}(json.loads(trace_original), json.loads(manifest), {FIXTURE!r})",
            f"{SELECTED_FUNCTION}(json.loads(trace_variant), json.loads(manifest), {FIXTURE!r})",
        ],
        "modules_loaded_before_evaluation": modules_at_start,
    }
    started_bytes = encode(started)
    started_path = args.out / "receipt_STARTED.json"
    write_synced(started_path, started_bytes)
    started_sha = hashlib.sha256(started_bytes).hexdigest()
    print(f"STARTED {started_sha} {started_path}", flush=True)

    # Evaluation on the retained buffers only.
    outcome, diagnostics, raw, summary = "failed", {}, {}, {}
    modules_before_eval = set(sys.modules)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            namespace: dict[str, Any] = {"__name__": "order_compare_from_buffer", "__builtins__": __builtins__}
            exec(compile(buffers["comparator_source"], INPUTS["comparator_source"], "exec"), namespace)
            compare = namespace[SELECTED_FUNCTION]
            manifest = json.loads(buffers["manifest"])
            original_trace = json.loads(buffers["trace_original"])
            variant_trace = json.loads(buffers["trace_variant"])
            raw = {
                "original": compare(original_trace, manifest, FIXTURE),
                "variant": compare(variant_trace, manifest, FIXTURE),
            }
            recorded = json.loads(buffers["run3_recorded_comparison"])[FIXTURE]["pypdf_layout_debug"]["tj_positions"]
            rows = zip(raw["original"]["rows"], raw["variant"]["rows"], variant_trace, strict=True)
            summary = {
                "original_equals_run3_recorded_tj_positions": raw["original"] == recorded,
                "counts_match": [raw["original"]["counts_match"], raw["variant"]["counts_match"]],
                "runs_with_tx_mismatch": [raw["original"]["runs_with_tx_mismatch"], raw["variant"]["runs_with_tx_mismatch"]],
                "rows": [
                    {
                        "run_id": o["run_id"],
                        "input_label_in_variant": rec["text"],
                        "text_matches_run": [o["text_matches_run"], v["text_matches_run"]],
                        "tx_matches": [o["tx_matches"], v["tx_matches"]],
                    }
                    for o, v, rec in rows
                ],
                "result_fields_that_differ": field_differences(raw["original"], raw["variant"]),
            }
            outcome = "completed"
        except Exception as exc:
            diagnostics["exception"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    diagnostics["python_warnings"] = [{"category": w.category.__name__, "message": str(w.message)} for w in caught]
    diagnostics["modules_imported_during_evaluation"] = sorted(set(sys.modules) - modules_before_eval)
    diagnostics["retained_buffers_rehashed_after_evaluation"] = {
        key: hashlib.sha256(buf).hexdigest() for key, buf in buffers.items()
    }

    result = {
        "receipt_type": "RESULT",
        "request_id": REQUEST_ID,
        "result_id": uuid.uuid4().hex,
        "process_nonce": nonce,
        "links": {
            "started_receipt_id": started["receipt_id"],
            "started_receipt_file": started_path.name,
            "started_receipt_sha256": started_sha,
        },
        "finished_at_utc": now_utc(),
        "elapsed_ns_since_process_start_of_main": time.monotonic_ns() - mono_start,
        "outcome": outcome,
        "summary": summary,
        "raw_results": raw,
        "diagnostics": diagnostics,
    }
    result_bytes = encode(result)
    result_path = args.out / "receipt_RESULT.json"
    write_synced(result_path, result_bytes)
    print(f"RESULT {hashlib.sha256(result_bytes).hexdigest()} {result_path} outcome={outcome}", flush=True)
    return 0 if outcome == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())

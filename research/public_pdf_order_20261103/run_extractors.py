#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run pinned pypdf (plain/layout) and pdfplumber (characters) on the fixtures.

Writes exact raw outputs, captured warnings/log records/stdout/stderr and
exceptions, then the comparison against fixtures/manifest.json. Refuses to
run with package versions other than the pins (no silent substitution).

    python -I run_extractors.py [--out runs/<name>]
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata as md
import inspect
import io
import json
import logging
import platform
import sys
import traceback
import warnings
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import order_compare  # noqa: E402
from generate_fixtures import dump_json  # noqa: E402

PINS = {"pypdf": "6.21.4", "pdfplumber": "0.11.9", "pdfminer.six": "20251230"}
CHAR_KEYS = ("text", "fontname", "size", "adv", "matrix", "x0", "x1", "y0", "y1",
             "top", "bottom", "width", "height", "upright")


def check_pins() -> dict[str, str]:
    found = {}
    for dist, want in PINS.items():
        try:
            found[dist] = md.version(dist)
        except md.PackageNotFoundError:
            found[dist] = "not installed"
    bad = {d: v for d, v in found.items() if v != PINS[d]}
    if bad:
        print(f"refusing to run: expected {PINS}, found {found}", file=sys.stderr)
        sys.exit(2)
    return found


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append({"logger": record.name, "level": record.levelname,
                             "message": record.getMessage()})


def capture(fn: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
    """Call fn, recording warnings, WARNING+ log records, stdout, stderr, exceptions."""
    handler = _ListHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    out, err = io.StringIO(), io.StringIO()
    info: dict[str, Any] = {"status": "ok"}
    value = None
    try:
        with warnings.catch_warnings(record=True) as caught, \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            warnings.simplefilter("always")
            try:
                value = fn()
            except Exception as exc:  # recorded as a failure case, not hidden
                info["status"] = "error"
                info["exception"] = {"type": type(exc).__name__, "message": str(exc),
                                     "traceback": traceback.format_exc()}
    finally:
        root.removeHandler(handler)
    info["python_warnings"] = [{"category": w.category.__name__, "message": str(w.message)}
                               for w in caught]
    info["log_records"] = handler.records
    info["stdout"] = out.getvalue()
    info["stderr"] = err.getvalue()
    return value, info


def pypdf_plain(path: Path) -> str:
    from pypdf import PdfReader
    return PdfReader(path).pages[0].extract_text()


def pypdf_layout(path: Path) -> str:
    from pypdf import PdfReader
    return PdfReader(path).pages[0].extract_text(extraction_mode="layout")


def pypdf_plain_visitor(path: Path) -> dict[str, Any]:
    """Auxiliary: pypdf plain-mode chunks with the matrices pypdf reports."""
    from pypdf import PdfReader
    chunks: list[dict[str, Any]] = []

    def visit(text: str, cm: Any, tm: Any, font: Any, size: Any) -> None:
        chunks.append({"text": text, "cm": [float(v) for v in cm], "tm": [float(v) for v in tm],
                       "font": None if font is None else str(font.get("/BaseFont")),
                       "font_size": float(size)})

    text = PdfReader(path).pages[0].extract_text(visitor_text=visit)
    return {"text": text, "chunks": chunks}


def pypdf_layout_debug(path: Path) -> dict[str, str]:
    """Auxiliary: pypdf's own layout-mode debug files (bts/tjs/bt_groups), verbatim."""
    import tempfile
    from pypdf import PdfReader
    with tempfile.TemporaryDirectory() as tmp:
        text = PdfReader(path).pages[0].extract_text(
            extraction_mode="layout", layout_mode_debug_path=Path(tmp))
        files = {p.name: p.read_text("utf-8") for p in sorted(Path(tmp).iterdir())}
    files["_extract_text_return.txt"] = text
    return files


def pdfplumber_chars(path: Path) -> list[dict[str, Any]]:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        out = []
        for c in pdf.pages[0].chars:
            rec = {k: (list(c[k]) if k == "matrix" else c[k]) for k in CHAR_KEYS}
            rec["origin"] = [c["matrix"][4], c["matrix"][5]]
            rec["advance"] = c["adv"]
            out.append(rec)
        return out


METHODS: dict[str, tuple[Callable[[Path], Any], str]] = {
    "pypdf_plain": (pypdf_plain, "txt"),
    "pypdf_layout": (pypdf_layout, "txt"),
    "pypdf_plain_visitor": (pypdf_plain_visitor, "json"),
    "pypdf_layout_debug": (pypdf_layout_debug, "dir"),
    "pdfplumber_chars": (pdfplumber_chars, "json"),
}


def environment(found: dict[str, str]) -> dict[str, Any]:
    from pypdf import PageObject
    dists = sorted((d.metadata["Name"], d.version) for d in md.distributions())
    lic = {}
    for name, _ in dists:
        meta = md.metadata(name)
        lic[name] = meta.get("License-Expression") or meta.get("License") or \
            "; ".join(v for v in (meta.get_all("Classifier") or []) if v.startswith("License"))
    return {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "libc": list(platform.libc_ver()),
        "pinned": found,
        "installed_distributions": dict(dists),
        "declared_licenses": lic,
        "pypdf_extract_text_signature": str(inspect.signature(PageObject.extract_text)),
        "isolated_mode": bool(sys.flags.isolated),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=HERE / "runs" / "local")
    parser.add_argument("--fixtures", type=Path, default=HERE / "fixtures")
    args = parser.parse_args(argv)
    found = check_pins()
    manifest = json.loads((args.fixtures / "manifest.json").read_text("ascii"))

    raw_dir = args.out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    runs: dict[str, Any] = {}
    comparison: dict[str, Any] = {}
    texts: dict[tuple[str, str], str] = {}
    for name, fx in manifest["fixtures"].items():
        pdf = args.fixtures / fx["file"]
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if sha != fx["pdf_sha256"]:
            print(f"{pdf}: sha256 {sha} != manifest {fx['pdf_sha256']}", file=sys.stderr)
            return 3
        runs[name] = {"pdf": fx["file"], "pdf_sha256": sha, "methods": {}}
        comparison[name] = {}
        for method, (fn, ext) in METHODS.items():
            value, info = capture(lambda fn=fn: fn(pdf))
            rel = f"raw/{name}.{method}.{ext}"
            if info["status"] == "ok" and ext == "dir":
                (args.out / rel).mkdir(parents=True, exist_ok=True)
                info["raw_files"] = {}
                for fname, content in value.items():
                    data = content.encode("utf-8")
                    (args.out / rel / fname).write_bytes(data)
                    info["raw_files"][f"{rel}/{fname}"] = hashlib.sha256(data).hexdigest()
            elif info["status"] == "ok":
                data = (value.encode("utf-8") if ext == "txt"
                        else (dump_json(value) + "\n").encode("utf-8"))
                (args.out / rel).write_bytes(data)
                info["raw_file"] = rel
                info["raw_sha256"] = hashlib.sha256(data).hexdigest()
                if ext == "txt":
                    info["raw_repr"] = repr(value)
                    texts[(name, method)] = value
            runs[name]["methods"][method] = info
            if info["status"] != "ok":
                comparison[name][method] = {"status": "extractor_error"}
                continue
            if method in ("pypdf_plain", "pypdf_layout"):
                comparison[name][method] = order_compare.compare_text(value, manifest, name)
            elif method == "pdfplumber_chars":
                comparison[name][method] = order_compare.compare_chars(value, manifest, name)
            elif method == "pypdf_layout_debug":
                comparison[name][method] = {
                    "auxiliary": True,
                    "return_equals_pypdf_layout":
                        value["_extract_text_return.txt"] == texts.get((name, "pypdf_layout")),
                    "tj_positions": order_compare.compare_layout_tjs(
                        json.loads(value["tjs.json"]), manifest, name)}
            else:
                comparison[name][method] = {
                    "auxiliary": True,
                    "text_equals_pypdf_plain": value["text"] == texts.get((name, "pypdf_plain"))}

    (args.out / "extraction_runs.json").write_text(dump_json(runs) + "\n", "utf-8")
    (args.out / "comparison.json").write_text(dump_json(comparison) + "\n", "utf-8")
    (args.out / "environment.json").write_text(dump_json(environment(found)) + "\n", "utf-8")

    for name, methods in comparison.items():
        for method, res in methods.items():
            if method in ("pypdf_plain", "pypdf_layout") and "token_sequence_equals" in res:
                lc = res.get("s1_limit_context", {})
                print(f"{name} {method:14s} tokens=declared:{res['token_sequence_equals']['declared']!s:5} "
                      f"drawing:{res['token_sequence_equals']['drawing']!s:5} "
                      f"sep_mismatch:{len(res.get('separators', {}).get('mismatches', [])) if 'separators' in res else 'n/a'} "
                      f"limit_with_negation(line/segment):"
                      f"{lc.get('same_line_as_negation')}/{lc.get('same_period_segment_as_negation')}")
            elif method == "pdfplumber_chars" and "all_checks_pass" in res:
                print(f"{name} {method:14s} geometry_ok:{res['all_checks_pass']} "
                      f"stream=drawing:{res['observed_order_equals']['drawing']} "
                      f"geo_sort=declared:{res['geometric_sort_of_observed_equals_declared']}")
            elif res.get("status") == "extractor_error":
                print(f"{name} {method}: EXTRACTOR ERROR")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render and extract the fixtures once with pinned tools; record raw outputs and checks.

Renderers: PDFium (pypdfium2) and Poppler pdftoppm, both at 144 dpi, compared as
raw RGB pixels and saved as PNG (lossless; the round trip is verified). Text:
pypdf plain/layout and content-stream operators, pdfplumber characters and
images, the PDFium text page and page objects (including the text render mode),
and Poppler pdftotext (plain, -layout, -bbox-layout). A tool that is missing or
has a different version than pinned is not run, and its checks are recorded as
``not_run`` with the missing condition.

    python3 -I run_tools.py --out runs/<name>
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import importlib.metadata as md
import io
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import layer_compare as lc  # noqa: E402
from generate_fixtures import FONT  # noqa: E402

PINS = {"pypdf": "6.21.4", "pdfplumber": "0.11.9", "pdfminer.six": "20251230", "pypdfium2": "5.14.0", "pillow": "13.0.0"}
POPPLER = "24.02.0"
SCALE, DPI = 2, 144
NEEDS = {
    "pdfium_render": ["pypdfium2", "pillow"],
    "pdfium_text": ["pypdfium2"],
    "pypdf_text": ["pypdf"],
    "pdfplumber_text": ["pdfplumber", "pdfminer.six", "pillow"],
    "poppler_render": ["pdftoppm", "pillow"],
    "poppler_text": ["pdftotext"],
}


# ---------------------------------------------------------------------------
# Availability and capture
# ---------------------------------------------------------------------------


def availability() -> dict[str, dict[str, Any]]:
    installed = {d.metadata["Name"].lower(): d.version for d in md.distributions()}
    out = {d: {"expected": v, "found": installed.get(d.lower())} for d, v in PINS.items()}
    for tool in ("pdftoppm", "pdftotext"):
        found = None
        if shutil.which(tool):
            proc = subprocess.run([tool, "-v"], capture_output=True, text=True, check=False)
            m = re.search(r"version (\S+)", proc.stderr + proc.stdout)
            found = m.group(1) if m else "unparsed"
        out[tool] = {"expected": POPPLER, "found": found}
    for rec in out.values():
        rec["ok"] = rec["found"] == rec["expected"]
    return out


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.items: list[dict[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.items.append({"logger": record.name, "level": record.levelname, "message": record.getMessage()})


def capture(fn: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
    handler = _Records()
    logging.getLogger().addHandler(handler)
    out, err = io.StringIO(), io.StringIO()
    info: dict[str, Any] = {"status": "ok"}
    value = None
    try:
        with warnings.catch_warnings(record=True) as caught, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            warnings.simplefilter("always")
            try:
                value = fn()
            except Exception as exc:
                info["status"] = "error"
                info["exception"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    finally:
        logging.getLogger().removeHandler(handler)
    info["python_warnings"] = [{"category": w.category.__name__, "message": str(w.message)} for w in caught]
    info["log_records"] = handler.items
    info["stdout"], info["stderr"] = out.getvalue(), err.getvalue()
    return value, info


def run_cli(argv: list[str], shown: list[str]) -> dict[str, Any]:
    proc = subprocess.run(argv, capture_output=True, check=False)
    return {
        "argv": shown,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr.decode("utf-8", "replace"),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def pdfium_render(path: Path) -> dict[str, Any]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(path)
    try:
        page = pdf[0]
        bm = page.render(scale=SCALE, rev_byteorder=True)
        w, h, n, stride = bm.width, bm.height, bm.n_channels, bm.stride
        buf = bytes(bm.buffer)
        rows = b"".join(buf[y * stride : y * stride + w * n] for y in range(h))
        if n == 4:  # drop alpha/padding channel
            rows = b"".join(rows[i : i + 3] for i in range(0, len(rows), 4))
        return {
            "width": w,
            "height": h,
            "pixels": rows,
            "native_channels": n,
            "mode": "RGB",
            "options": {"scale": SCALE, "rev_byteorder": True, "smoothing": "pypdfium2 defaults"},
        }
    finally:
        pdf.close()


def poppler_render(path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        prefix = Path(tmp) / "page"
        cli = run_cli(
            ["pdftoppm", "-r", str(DPI), "-singlefile", str(path), str(prefix)],
            ["pdftoppm", "-r", str(DPI), "-singlefile", str(path), "<tmp>/page"],
        )
        data = (Path(tmp) / "page.ppm").read_bytes() if cli["returncode"] == 0 else b""
    cli.pop("stdout")
    if not data:
        raise RuntimeError(f"pdftoppm failed: {cli}")
    m = re.match(rb"P6\s+(\d+)\s+(\d+)\s+(\d+)\s", data)
    w, h, maxval = (int(v) for v in m.groups())
    assert maxval == 255
    return {"width": w, "height": h, "pixels": data[m.end() :], "mode": "RGB", "cli": cli}


def pypdf_text(path: Path) -> dict[str, Any]:
    from pypdf import PdfReader
    from pypdf.generic import ContentStream

    reader = PdfReader(path)
    page = reader.pages[0]
    ops = [
        [op.decode("latin-1"), [str(o) for o in operands]]
        for operands, op in ContentStream(page.get_contents(), reader).operations
    ]
    return {"plain": page.extract_text(), "layout": page.extract_text(extraction_mode="layout"), "operations": ops}


def pdfplumber_text(path: Path) -> dict[str, Any]:
    import pdfplumber

    keys = ("text", "fontname", "size", "x0", "x1", "y0", "y1", "top", "bottom", "matrix")
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        chars = [{k: (list(c[k]) if k == "matrix" else c[k]) for k in keys} for c in page.chars]
        images = [
            {
                k: (list(im[k]) if isinstance(im[k], tuple) else im[k])
                for k in ("x0", "x1", "top", "bottom", "srcsize", "bits", "name")
                if k in im
            }
            for im in page.images
        ]
        return {"chars": chars, "images": images, "extract_text": page.extract_text()}


def pdfium_text(path: Path) -> dict[str, Any]:
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    pdf = pdfium.PdfDocument(path)
    try:
        page = pdf[0]
        tp = page.get_textpage()
        chars = []
        for i in range(tp.count_chars()):
            x, y = ctypes.c_double(), ctypes.c_double()
            raw.FPDFText_GetCharOrigin(tp.raw, i, ctypes.byref(x), ctypes.byref(y))
            obj = raw.FPDFText_GetTextObject(tp.raw, i)
            chars.append(
                {
                    "index": i,
                    "text": chr(raw.FPDFText_GetUnicode(tp.raw, i)),
                    "generated": raw.FPDFText_IsGenerated(tp.raw, i),
                    "box": list(tp.get_charbox(i)),
                    "loose_box": list(tp.get_charbox(i, loose=True)),
                    "origin": [x.value, y.value],
                    "font_size": raw.FPDFText_GetFontSize(tp.raw, i),
                    "render_mode": raw.FPDFTextObj_GetTextRenderMode(obj) if obj else None,
                }
            )
        objects = []
        for obj in page.get_objects():
            rec = {"type": obj.type, "pos": list(obj.get_pos())}
            if obj.type == raw.FPDF_PAGEOBJ_TEXT:
                rec["render_mode"] = raw.FPDFTextObj_GetTextRenderMode(obj.raw)
            objects.append(rec)
        return {
            "text": tp.get_text_range(),
            "chars": chars,
            "objects": objects,
            "constants": {
                "FPDF_PAGEOBJ_TEXT": raw.FPDF_PAGEOBJ_TEXT,
                "FPDF_PAGEOBJ_IMAGE": raw.FPDF_PAGEOBJ_IMAGE,
                "FPDF_TEXTRENDERMODE_FILL": raw.FPDF_TEXTRENDERMODE_FILL,
                "FPDF_TEXTRENDERMODE_INVISIBLE": raw.FPDF_TEXTRENDERMODE_INVISIBLE,
            },
        }
    finally:
        pdf.close()


def poppler_text(path: Path) -> dict[str, Any]:
    out = {}
    for name, extra in (("plain", []), ("layout", ["-layout"]), ("bbox_layout", ["-bbox-layout"])):
        argv = ["pdftotext", "-enc", "UTF-8", *extra, str(path), "-"]
        cli = run_cli(argv, argv)
        out[name] = {
            "argv": cli["argv"],
            "returncode": cli["returncode"],
            "stderr": cli["stderr"],
            "text": cli["stdout"].decode("utf-8"),
        }
    words = [
        {"text": m.group(5), "box": [float(m.group(1)), 792 - float(m.group(4)), float(m.group(3)), 792 - float(m.group(2))]}
        for m in re.finditer(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', out["bbox_layout"]["text"]
        )
    ]
    out["words_pdf_coords"] = words
    return out


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def check(
    results: list[dict[str, Any]],
    cid: str,
    pred: str,
    desc: str,
    expected: Any,
    observed: Any,
    ok: bool | None,
    missing: str | None = None,
) -> None:
    status = "not_run" if missing else ("observed" if ok is None else ("pass" if ok else "fail"))
    results.append(
        {
            "check_id": cid,
            "prediction": pred,
            "description": desc,
            "expected": expected,
            "observed": observed,
            "status": status,
            "missing_condition": missing,
        }
    )


def items_from(tool: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    if tool == "pdfplumber":
        return [{"text": c["text"], "center": [(c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2]} for c in data["chars"]]
    if tool == "pdfium":
        return [
            {
                "text": c["text"],
                "center": [(c["loose_box"][0] + c["loose_box"][2]) / 2, (c["loose_box"][1] + c["loose_box"][3]) / 2],
            }
            for c in data["chars"]
            if c["generated"] != 1
        ]
    return [
        {"text": w["text"], "unit": "word", "center": [(w["box"][0] + w["box"][2]) / 2, (w["box"][1] + w["box"][3]) / 2]}
        for w in data["words_pdf_coords"]
    ]


def analyze(manifest: dict[str, Any], renders: dict, texts: dict, missing: dict[str, str]) -> list[dict[str, Any]]:
    res: list[dict[str, Any]] = []
    cells = manifest["visible_truth"]["cells"]
    wrong = manifest["hidden_text"]["wrong_cell"]
    hidden_c = {
        c["cell_id"]: (wrong["searchable"] if (c["row"], c["col"]) == (wrong["row"], wrong["col"]) else c["text"])
        for c in cells
    }
    ink = read_pbm(HERE / "fixtures" / manifest["raster"]["file"])
    pl = manifest["raster"]["placed_at_pt"]
    origin_px = (pl["x"] * SCALE, (792 - (pl["y"] + pl["h"])) * SCALE)
    text_boxes_px = [lc.pt_box_to_px(c["text_box_pt"], pad_pt=1) for c in cells]

    # Visible truth from the authored raster itself (method self-check).
    raster_render = lc.raster_as_render(ink, origin_px)
    dec = {c["cell_id"]: lc.decode_cell(raster_render, c, FONT)["decoded"] for c in cells}
    check(
        res,
        "truth.raster_decode",
        "P13 (method)",
        "exact template decode of the authored raster",
        {c["cell_id"]: c["text"] for c in cells},
        dec,
        dec == {c["cell_id"]: c["text"] for c in cells},
    )

    for rname, label, preds in (
        ("pdfium", "PDFium", ("P1", "P2", "P3", "P4", "P7")),
        ("poppler", "Poppler", ("P5", "P5", "P5", "P5", "P7")),
    ):
        miss = missing.get(f"{rname}_render")
        rr = renders.get(rname, {})

        def d(a: str, b: str, rr: dict = rr) -> dict[str, Any]:
            return lc.diff_pixels(rr[a], rr[b])

        if miss:
            for cid in ("B_eq_C", "B_eq_D", "E_ne_B", "B_region_eq_raster", "A_ne_B", "decode_C"):
                check(res, f"{rname}.{cid}", "-", f"{label} {cid}", None, None, None, miss)
            continue
        bc, bd, be, ab = d("B", "C"), d("B", "D"), d("B", "E"), d("A", "B")
        conf = lc.confined(be.pop("_coords", []), text_boxes_px)
        for x in (bc, bd, ab):
            x.pop("_coords", None)
        check(res, f"{rname}.B_eq_C", preds[0], f"{label}: render(B) == render(C)", True, bc, bc.get("identical") is True)
        check(res, f"{rname}.B_eq_D", preds[1], f"{label}: render(B) == render(D)", True, bd, bd.get("identical") is True)
        check(
            res,
            f"{rname}.E_ne_B",
            preds[2],
            f"{label}: render(E) != render(B), diffs inside text cells (+1 pt)",
            {"identical": False, "outside_count": 0},
            {**be, "confinement": conf},
            be.get("identical") is False and conf["outside_count"] == 0,
        )
        reg = {f: lc.raster_region_check(rr[f], ink, origin_px) for f in ("B", "C", "D")}
        check(
            res,
            f"{rname}.B_region_eq_raster",
            preds[3],
            f"{label}: image rectangle == authored raster, rest white",
            {"exact": True},
            reg,
            all(r["exact"] for r in reg.values()),
        )
        check(res, f"{rname}.A_ne_B", preds[4], f"{label}: render(A) != render(B)", False, ab, ab.get("identical") is False)
        decoded = {f: {c["cell_id"]: lc.decode_cell(rr[f], c, FONT) for c in cells} for f in ("B", "C", "D", "E")}
        got_c = {k: v["decoded"] for k, v in decoded["C"].items()}
        check(
            res,
            f"{rname}.decode_C",
            "P13",
            f"{label}: exact template decode of render(C) == visible truth",
            {c["cell_id"]: c["text"] for c in cells},
            {"C": got_c, "all_fixtures": decoded},
            got_c == {c["cell_id"]: c["text"] for c in cells},
        )

    if missing.get("pdfium_render") or missing.get("poppler_render"):
        check(
            res,
            "cross.pdfium_vs_poppler_B",
            "P6",
            "PDFium vs Poppler render(B)",
            "no prediction",
            None,
            None,
            missing.get("pdfium_render") or missing.get("poppler_render"),
        )
    else:
        x = lc.diff_pixels(renders["pdfium"]["B"], renders["poppler"]["B"])
        x.pop("_coords", None)
        check(res, "cross.pdfium_vs_poppler_B", "P6", "PDFium vs Poppler render(B)", "no prediction", x, None)

    # Text presence (P8, P9) for every extractor.
    extractors = {
        "pypdf_plain": ("pypdf_text", lambda t: t["plain"]),
        "pypdf_layout": ("pypdf_text", lambda t: t["layout"]),
        "pdfplumber_text": ("pdfplumber_text", lambda t: t["extract_text"]),
        "pdfium_text": ("pdfium_text", lambda t: t["text"]),
        "poppler_plain": ("poppler_text", lambda t: t["plain"]["text"]),
        "poppler_layout": ("poppler_text", lambda t: t["layout"]["text"]),
    }
    for ename, (tool, get) in extractors.items():
        miss = missing.get(tool)
        if miss:
            check(res, f"{ename}.presence", "P8/P9", f"{ename} text presence", None, None, None, miss)
            continue
        got = {f: get(texts[tool][f]) for f in "ABCDE"}
        nonspace = {f: len(re.sub(r"\s", "", v or "")) for f, v in got.items()}
        a_ok = all(c["text"] in got["A"] for c in cells)
        b_ok = nonspace["B"] == 0
        c_ok = all(v in got["C"] for v in hidden_c.values()) and "12 mm" not in got["C"]
        d_ok = all(c["text"] in got["D"] for c in cells)
        check(
            res,
            f"{ename}.presence",
            "P8/P9",
            f"{ename}: B empty; A and D contain the authored strings; C contains the hidden strings incl. 17 mm",
            {"B_nonspace": 0, "A": True, "C": True, "D": True},
            {"nonspace_chars": nonspace, "A": a_ok, "C": c_ok, "D": d_ok, "raw_repr": {f: repr(v) for f, v in got.items()}},
            a_ok and b_ok and c_ok and d_ok,
        )

    # Render mode (P10).
    if missing.get("pdfium_text") or missing.get("pypdf_text"):
        check(
            res, "render_mode", "P10", "render mode", None, None, None, missing.get("pdfium_text") or missing.get("pypdf_text")
        )
    else:
        modes = {
            f: sorted({o["render_mode"] for o in texts["pdfium_text"][f]["objects"] if "render_mode" in o}) for f in "ABCDE"
        }
        trs = {f: [ops[1] for ops in texts["pypdf_text"][f]["operations"] if ops[0] == "Tr"] for f in "ABCDE"}
        want_modes = {"A": [0], "B": [], "C": [3], "D": [3], "E": [0]}
        want_trs = {"A": [["0"]], "B": [], "C": [["3"]], "D": [["3"]], "E": [["0"]]}
        check(
            res,
            "render_mode",
            "P10",
            "PDFium per-object render mode and pypdf Tr operators",
            {"pdfium": want_modes, "pypdf_Tr": want_trs},
            {"pdfium": modes, "pypdf_Tr": trs},
            modes == want_modes and trs == want_trs,
        )

    # Geometry: coverage of the visible '2' by the wrong '7' (P11); C vs D geometry (P12).
    cell = next(c for c in cells if (c["row"], c["col"]) == (wrong["row"], wrong["col"]))
    glyph2 = cell["glyphs"][1]
    baseline = cell["origin_pt"][1]
    boxes: dict[str, Any] = {}
    if not missing.get("pdfplumber_text"):
        ch = [
            c
            for c in texts["pdfplumber_text"]["C"]["chars"]
            if c["text"] == "7" and abs((c["x0"] + c["x1"]) / 2 - (glyph2["box_pt"][0] + 3)) < 3
        ]
        if ch:
            boxes["pdfplumber_char"] = [ch[0]["x0"], ch[0]["y0"], ch[0]["x1"], ch[0]["y1"]]
    if not missing.get("pdfium_text"):
        ch = [
            c for c in texts["pdfium_text"]["C"]["chars"] if c["text"] == "7" and abs(c["origin"][0] - glyph2["box_pt"][0]) < 1
        ]
        if ch:
            boxes["pdfium_tight"] = ch[0]["box"]
            boxes["pdfium_loose"] = ch[0]["loose_box"]
    if not missing.get("poppler_text"):
        wd = [w for w in texts["poppler_text"]["C"]["words_pdf_coords"] if w["text"] == "17"]
        if wd:
            boxes["poppler_word_17"] = wd[0]["box"]
    cov = {k: round(lc.ink_coverage(glyph2, baseline, FONT, b), 6) for k, b in boxes.items()}
    check(
        res,
        "geometry.coverage_7_over_2",
        "P11",
        "share of the visible '2' ink inside each box reported for the wrong '7'",
        ">= 0.95 for every box",
        {"boxes": boxes, "coverage": cov},
        bool(cov) and all(v >= 0.95 for v in cov.values()),
    )

    if not missing.get("pdfplumber_text"):
        cc, dd = texts["pdfplumber_text"]["C"]["chars"], texts["pdfplumber_text"]["D"]["chars"]
        geo_eq = len(cc) == len(dd) and all(
            {k: v for k, v in a.items() if k != "text"} == {k: v for k, v in b.items() if k != "text"}
            for a, b in zip(cc, dd, strict=False)
        )
        tdiff = [[i, a["text"], b["text"]] for i, (a, b) in enumerate(zip(cc, dd, strict=False)) if a["text"] != b["text"]]
        check(
            res,
            "geometry.C_vs_D.pdfplumber",
            "P12",
            "pdfplumber: C and D chars identical except text at one index",
            {"geometry_identical": True, "text_differences": 1},
            {"counts": [len(cc), len(dd)], "geometry_identical": geo_eq, "text_differences": tdiff},
            geo_eq and len(tdiff) == 1,
        )
    if not missing.get("pdfium_text"):
        cc, dd = texts["pdfium_text"]["C"]["chars"], texts["pdfium_text"]["D"]["chars"]
        same = len(cc) == len(dd)
        per = {
            k: same and all(a[k] == b[k] for a, b in zip(cc, dd, strict=False))
            for k in ("box", "loose_box", "origin", "render_mode", "font_size", "generated")
        }
        tdiff = [[i, a["text"], b["text"]] for i, (a, b) in enumerate(zip(cc, dd, strict=False)) if a["text"] != b["text"]]
        check(
            res,
            "geometry.C_vs_D.pdfium",
            "P12",
            "PDFium: C and D chars identical except text at one index",
            dict.fromkeys(per, True) | {"text_differences": 1},
            {"counts": [len(cc), len(dd)], "fields_identical": per, "text_differences": tdiff},
            all(per.values()) and len(tdiff) == 1,
        )

    # Text layer vs visible truth per cell (P14).
    for tool in ("pdfplumber", "pdfium", "poppler"):
        tkey = f"{tool}_text"
        if missing.get(tkey):
            check(res, f"cells.{tool}", "P14", f"{tool}: cell strings vs visible truth", None, None, None, missing[tkey])
            continue
        per = {f: lc.assign_to_cells(items_from(tool, texts[tkey][f]), cells) for f in "ACDE"}
        mism = {f: lc.cell_mismatches(per[f]["cell_strings"], cells) for f in per}
        unassigned = {f: [u["text"] for u in per[f]["unassigned"]] for f in per}
        ok = [m["cell_id"] for m in mism["C"]] == ["r1c1"] and not mism["D"] and not mism["A"]
        check(
            res,
            f"cells.{tool}",
            "P14",
            f"{tool}: cell strings (by geometry) vs visible truth",
            {"A": [], "C": ["r1c1"], "D": []},
            {"mismatches": mism, "cell_strings": {f: p["cell_strings"] for f, p in per.items()}, "unassigned": unassigned},
            ok,
        )

    # P15: derived from the checks above (no separate tool run).
    by = {r["check_id"]: r["status"] for r in res}
    deps = [
        k
        for k in by
        if k.startswith(("render_mode", "geometry.C_vs_D", "pdfium.decode_C", "cells.")) or k.endswith(".presence")
    ]
    check(
        res,
        "derived.P15",
        "P15",
        "presence/geometry/render mode do not separate C from D; only image evidence shows the visible value",
        "all dependency checks pass",
        {k: by[k] for k in deps},
        all(by[k] == "pass" for k in deps) if deps else None,
        None if deps else "no dependency checks ran",
    )
    return res


def read_pbm(path: Path) -> list[list[int]]:
    data = path.read_bytes()
    m = re.match(rb"P4\s+(\d+)\s+(\d+)\s", data)
    w, h = int(m.group(1)), int(m.group(2))
    body, rowbytes = data[m.end() :], (w + 7) // 8
    return [[(body[y * rowbytes + x // 8] >> (7 - x % 8)) & 1 for x in range(w)] for y in range(h)]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def environment(avail: dict[str, Any]) -> dict[str, Any]:
    env: dict[str, Any] = {
        "label": "actual tool run on this platform; fixtures are generated test inputs",
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "libc": list(platform.libc_ver()),
        "isolated_flag": bool(sys.flags.isolated),
        "tools": avail,
    }
    lic = {}
    for name in PINS:
        with contextlib.suppress(md.PackageNotFoundError):
            meta = md.metadata(name)
            lic[name] = (
                meta.get("License-Expression")
                or meta.get("License")
                or "; ".join(v for v in (meta.get_all("Classifier") or []) if v.startswith("License"))
            )
    env["python_package_licenses"] = lic
    with contextlib.suppress(Exception):
        import pypdfium2

        env["pdfium"] = {"pypdfium2": str(pypdfium2.version.PYPDFIUM_INFO), "pdfium": str(pypdfium2.version.PDFIUM_INFO)}
    deb = Path("/usr/share/doc/poppler-utils/copyright")
    if deb.is_file():
        text = deb.read_text("utf-8", "replace")
        env["poppler_utils_copyright"] = {
            "file": str(deb),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "license_fields": sorted(set(re.findall(r"^License: (.+)$", text, re.MULTILINE))),
        }
    if shutil.which("dpkg-query"):
        proc = subprocess.run(
            ["dpkg-query", "-W", "-f", "${Version}", "poppler-utils"], capture_output=True, text=True, check=False
        )
        env["poppler_utils_package_version"] = proc.stdout or None
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out = args.out.resolve()
    os.chdir(HERE)  # fixture paths and recorded CLI argv stay relative to this directory
    manifest = json.loads((HERE / "fixtures" / "manifest.json").read_text("ascii"))
    avail = availability()
    missing = {}
    for tool, needs in NEEDS.items():
        bad = [n for n in needs if not avail[n]["ok"]]
        if bad:
            missing[tool] = "; ".join(f"{n}: expected {avail[n]['expected']}, found {avail[n]['found']}" for n in bad)

    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "raw").mkdir()
    (args.out / "renders").mkdir()
    tool_runs: dict[str, Any] = {"missing_conditions": missing, "fixtures": {}}
    renders: dict[str, dict[str, Any]] = {"pdfium": {}, "poppler": {}}
    texts: dict[str, dict[str, Any]] = {k: {} for k in ("pypdf_text", "pdfplumber_text", "pdfium_text", "poppler_text")}
    render_index: dict[str, Any] = {}
    for name, fx in manifest["fixtures"].items():
        pdf = Path("fixtures") / fx["file"]
        sha = hashlib.sha256((HERE / pdf).read_bytes()).hexdigest()
        if sha != fx["pdf_sha256"]:
            print(f"{pdf}: sha256 {sha} != manifest", file=sys.stderr)
            return 3
        rec: dict[str, Any] = {"pdf": str(pdf), "pdf_sha256": sha, "runs": {}}
        for tool, fn in (
            ("pdfium_render", pdfium_render),
            ("poppler_render", poppler_render),
            ("pypdf_text", pypdf_text),
            ("pdfplumber_text", pdfplumber_text),
            ("pdfium_text", pdfium_text),
            ("poppler_text", poppler_text),
        ):
            if tool in missing:
                rec["runs"][tool] = {"status": "not_run", "missing_condition": missing[tool]}
                continue
            value, info = capture(lambda fn=fn, pdf=pdf: fn(pdf))
            rec["runs"][tool] = info
            if info["status"] != "ok":
                missing.setdefault(tool, f"{tool} raised on {name}")
                continue
            if tool.endswith("_render"):
                rname = tool.split("_")[0]
                cli = value.pop("cli", None)
                if cli:
                    info["cli"] = cli
                renders[rname][name] = value
                png = args.out / "renders" / f"{name}.{rname}.png"
                from PIL import Image

                Image.frombytes("RGB", (value["width"], value["height"]), value["pixels"]).save(png, format="PNG")
                back = Image.open(png)
                render_index[f"{name}.{rname}"] = {
                    "size": [value["width"], value["height"]],
                    "mode": value["mode"],
                    "pixel_sha256": hashlib.sha256(value["pixels"]).hexdigest(),
                    "png": png.relative_to(args.out).as_posix(),
                    "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
                    "png_roundtrip_lossless": back.mode == "RGB" and back.tobytes() == value["pixels"],
                    **{k: v for k, v in value.items() if k not in ("pixels", "width", "height", "mode")},
                }
            else:
                texts[tool][name] = value
                (args.out / "raw" / f"{name}.{tool}.json").write_text(
                    json.dumps(value, indent=1, ensure_ascii=True) + "\n", "ascii"
                )
                for key in ("plain", "layout"):
                    if tool == "pypdf_text":
                        (args.out / "raw" / f"{name}.pypdf_{key}.txt").write_bytes(value[key].encode("utf-8"))
                    if tool == "poppler_text":
                        (args.out / "raw" / f"{name}.pdftotext_{key}.txt").write_bytes(value[key]["text"].encode("utf-8"))
                if tool == "poppler_text":
                    (args.out / "raw" / f"{name}.pdftotext_bbox_layout.html").write_bytes(
                        value["bbox_layout"]["text"].encode("utf-8")
                    )
        tool_runs["fixtures"][name] = rec

    checks: list[dict[str, Any]] = []
    analysis_error = None
    try:
        checks = analyze(manifest, renders, texts, missing)
    except Exception:
        analysis_error = traceback.format_exc()
    (args.out / "tool_runs.json").write_text(json.dumps(tool_runs, indent=1, ensure_ascii=True) + "\n", "ascii")
    (args.out / "render_index.json").write_text(json.dumps(render_index, indent=1, ensure_ascii=True) + "\n", "ascii")
    (args.out / "checks.json").write_text(
        json.dumps({"analysis_error": analysis_error, "checks": checks}, indent=1, ensure_ascii=True) + "\n", "ascii"
    )
    (args.out / "environment.json").write_text(json.dumps(environment(avail), indent=1, ensure_ascii=True) + "\n", "ascii")
    for c in checks:
        print(f"{c['status']:8s} {c['prediction']:12s} {c['check_id']}")
    if analysis_error:
        print(analysis_error, file=sys.stderr)
    statuses = {c["status"] for c in checks}
    print(f"checks: {len(checks)}; " + ", ".join(f"{s}={sum(c['status'] == s for c in checks)}" for s in sorted(statuses)))
    return 1 if analysis_error else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Part of a standalone research directory inside a fork of Trafilatura
# (Apache-2.0). Not imported by the trafilatura package.
"""Deterministic generator for the public_pdf_order_20261103 fixture family.

All text is fictional and authored for this fixture. The PDFs are written by
hand, byte for byte, without any PDF library, so the generator (and therefore
the expected geometry) does not depend on any extractor under test.

Fixtures (one page each, 612 x 792 pt, all text at 10 pt):

A  ordinary drawing order, one Courier run per line.
B  same characters and glyph origins as A; the negation "not" is drawn with
   Courier-Bold and the word "closed" is split across two font runs
   ("clo" in Courier, "sed" in Courier-Oblique). Runs inside a line continue
   by the implicit glyph advance; no extra positioning operators are added.
C  same font runs and glyph origins as B, but the final measurement suffix of
   the first sentence ("12 cm.") is painted after the second sentence, with an
   explicit Tm placing it at its original coordinates.
D  added after the initial A/B/C run (see REPORT.md and runs/run1_ABC): same
   font runs, glyph origins and drawing order as B, but the suffix "12 cm." is
   a separate run placed by the same explicit Tm as in C. B/D is one
   equivalent operator pair (implicit advance vs explicit Tm to the same
   origin); C/D differ only in drawing order.

Glyph positions are derived from declared metrics only:

    advance = (Widths[code - FirstChar] / 1000 * font_size + Tc + Tw') * Tz / 100

with Widths = 600 for every code 32..126 in all three fonts, font_size = 10,
and the PDF initial text state Tc = 0, Tw = 0, Tz = 100, Ts = 0 (no text-state
operators are emitted), so every glyph advances by exactly 6.0 pt.

Usage:
    python generate_fixtures.py            # (re)write fixtures/
    python generate_fixtures.py --check    # verify fixtures/ is byte-identical
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REQUEST_ID = "public-styled-prose-fixture-20261103-01"
MANIFEST_VERSION = 1
HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "fixtures"

# ---------------------------------------------------------------------------
# Declared page, text state and font metrics
# ---------------------------------------------------------------------------

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
FONT_SIZE = 10
FIRST_CHAR = 32
LAST_CHAR = 126
GLYPH_WIDTH = 600  # glyph-space units (1/1000 of text space), every code
# PDF 32000-1 9.3.1 initial text state; no operator in the fixtures changes it.
TEXT_STATE = {"Tc": 0, "Tw": 0, "Tz": 100, "TL": 0, "Ts": 0, "Tr": 0}

FONTS: dict[str, dict[str, str]] = {
    "F1": {"BaseFont": "Courier", "style": "regular"},
    "F2": {"BaseFont": "Courier-Bold", "style": "bold"},
    "F3": {"BaseFont": "Courier-Oblique", "style": "oblique"},
}
ENCODING = "WinAnsiEncoding"
# Characters used by the fixture text. For these codes WinAnsiEncoding,
# StandardEncoding and ASCII agree, so the code is the ASCII value.
ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,:"
)


def glyph_advance(char: str) -> float:
    """Horizontal advance in user space (pt) from the declared metrics."""
    code = ord(char)
    if not FIRST_CHAR <= code <= LAST_CHAR:
        raise ValueError(f"code {code} outside declared FirstChar..LastChar")
    w0 = GLYPH_WIDTH / 1000.0
    tw = TEXT_STATE["Tw"] if code == 32 else 0
    return (w0 * FONT_SIZE + TEXT_STATE["Tc"] + tw) * TEXT_STATE["Tz"] / 100.0


# ---------------------------------------------------------------------------
# Declared structure (the fixture author's intent; not inferred from text)
# ---------------------------------------------------------------------------
# Token spec: " " is a space token. Other tokens are
# (text, kind, clause_id, roles, measurement_id).

S1_SPEC: list[Any] = [
    ("If", "word", "S1.cl1", ["condition", "condition_marker"], None), " ",
    ("the", "word", "S1.cl1", ["condition"], None), " ",
    ("blue", "word", "S1.cl1", ["condition"], None), " ",
    ("latch", "word", "S1.cl1", ["condition"], None), " ",
    ("is", "word", "S1.cl1", ["condition"], None), " ",
    ("closed", "word", "S1.cl1", ["condition"], None),
    (",", "punct", None, ["clause_boundary"], None), " ",
    ("do", "word", "S1.cl2", ["auxiliary"], None), " ",
    ("not", "word", "S1.cl2", ["negation"], None), " ",
    ("move", "word", "S1.cl2", [], None), " ",
    ("the", "word", "S1.cl2", [], None), " ",
    ("crate", "word", "S1.cl2", [], None), " ",
    ("more", "word", "S1.cl2", ["comparator"], None), " ",
    ("than", "word", "S1.cl2", ["comparator"], None), " ",
    ("12", "number", "S1.cl2", ["number"], "S1.m1"), " ",
    ("cm", "word", "S1.cl2", ["unit"], "S1.m1"),
    (".", "punct", None, ["sentence_terminal"], None),
]
S2_SPEC: list[Any] = [
    ("The", "word", "S2.cl1", [], None), " ",
    ("green", "word", "S2.cl1", [], None), " ",
    ("lamp", "word", "S2.cl1", [], None), " ",
    ("remains", "word", "S2.cl1", [], None), " ",
    ("on", "word", "S2.cl1", [], None),
    (".", "punct", None, ["sentence_terminal"], None),
]
R1_SPEC: list[Any] = [
    ("Span", "word", "R1.label", ["label"], None),
    (":", "punct", "R1.label", ["label_delimiter"], None), " ",
    ("12", "number", "R1.value", ["value", "number"], "R1.m1"), " ",
    ("cm", "word", "R1.value", ["value", "unit"], "R1.m1"),
]
R2_SPEC: list[Any] = [
    ("Delay", "word", "R2.label", ["label"], None),
    (":", "punct", "R2.label", ["label_delimiter"], None), " ",
    ("7", "number", "R2.value", ["value", "number"], "R2.m1"), " ",
    ("s", "word", "R2.value", ["value", "unit"], "R2.m1"),
]

BLOCKS: list[dict[str, Any]] = [
    {"block_id": "S1", "kind": "sentence", "origin": [72, 720], "spec": S1_SPEC,
     "text": "If the blue latch is closed, do not move the crate more than 12 cm."},
    {"block_id": "S2", "kind": "sentence", "origin": [72, 696], "spec": S2_SPEC,
     "text": "The green lamp remains on."},
    {"block_id": "R1", "kind": "label_value_line", "origin": [72, 672], "spec": R1_SPEC,
     "text": "Span: 12 cm"},
    {"block_id": "R2", "kind": "label_value_line", "origin": [72, 648], "spec": R2_SPEC,
     "text": "Delay: 7 s"},
]

MEASUREMENTS = {
    "S1.m1": {"block_id": "S1", "number": "12", "unit": "cm",
              "note": "limit inside the negated main clause of S1"},
    "R1.m1": {"block_id": "R1", "number": "12", "unit": "cm",
              "note": "value of label 'Span'; same surface string as S1.m1 by design"},
    "R2.m1": {"block_id": "R2", "number": "7", "unit": "s",
              "note": "value of label 'Delay'"},
}
CLAUSES = {
    "S1.cl1": {"block_id": "S1", "role": "condition"},
    "S1.cl2": {"block_id": "S1", "role": "negated_main_clause"},
    "S2.cl1": {"block_id": "S2", "role": "main_clause"},
    "R1.label": {"block_id": "R1", "role": "label"},
    "R1.value": {"block_id": "R1", "role": "value"},
    "R2.label": {"block_id": "R2", "role": "label"},
    "R2.value": {"block_id": "R2", "role": "value"},
}

# ---------------------------------------------------------------------------
# Fixture drawing plans: runs in drawing order.
# (font_resource, block_id, start, end, positioning)
#   positioning "Tm": emit "1 0 0 1 x y Tm" at the declared origin of the
#                      run's first character.
#   positioning "advance": emit nothing; the run must start where the
#                      previous run's implicit advance left the pen.
# ---------------------------------------------------------------------------

FIXTURES: dict[str, dict[str, Any]] = {
    "A": {
        "file": "A_plain_order.pdf",
        "summary": "ordinary drawing order; one Courier (F1) run per line",
        "runs": [
            ("F1", "S1", 0, 67, "Tm"),
            ("F1", "S2", 0, 26, "Tm"),
            ("F1", "R1", 0, 11, "Tm"),
            ("F1", "R2", 0, 10, "Tm"),
        ],
    },
    "B": {
        "file": "B_styled_runs.pdf",
        "summary": ("as A, but 'not' in Courier-Bold (F2) and 'closed' split into "
                    "'clo' (F1) + 'sed' (F3 Courier-Oblique); runs continue by "
                    "implicit advance"),
        "runs": [
            ("F1", "S1", 0, 24, "Tm"),
            ("F3", "S1", 24, 27, "advance"),
            ("F1", "S1", 27, 32, "advance"),
            ("F2", "S1", 32, 35, "advance"),
            ("F1", "S1", 35, 67, "advance"),
            ("F1", "S2", 0, 26, "Tm"),
            ("F1", "R1", 0, 11, "Tm"),
            ("F1", "R2", 0, 10, "Tm"),
        ],
    },
    "C": {
        "file": "C_late_suffix.pdf",
        "summary": ("as B, but S1 suffix '12 cm.' painted after S2, explicitly "
                    "positioned with Tm at its original origin"),
        "runs": [
            ("F1", "S1", 0, 24, "Tm"),
            ("F3", "S1", 24, 27, "advance"),
            ("F1", "S1", 27, 32, "advance"),
            ("F2", "S1", 32, 35, "advance"),
            ("F1", "S1", 35, 61, "advance"),
            ("F1", "S2", 0, 26, "Tm"),
            ("F1", "S1", 61, 67, "Tm"),
            ("F1", "R1", 0, 11, "Tm"),
            ("F1", "R2", 0, 10, "Tm"),
        ],
    },
    "D": {
        "file": "D_explicit_suffix_in_order.pdf",
        "summary": ("as B (same drawing order), but the S1 suffix '12 cm.' is a separate "
                    "run positioned by the same explicit Tm as in C"),
        "added_after_initial_run": True,
        "justification": (
            "In run1 the C layout output separated 'than' and '12' by 24 spaces. "
            "C changes two things relative to B: the suffix is drawn late and it is "
            "re-positioned by an explicit Tm. D keeps B's drawing order and adds only "
            "the Tm, so B/D tests the equivalent operator pair (implicit advance vs "
            "explicit Tm to the same origin, cf. the TJ-vs-Td pair in pypdf's #3951 "
            "regression test) and C/D isolates drawing order."),
        "runs": [
            ("F1", "S1", 0, 24, "Tm"),
            ("F3", "S1", 24, 27, "advance"),
            ("F1", "S1", 27, 32, "advance"),
            ("F2", "S1", 32, 35, "advance"),
            ("F1", "S1", 35, 61, "advance"),
            ("F1", "S1", 61, 67, "Tm"),
            ("F1", "S2", 0, 26, "Tm"),
            ("F1", "R1", 0, 11, "Tm"),
            ("F1", "R2", 0, 10, "Tm"),
        ],
    },
}
INITIAL_FIXTURES = ("A", "B", "C")

# ---------------------------------------------------------------------------
# Declared structure -> characters, tokens, expected glyph origins
# ---------------------------------------------------------------------------


def _expand_spec(block: dict[str, Any]) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    spec = block["spec"]
    for i, item in enumerate(spec):
        if item == " ":
            prev_item, next_item = spec[i - 1], spec[i + 1]
            clause = prev_item[2] if prev_item[2] == next_item[2] else None
            meas = prev_item[4] if prev_item[4] and prev_item[4] == next_item[4] else None
            tokens.append({"text": " ", "kind": "space", "clause_id": clause,
                           "roles": [], "measurement_id": meas})
        else:
            text, kind, clause, roles, meas = item
            tokens.append({"text": text, "kind": kind, "clause_id": clause,
                           "roles": list(roles), "measurement_id": meas})
    return tokens


def declared_structure() -> dict[str, Any]:
    """Characters, tokens and expected origins from the declared structure."""
    blocks_out, tokens_out, chars_out = [], [], []
    for block in BLOCKS:
        bid = block["block_id"]
        tokens = _expand_spec(block)
        text = "".join(t["text"] for t in tokens)
        if text != block["text"]:
            raise AssertionError(f"{bid}: token spec {text!r} != text {block['text']!r}")
        if not set(text) <= ALLOWED_CHARS:
            raise AssertionError(f"{bid}: unexpected characters {set(text) - ALLOWED_CHARS}")
        x0, y0 = block["origin"]
        pos = 0
        token_ids = []
        for t_idx, tok in enumerate(tokens):
            tid = f"{bid}.t{t_idx:02d}"
            token_ids.append(tid)
            char_ids = []
            for ch in tok["text"]:
                cid = f"{bid}:{pos:02d}"
                char_ids.append(cid)
                chars_out.append({
                    "char_id": cid,
                    "char": ch,
                    "block_id": bid,
                    "index_in_block": pos,
                    "token_id": tid,
                    "token_kind": tok["kind"],
                    "clause_id": tok["clause_id"],
                    "measurement_id": tok["measurement_id"],
                    "roles": tok["roles"],
                    # x = block origin + sum of preceding declared advances
                    "expected_origin": [x0 + sum(glyph_advance(c) for c in text[:pos]), y0],
                    "expected_advance": glyph_advance(ch),
                })
                pos += 1
            tokens_out.append({"token_id": tid, "block_id": bid, "text": tok["text"],
                               "kind": tok["kind"], "clause_id": tok["clause_id"],
                               "measurement_id": tok["measurement_id"],
                               "roles": tok["roles"], "char_ids": char_ids})
        blocks_out.append({"block_id": bid, "kind": block["kind"], "text": text,
                           "origin": [x0, y0], "token_ids": token_ids,
                           "char_count": len(text),
                           "line_end_x": x0 + sum(glyph_advance(c) for c in text)})
    return {"blocks": blocks_out, "tokens": tokens_out, "characters": chars_out,
            "clauses": CLAUSES, "measurements": MEASUREMENTS,
            "declared_order": [c["char_id"] for c in chars_out]}


# ---------------------------------------------------------------------------
# Content stream and PDF bytes
# ---------------------------------------------------------------------------


def _num(value: float) -> str:
    if float(value) != int(value):
        raise ValueError(f"non-integral coordinate {value!r}; adjust the layout")
    return str(int(value))


def _pdf_string(text: str) -> str:
    # Literal string; escape the three characters that need it.
    return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def build_fixture(name: str, decl: dict[str, Any]) -> dict[str, Any]:
    plan = FIXTURES[name]
    chars_by_block: dict[str, list[dict[str, Any]]] = {}
    for c in decl["characters"]:
        chars_by_block.setdefault(c["block_id"], []).append(c)

    lines: list[str] = ["BT"]
    op_roles: list[dict[str, Any]] = [{"kind": "begin_text"}]
    runs, glyphs = [], []
    current_font = None
    pen = None  # simulated text-space pen (Tm translation only), from metrics
    draw_seq = 0
    for r_idx, (font, bid, start, end, positioning) in enumerate(plan["runs"]):
        run_id = f"{name}.r{r_idx}"
        run_chars = chars_by_block[bid][start:end]
        first_origin = run_chars[0]["expected_origin"]
        if font != current_font:
            lines.append(f"/{font} {FONT_SIZE} Tf")
            op_roles.append({"kind": "select_font", "font_resource": font,
                             "before_run": run_id})
            current_font = font
        if positioning == "Tm":
            lines.append(f"1 0 0 1 {_num(first_origin[0])} {_num(first_origin[1])} Tm")
            op_roles.append({"kind": "set_text_matrix", "before_run": run_id})
            pen = list(first_origin)
        elif positioning == "advance":
            if pen != first_origin:
                raise AssertionError(f"{run_id}: implicit advance {pen} != declared {first_origin}")
        else:
            raise ValueError(positioning)
        text = "".join(c["char"] for c in run_chars)
        show_index = len(lines)
        lines.append(f"{_pdf_string(text)} Tj")
        op_roles.append({"kind": "show_text", "run_id": run_id})
        for g_idx, c in enumerate(run_chars):
            if pen != c["expected_origin"]:
                raise AssertionError(f"{c['char_id']}: pen {pen} != declared {c['expected_origin']}")
            glyphs.append({
                "draw_seq": draw_seq, "char_id": c["char_id"], "char": c["char"],
                "run_id": run_id, "op_index": show_index, "index_in_run": g_idx,
                "font_resource": font, "base_font": FONTS[font]["BaseFont"],
                "origin": list(pen), "advance": glyph_advance(c["char"]),
            })
            draw_seq += 1
            pen = [pen[0] + glyph_advance(c["char"]), pen[1]]
        runs.append({"run_id": run_id, "block_id": bid, "char_start": start,
                     "char_end": end, "text": text, "font_resource": font,
                     "base_font": FONTS[font]["BaseFont"], "positioning": positioning,
                     "op_index": show_index,
                     "char_ids": [c["char_id"] for c in run_chars]})
    lines.append("ET")
    op_roles.append({"kind": "end_text"})

    content = ("\n".join(lines) + "\n").encode("ascii")
    operations, offset = [], 0
    for idx, (line, role) in enumerate(zip(lines, op_roles)):
        raw = line.encode("ascii")
        if line.endswith(" Tj"):
            operator, operands = "Tj", [line[: -len(" Tj")]]
        else:
            parts = line.split(" ")
            operator, operands = parts[-1], parts[:-1]
        operations.append({"op_index": idx, "operator": operator, "operands": operands,
                           "source": line, "byte_offset": offset,
                           "byte_length": len(raw), **role})
        offset += len(raw) + 1
    assert offset == len(content)

    drawing_order = [g["char_id"] for g in glyphs]
    declared_pos = {cid: i for i, cid in enumerate(decl["declared_order"])}
    perturbations = {
        "non_F1_glyphs": {f: [g["char_id"] for g in glyphs if g["font_resource"] == f]
                          for f in FONTS if f != "F1"},
        "run_boundaries_between_adjacent_nonspace_glyphs": [
            [a["char_id"], b["char_id"]] for a, b in zip(glyphs, glyphs[1:])
            if a["run_id"] != b["run_id"] and a["char"] != " " and b["char"] != " "
            and a["char_id"].split(":")[0] == b["char_id"].split(":")[0]],
        "glyphs_drawn_out_of_declared_order": [
            g["char_id"] for i, g in enumerate(glyphs)
            if any(declared_pos[h["char_id"]] > declared_pos[g["char_id"]] for h in glyphs[:i])],
    }
    geometric_order = [g["char_id"] for g in sorted(glyphs, key=lambda g: (-g["origin"][1], g["origin"][0]))]
    pdf = build_pdf(content)
    return {
        "file": plan["file"],
        "summary": plan["summary"],
        "added_after_initial_run": bool(plan.get("added_after_initial_run")),
        "justification": plan.get("justification"),
        "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
        "pdf_bytes": len(pdf),
        "content_stream_sha256": hashlib.sha256(content).hexdigest(),
        "content_stream": content.decode("ascii"),
        "operations": operations,
        "perturbations": perturbations,
        "runs": runs,
        "glyphs": glyphs,
        "drawing_order": drawing_order,
        "geometric_order": geometric_order,
        "geometric_order_rule": "glyph origin y descending, then x ascending",
        "drawing_equals_declared": drawing_order == decl["declared_order"],
        "geometric_equals_declared": geometric_order == decl["declared_order"],
        "_pdf": pdf,
        "_content": content,
    }


def font_object(font: str) -> bytes:
    widths = " ".join([str(GLYPH_WIDTH)] * (LAST_CHAR - FIRST_CHAR + 1))
    return (
        f"<< /Type /Font /Subtype /Type1 /BaseFont /{FONTS[font]['BaseFont']} "
        f"/Encoding /{ENCODING} /FirstChar {FIRST_CHAR} /LastChar {LAST_CHAR} "
        f"/Widths [{widths}] >>"
    ).encode("ascii")


def build_pdf(content: bytes) -> bytes:
    """Minimal one-page PDF 1.7; no Info dictionary, no dates, no /ID."""
    font_refs = " ".join(f"/{f} {5 + i} 0 R" for i, f in enumerate(FONTS))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
         f"/Resources << /Font << {font_refs} >> >> /Contents 4 0 R >>").encode("ascii"),
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
        + content + b"endstream",
    ] + [font_object(f) for f in FONTS]
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii") + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode("ascii")
    return bytes(out)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def _flat(value: Any) -> bool:
    if isinstance(value, dict):
        return all(_flat_leaf(v) for v in value.values())
    if isinstance(value, list):
        return all(not isinstance(v, (dict, list)) for v in value)
    return True


def _flat_leaf(value: Any) -> bool:
    if isinstance(value, list):
        return all(not isinstance(v, (dict, list)) for v in value)
    return not isinstance(value, dict)


def dump_json(value: Any, indent: int = 0) -> str:
    """Stable JSON: containers pretty-printed, flat records on one line."""
    pad = " " * indent
    if _flat(value):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, dict):
        items = [f"{pad} {json.dumps(k)}: {dump_json(v, indent + 1)}" for k, v in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    items = [f"{pad} {dump_json(v, indent + 1)}" for v in value]
    return "[\n" + ",\n".join(items) + "\n" + pad + "]"


def build_all() -> tuple[dict[str, Any], dict[str, bytes]]:
    decl = declared_structure()
    files: dict[str, bytes] = {}
    fixtures = {}
    for name in FIXTURES:
        fx = build_fixture(name, decl)
        files[fx["file"]] = fx.pop("_pdf")
        files[f"content_streams/{name}.txt"] = fx.pop("_content")
        fixtures[name] = fx

    def geometry(name: str) -> list[tuple]:
        return sorted((g["char_id"], g["char"], tuple(g["origin"]), g["advance"])
                      for g in fixtures[name]["glyphs"])

    declared_geometry = sorted((c["char_id"], c["char"], tuple(c["expected_origin"]),
                                c["expected_advance"]) for c in decl["characters"])
    cross = {name: {"glyph_geometry_equals_declared": geometry(name) == declared_geometry,
                    "glyph_geometry_equals_A": geometry(name) == geometry("A")}
             for name in fixtures}

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "request_id": REQUEST_ID,
        "notice": ("Fictional text authored for this fixture. Not derived from, and not "
                   "attributable to, any real document."),
        "generator": "generate_fixtures.py",
        "page": {"MediaBox": [0, 0, PAGE_WIDTH, PAGE_HEIGHT], "count": 1},
        "text_state": {"font_size": FONT_SIZE, **TEXT_STATE,
                       "note": "PDF initial text state; no Tc/Tw/Tz/TL/Ts/Tr operators emitted"},
        "fonts": {f: {"resource": f, "Type": "Font", "Subtype": "Type1",
                      "BaseFont": FONTS[f]["BaseFont"], "style": FONTS[f]["style"],
                      "Encoding": ENCODING, "FirstChar": FIRST_CHAR, "LastChar": LAST_CHAR,
                      "Widths_all_equal": GLYPH_WIDTH,
                      "Widths_count": LAST_CHAR - FIRST_CHAR + 1,
                      "embedded": False, "FontDescriptor": None,
                      "object_source": font_object(f).decode("ascii")}
                  for f in FONTS},
        "metric_derivation": ("advance_pt = (Widths[code-FirstChar]/1000 * font_size + Tc + "
                              "(Tw if code==32)) * Tz/100 = (600/1000*10 + 0 + 0) * 1 = 6.0; "
                              "expected x = block origin x + 6.0 * index_in_block; "
                              "expected y = block baseline y"),
        "order_definitions": {
            "declared_order": "fixture author's intended reading order: S1, S2, R1, R2, each left to right",
            "drawing_order": "order in which glyphs are painted by the content stream (draw_seq)",
            "geometric_order": "glyph origins sorted by y descending, then x ascending (a rule, not a semantic claim)",
        },
        "declared_structure": decl,
        "fixtures": fixtures,
        "cross_fixture": cross,
        "initial_fixtures": list(INITIAL_FIXTURES),
    }
    files["manifest.json"] = (dump_json(manifest) + "\n").encode("ascii")
    return manifest, files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true",
                        help="verify existing files are byte-identical; write nothing")
    args = parser.parse_args(argv)
    _, files = build_all()
    if args.check:
        bad = []
        for rel, data in files.items():
            path = args.out / rel
            if not path.exists() or path.read_bytes() != data:
                bad.append(rel)
        for rel in bad:
            print(f"MISMATCH {rel}", file=sys.stderr)
        print(f"checked {len(files)} files, {len(bad)} mismatches")
        return 1 if bad else 0
    for rel, data in files.items():
        path = args.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"{hashlib.sha256(data).hexdigest()}  {rel}  ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Standalone research directory inside a fork of Trafilatura (Apache-2.0).
"""Deterministic generator for the public_pdf_visible_layers_20261104 fixtures.

Fictional table, authored here. The PDFs are written byte by byte with the
standard library only, so the generator does not depend on any tool under test.
The raster is drawn with a 5x9 bitmap font authored in this file, stored as an
uncompressed 1-bit image, and placed at 2 px/pt so that a 144 dpi render maps
image pixels 1:1 onto device pixels.

A  born-digital: vector rules plus visible Courier 10 pt text (0 Tr)
B  image-only: the raster, no text object
C  raster + hidden text (3 Tr); the Gap value is WRONG ("17 mm" over visible "12 mm")
D  control: raster + hidden text (3 Tr), every value correct
E  render-sensitivity control: C's text layer drawn visibly (0 Tr)

    python3 generate_fixtures.py            # (re)write fixtures/
    python3 generate_fixtures.py --check    # verify fixtures/ is byte-identical
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REQUEST_ID = "public-pdf-visible-table-and-text-layer-20261104-01"
HERE = Path(__file__).resolve().parent
OUT = HERE / "fixtures"

PAGE_W, PAGE_H = 612, 792
PX_PER_PT = 2  # raster resolution; a 144 dpi render is 1:1
FONT_SIZE = 10  # Courier: advance 600/1000 * 10 = 6 pt per glyph
ADVANCE_PT = 6  # bitmap glyph cell: 5 font px ink + 1 font px gap, 1 font px = 1 pt
CAP_ROWS, DESC_ROWS = 7, 2  # rows above / below the baseline

# Table geometry in PDF points (y up).
X0, X1, XSPLIT = 72, 192, 132
TOP, ROW_H, NROWS = 720, 16, 4
BOTTOM = TOP - ROW_H * NROWS  # 656
TEXT_PAD = 6
BASELINE_DROP = 12  # baseline = row top - 12
RULE = 1  # rule thickness in pt
TABLE = [("Item", "Value"), ("Gap", "12 mm"), ("Delay", "7 s"), ("Load", "18 kg")]
WRONG_CELL = {"row": 1, "col": 1, "visible": "12 mm", "searchable": "17 mm"}

# Bitmap font authored for this experiment: 5 columns x 9 rows ('#' = ink).
# Rows 0-6 are above the baseline, rows 7-8 are descenders.
FONT_ROWS = {
    "I": ".###. ..#.. ..#.. ..#.. ..#.. ..#.. .###. ..... .....",
    "t": ".#... .#... ####. .#... .#... .#..# ..##. ..... .....",
    "e": "..... ..... .###. #...# ##### #.... .###. ..... .....",
    "m": "..... ..... ##.#. #.#.# #.#.# #.#.# #.#.# ..... .....",
    "V": "#...# #...# #...# #...# .#.#. .#.#. ..#.. ..... .....",
    "a": "..... ..... .###. ....# .#### #...# .#### ..... .....",
    "l": ".##.. ..#.. ..#.. ..#.. ..#.. ..#.. .###. ..... .....",
    "u": "..... ..... #...# #...# #...# #..## .##.# ..... .....",
    "G": ".###. #...# #.... #.### #...# #...# .###. ..... .....",
    "p": "..... ..... ####. #...# #...# #...# ####. #.... #....",
    "D": "####. #...# #...# #...# #...# #...# ####. ..... .....",
    "y": "..... ..... #...# #...# #...# #...# .#### ....# .###.",
    "L": "#.... #.... #.... #.... #.... #.... ##### ..... .....",
    "o": "..... ..... .###. #...# #...# #...# .###. ..... .....",
    "d": "....# ....# .#### #...# #...# #...# .#### ..... .....",
    "1": "..#.. .##.. ..#.. ..#.. ..#.. ..#.. .###. ..... .....",
    "2": ".###. #...# ....# ...#. ..#.. .#... ##### ..... .....",
    "7": "##### ....# ...#. ..#.. .#... .#... .#... ..... .....",
    "8": ".###. #...# #...# .###. #...# #...# .###. ..... .....",
    "s": "..... ..... .#### #.... .###. ....# ####. ..... .....",
    "k": "#.... #.... #..#. #.#.. ##... #.#.. #..#. ..... .....",
    "g": "..... ..... .#### #...# #...# #...# .#### ....# .###.",
    " ": "..... ..... ..... ..... ..... ..... ..... ..... .....",
}
FONT = {ch: spec.split() for ch, spec in FONT_ROWS.items()}


def check_font() -> None:
    for ch, rows in FONT.items():
        assert len(rows) == CAP_ROWS + DESC_ROWS, ch
        assert all(len(r) == 5 for r in rows), ch
    glyphs = ["".join(rows) for rows in FONT.values()]
    assert len(set(glyphs)) == len(glyphs), "bitmap glyphs must be pairwise distinct"


# ---------------------------------------------------------------------------
# Declared cells and the authored raster (visible truth)
# ---------------------------------------------------------------------------


def cells() -> list[dict[str, Any]]:
    out = []
    for r, row in enumerate(TABLE):
        baseline = TOP - ROW_H * r - BASELINE_DROP
        for c, text in enumerate(row):
            x = (X0 if c == 0 else XSPLIT) + TEXT_PAD
            glyphs = [
                {
                    "index": i,
                    "char": ch,
                    "box_pt": [x + ADVANCE_PT * i, baseline - DESC_ROWS, x + ADVANCE_PT * i + 5, baseline + CAP_ROWS],
                    "ink_font_px": sum(row_.count("#") for row_ in FONT[ch]),
                }
                for i, ch in enumerate(text)
            ]
            out.append(
                {
                    "cell_id": f"r{r}c{c}",
                    "row": r,
                    "col": c,
                    "text": text,
                    "origin_pt": [x, baseline],
                    "text_box_pt": [x, baseline - DESC_ROWS, x + ADVANCE_PT * len(text), baseline + CAP_ROWS],
                    "glyphs": glyphs,
                }
            )
    return out


def rules_pt() -> list[list[int]]:
    """Filled rule rectangles [x, y, w, h] in points."""
    return [
        [X0, TOP - RULE, X1 - X0, RULE],  # top
        [X0, BOTTOM, X1 - X0, RULE],  # bottom
        [X0, BOTTOM, RULE, TOP - BOTTOM],  # left
        [X1 - RULE, BOTTOM, RULE, TOP - BOTTOM],  # right
        [XSPLIT, BOTTOM, RULE, TOP - BOTTOM],  # column separator
        [X0, TOP - ROW_H - RULE, X1 - X0, RULE],  # header separator
    ]


def raster() -> list[bytearray]:
    """Ink matrix (1 = ink) of the table image, row 0 = top."""
    w, h = (X1 - X0) * PX_PER_PT, (TOP - BOTTOM) * PX_PER_PT
    ink = [bytearray(w) for _ in range(h)]

    def fill_pt(x: float, y_top: float, wd: float, ht: float) -> None:
        c0, r0 = round((x - X0) * PX_PER_PT), round((TOP - y_top) * PX_PER_PT)
        for rr in range(r0, r0 + round(ht * PX_PER_PT)):
            for cc in range(c0, c0 + round(wd * PX_PER_PT)):
                ink[rr][cc] = 1

    for x, y, wd, ht in rules_pt():
        fill_pt(x, y + ht, wd, ht)
    for cell in cells():
        x, baseline = cell["origin_pt"]
        for i, ch in enumerate(cell["text"]):
            for r, row in enumerate(FONT[ch]):
                for c, v in enumerate(row):
                    if v == "#":
                        fill_pt(x + ADVANCE_PT * i + c, baseline + CAP_ROWS - r, 1, 1)
    return ink


def pack_rows(ink: list[bytearray], ink_bit: int) -> bytes:
    out = bytearray()
    for row in ink:
        assert len(row) % 8 == 0
        for i in range(0, len(row), 8):
            byte = 0
            for v in row[i : i + 8]:
                byte = (byte << 1) | (ink_bit if v else 1 - ink_bit)
            out.append(byte)
    return bytes(out)


def pbm(ink: list[bytearray]) -> bytes:
    """Raw PBM (P4): 1 = black. Lossless, uncompressed."""
    return f"P4\n{len(ink[0])} {len(ink)}\n".encode("ascii") + pack_rows(ink, ink_bit=1)


# ---------------------------------------------------------------------------
# PDF bytes
# ---------------------------------------------------------------------------


def text_layer(render_mode: int, wrong: bool) -> list[str]:
    ops = ["BT", f"/F1 {FONT_SIZE} Tf", f"{render_mode} Tr"]
    for cell in cells():
        text = cell["text"]
        if wrong and (cell["row"], cell["col"]) == (WRONG_CELL["row"], WRONG_CELL["col"]):
            assert text == WRONG_CELL["visible"]
            text = WRONG_CELL["searchable"]
        x, baseline = cell["origin_pt"]
        ops += [f"1 0 0 1 {x} {baseline} Tm", f"({text}) Tj"]
    return [*ops, "ET"]


IMAGE_OPS = [f"q {X1 - X0} 0 0 {TOP - BOTTOM} {X0} {BOTTOM} cm", "/Im1 Do", "Q"]
RULE_OPS = ["q", "0 g", *[f"{x} {y} {w} {h} re f" for x, y, w, h in rules_pt()], "Q"]

FIXTURES: dict[str, dict[str, Any]] = {
    "A": {
        "file": "A_born_digital.pdf",
        "role": "born-digital: vector rules and visible Courier text",
        "image": False,
        "ops": RULE_OPS + text_layer(0, wrong=False),
    },
    "B": {"file": "B_image_only.pdf", "role": "image-only: the authored raster, no text", "image": True, "ops": IMAGE_OPS},
    "C": {
        "file": "C_raster_hidden_wrong.pdf",
        "role": "raster + invisible (3 Tr) text layer; Gap value WRONG (17 mm over visible 12 mm)",
        "image": True,
        "ops": IMAGE_OPS + text_layer(3, wrong=True),
    },
    "D": {
        "file": "D_raster_hidden_correct.pdf",
        "role": "control: raster + invisible (3 Tr) text layer, all values correct",
        "image": True,
        "ops": IMAGE_OPS + text_layer(3, wrong=False),
    },
    "E": {
        "file": "E_raster_visible_wrong.pdf",
        "role": "render-sensitivity control: C's text layer drawn visibly (0 Tr)",
        "image": True,
        "ops": IMAGE_OPS + text_layer(0, wrong=True),
    },
}


def font_object() -> bytes:
    widths = " ".join(["600"] * 95)
    return (
        "<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding "
        f"/FirstChar 32 /LastChar 126 /Widths [{widths}] >>"
    ).encode("ascii")


def image_object(ink: list[bytearray]) -> bytes:
    data = pack_rows(ink, ink_bit=0)  # DeviceGray 1-bit: 0 = black
    head = (
        f"<< /Type /XObject /Subtype /Image /Width {len(ink[0])} /Height {len(ink)} "
        f"/ColorSpace /DeviceGray /BitsPerComponent 1 /Length {len(data)} >>\nstream\n"
    ).encode("ascii")
    return head + data + b"\nendstream"


def build_pdf(content: bytes, with_image: bool, with_font: bool, ink: list[bytearray]) -> bytes:
    resources, extra = [], []
    next_num = 5
    if with_font:
        resources.append(f"/Font << /F1 {next_num} 0 R >>")
        extra.append(font_object())
        next_num += 1
    if with_image:
        resources.append(f"/XObject << /Im1 {next_num} 0 R >>")
        extra.append(image_object(ink))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << {' '.join(resources)} >> /Contents 4 0 R >>"
        ).encode("ascii"),
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
        *extra,
    ]
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for num, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{num} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii") + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    return bytes(out)


def build_all() -> dict[str, bytes]:
    check_font()
    ink = raster()
    files: dict[str, bytes] = {"raster/table.pbm": pbm(ink)}
    fixtures = {}
    for name, fx in FIXTURES.items():
        content = ("\n".join(fx["ops"]) + "\n").encode("ascii")
        has_text = any(op == "BT" for op in fx["ops"])
        pdf = build_pdf(content, fx["image"], has_text, ink)
        files[fx["file"]] = pdf
        files[f"content_streams/{name}.txt"] = content
        tr = [op for op in fx["ops"] if op.endswith(" Tr")]
        fixtures[name] = {
            "file": fx["file"],
            "role": fx["role"],
            "has_image": fx["image"],
            "has_text_objects": has_text,
            "text_render_mode_ops": tr,
            "operations": [{"op_index": i, "source": op} for i, op in enumerate(fx["ops"])],
            "content_stream_sha256": hashlib.sha256(content).hexdigest(),
            "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
            "pdf_bytes": len(pdf),
        }
    image_data = pack_rows(ink, ink_bit=0)
    truth = {
        "request_id": REQUEST_ID,
        "notice": "Fictional table authored for this experiment; not derived from any real document.",
        "page": {"MediaBox": [0, 0, PAGE_W, PAGE_H]},
        "raster": {
            "file": "raster/table.pbm",
            "width_px": len(ink[0]),
            "height_px": len(ink),
            "px_per_pt": PX_PER_PT,
            "placed_at_pt": {"x": X0, "y": BOTTOM, "w": X1 - X0, "h": TOP - BOTTOM},
            "ink_pixels": sum(sum(r) for r in ink),
            "pdf_image_data_sha256": hashlib.sha256(image_data).hexdigest(),
            "pbm_sha256": hashlib.sha256(files["raster/table.pbm"]).hexdigest(),
            "encoding": "PDF: DeviceGray 1 bpc uncompressed, 0 = black; PBM P4: 1 = black",
        },
        "bitmap_font": {
            "cell_pt": [ADVANCE_PT, CAP_ROWS + DESC_ROWS],
            "glyph_px": [5, 9],
            "font_px_pt": 1,
            "rows": FONT_ROWS,
            "license": "authored for this experiment; Apache-2.0 with the repository",
        },
        "visible_truth": {"source": "authored raster (these strings drawn with the bitmap font)", "cells": cells()},
        "rules_pt": rules_pt(),
        "hidden_text": {"font": "Courier (standard 14, not embedded)", "size": FONT_SIZE, "wrong_cell": WRONG_CELL},
        "fixtures": fixtures,
    }
    files["manifest.json"] = (json.dumps(truth, indent=1, ensure_ascii=True) + "\n").encode("ascii")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--check", action="store_true", help="verify existing files; write nothing")
    args = parser.parse_args(argv)
    files = build_all()
    if args.check:
        bad = [rel for rel, data in files.items() if not (args.out / rel).is_file() or (args.out / rel).read_bytes() != data]
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

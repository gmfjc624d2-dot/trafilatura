# SPDX-License-Identifier: Apache-2.0
"""Fixture invariants and comparison-helper behaviour.

No renderer or extractor runs here, and no test asserts what a tool outputs.
The PDF checks re-parse the fixture bytes independently of the generator.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import generate_fixtures as gen  # noqa: E402
import layer_compare as lc  # noqa: E402

FIX = ROOT / "fixtures"
MANIFEST = json.loads((FIX / "manifest.json").read_text("ascii"))
CELLS = MANIFEST["visible_truth"]["cells"]
ORIGIN_PX = (144, 144)  # (72 pt, 792 - 720 pt) at 2 px/pt


def objects(name: str) -> dict[int, bytes]:
    pdf = (FIX / MANIFEST["fixtures"][name]["file"]).read_bytes()
    return {int(n): body for n, body in re.findall(rb"(\d+) 0 obj\n(.*?)\nendobj\n", pdf, flags=re.DOTALL)}


def stream(body: bytes) -> bytes:
    m = re.search(rb"/Length (\d+) >>\nstream\n", body)
    return body[m.end() : m.end() + int(m.group(1))]


def image_data(name: str) -> bytes | None:
    for body in objects(name).values():
        if b"/Subtype /Image" in body:
            return stream(body)
    return None


def content(name: str) -> list[str]:
    return stream(objects(name)[4]).decode("ascii").splitlines()


def pbm_ink() -> list[list[int]]:
    data = (FIX / "raster" / "table.pbm").read_bytes()
    m = re.match(rb"P4\s+(\d+)\s+(\d+)\s", data)
    w, h = int(m.group(1)), int(m.group(2))
    body = data[m.end() :]
    return [[(body[y * (w // 8) + x // 8] >> (7 - x % 8)) & 1 for x in range(w)] for y in range(h)]


def test_generator_reproduces_committed_files_byte_for_byte():
    files = gen.build_all()
    assert files == gen.build_all()
    for rel, data in files.items():
        assert (FIX / rel).read_bytes() == data, rel
    assert {p.relative_to(FIX).as_posix() for p in FIX.rglob("*") if p.is_file()} == set(files)


def test_bitmap_glyphs_are_distinct_and_the_raster_decodes_to_the_truth():
    gen.check_font()
    page = lc.raster_as_render(pbm_ink(), ORIGIN_PX)
    for cell in CELLS:
        assert lc.decode_cell(page, cell, gen.FONT) == {
            "cell_id": cell["cell_id"],
            "decoded": cell["text"],
            "ambiguous_blocks": 0,
        }
    assert [c["text"] for c in CELLS] == ["Item", "Value", "Gap", "12 mm", "Delay", "7 s", "Load", "18 kg"]


def test_raster_fixtures_share_one_image_equal_to_the_pbm():
    ink = pbm_ink()
    want = gen.pack_rows([bytearray(r) for r in ink], ink_bit=0)  # PDF DeviceGray: 0 = black
    assert image_data("A") is None
    for name in "BCDE":
        assert image_data(name) == want, name
    assert hashlib.sha256(want).hexdigest() == MANIFEST["raster"]["pdf_image_data_sha256"]


def test_content_streams_differ_only_as_declared():
    b, c, d, e = (content(n) for n in "BCDE")
    assert "BT" not in b
    assert c[: len(b)] == b and d[: len(b)] == b and e[: len(b)] == b  # same image placement
    assert [(i, x, y) for i, (x, y) in enumerate(zip(c, d, strict=True)) if x != y] == [
        (len(b) + 10, "(17 mm) Tj", "(12 mm) Tj")
    ]
    assert [(x, y) for x, y in zip(c, e, strict=True) if x != y] == [("3 Tr", "0 Tr")]
    assert sum(op.endswith(" Tr") for op in c) == 1


def test_hidden_text_sits_on_the_visible_glyph_grid():
    lines = content("C")
    tms = [(float(m.group(1)), float(m.group(2))) for m in (re.match(r"1 0 0 1 (\S+) (\S+) Tm", x) for x in lines) if m]
    strings = [x[1 : -len(") Tj")] for x in lines if x.endswith(") Tj")]
    assert tms == [tuple(c["origin_pt"]) for c in CELLS]
    wrong = MANIFEST["hidden_text"]["wrong_cell"]
    diffs = [(c["cell_id"], c["text"], s) for c, s in zip(CELLS, strings, strict=True) if c["text"] != s]
    assert diffs == [("r1c1", wrong["visible"], wrong["searchable"])]
    for cell in CELLS:  # Courier 10 pt advance (6 pt) equals the bitmap glyph cell
        assert [g["box_pt"][0] for g in cell["glyphs"]] == [cell["origin_pt"][0] + 6 * i for i in range(len(cell["text"]))]
    font = next(body for body in objects("C").values() if b"/BaseFont /Courier" in body)
    assert re.search(rb"/Widths \[([\d ]+)\]", font).group(1).split() == [b"600"] * 95


# ---------------------------------------------------------------------------
# Helpers on synthetic inputs
# ---------------------------------------------------------------------------


def blank(w: int = 8, h: int = 4) -> dict:
    return {"width": w, "height": h, "pixels": b"\xff" * (w * h * 3)}


def test_diff_pixels_is_exact_and_locates_changes():
    a, b = blank(), blank()
    assert lc.diff_pixels(a, b) == {"comparable": True, "identical": True, "differing_pixels": 0}
    px = bytearray(b["pixels"])
    px[(2 * 8 + 5) * 3] = 254  # one channel of one pixel, off by one
    r = lc.diff_pixels(a, {**b, "pixels": bytes(px)})
    assert (r["identical"], r["differing_pixels"], r["bbox_px"], r["_coords"]) == (False, 1, [5, 2, 6, 3], [(5, 2)])
    assert lc.confined([(5, 2)], [(0, 0, 5, 4)])["outside_count"] == 1
    assert lc.confined([(5, 2)], [(5, 2, 6, 3)])["outside_count"] == 0
    assert lc.diff_pixels(a, blank(9, 4))["comparable"] is False


def test_decode_marks_a_grey_block_ambiguous_instead_of_guessing():
    page = lc.raster_as_render(pbm_ink(), ORIGIN_PX)
    cell = next(c for c in CELLS if c["cell_id"] == "r1c1")
    x0, base = cell["origin_pt"]
    px = bytearray(page["pixels"])
    i = (((792 - (base + 7)) * 2) * page["width"] + (x0 + 6) * 2 + 1) * 3  # inside the '2' (top-left block)
    px[i : i + 3] = b"\x80\x80\x80"
    got = lc.decode_cell({**page, "pixels": bytes(px)}, cell, gen.FONT)
    assert got["decoded"] == "1? mm" and got["ambiguous_blocks"] == 1


def test_ink_coverage_and_cell_assignment():
    cell = next(c for c in CELLS if c["cell_id"] == "r1c1")
    g2, base = cell["glyphs"][1], cell["origin_pt"][1]
    x0, y0, x1, y1 = g2["box_pt"]
    assert lc.ink_coverage(g2, base, gen.FONT, [x0, y0, x1, y1]) == 1.0
    assert lc.ink_coverage(g2, base, gen.FONT, [x1, y0, x1 + 5, y1]) == 0.0
    half = lc.ink_coverage(g2, base, gen.FONT, [x0, y0, x0 + 2.5, y1])
    assert 0.0 < half < 1.0
    items = [
        {"text": "mm", "unit": "word", "center": [160, 694]},
        {"text": "12", "unit": "word", "center": [144, 694]},
        {"text": "x", "center": [400, 400]},
    ]
    got = lc.assign_to_cells(items, CELLS)
    assert got["cell_strings"]["r1c1"] == "12 mm"
    assert [u["text"] for u in got["unassigned"]] == ["x"]
    assert lc.cell_mismatches({"r1c1": "17 mm"}, [cell]) == [{"cell_id": "r1c1", "expected": "12 mm", "observed": "17 mm"}]


# ---------------------------------------------------------------------------
# Integrity of preserved renders (hashes only; contents are not judged)
# ---------------------------------------------------------------------------

RUN_DIRS = sorted(p.parent for p in (ROOT / "runs").glob("*/render_index.json"))


@pytest.mark.parametrize("run_dir", RUN_DIRS, ids=[p.name for p in RUN_DIRS])
def test_preserved_renders_match_recorded_hashes(run_dir):
    pil = pytest.importorskip("PIL.Image")
    index = json.loads((run_dir / "render_index.json").read_text("ascii"))
    assert index
    for rec in index.values():
        png = run_dir / rec["png"]
        assert hashlib.sha256(png.read_bytes()).hexdigest() == rec["png_sha256"]
        with pil.open(png) as im:
            assert hashlib.sha256(im.convert("RGB").tobytes()).hexdigest() == rec["pixel_sha256"]

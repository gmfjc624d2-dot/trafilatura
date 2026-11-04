# SPDX-License-Identifier: Apache-2.0
"""Pure comparison helpers (stdlib only; no renderer or extractor imported).

Coordinates: PDF points with y up (page 612 x 792). Renders are canonical
row-major RGB bytes at 2 px/pt (144 dpi), row 0 = top of page.
"""

from __future__ import annotations

import math
from typing import Any

PAGE_H = 792
PX_PER_PT = 2
BLACK, WHITE = (0, 0, 0), (255, 255, 255)


def pt_box_to_px(box: list[float], pad_pt: float = 0.0) -> tuple[int, int, int, int]:
    """[x0, y0, x1, y1] in pt (y up) -> (left, top, right, bottom) device px, exclusive."""
    x0, y0, x1, y1 = box
    return (
        math.floor((x0 - pad_pt) * PX_PER_PT),
        math.floor((PAGE_H - (y1 + pad_pt)) * PX_PER_PT),
        math.ceil((x1 + pad_pt) * PX_PER_PT),
        math.ceil((PAGE_H - (y0 - pad_pt)) * PX_PER_PT),
    )


def pixel(render: dict[str, Any], x: int, y: int) -> tuple[int, int, int]:
    i = (y * render["width"] + x) * 3
    p = render["pixels"]
    return p[i], p[i + 1], p[i + 2]


def diff_pixels(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Lossless comparison of two canonical RGB renders."""
    if (a["width"], a["height"]) != (b["width"], b["height"]):
        return {"comparable": False, "size_a": [a["width"], a["height"]], "size_b": [b["width"], b["height"]]}
    pa, pb, w = a["pixels"], b["pixels"], a["width"]
    if pa == pb:
        return {"comparable": True, "identical": True, "differing_pixels": 0}
    count, xs, ys, coords = 0, [], [], []
    for idx in range(0, len(pa), 3):
        if pa[idx : idx + 3] != pb[idx : idx + 3]:
            count += 1
            y, x = divmod(idx // 3, w)
            xs.append(x)
            ys.append(y)
            coords.append((x, y))
    out: dict[str, Any] = {"comparable": True, "identical": count == 0, "differing_pixels": count}
    if count:
        out["bbox_px"] = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
        out["_coords"] = coords  # removed before serialisation
    return out


def confined(coords: list[tuple[int, int]], boxes_px: list[tuple[int, int, int, int]]) -> dict[str, Any]:
    outside = [(x, y) for x, y in coords if not any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in boxes_px)]
    return {"pixels_checked": len(coords), "outside_count": len(outside), "outside_sample": outside[:10]}


def raster_as_render(ink: list[list[int]], origin_px: tuple[int, int], size: tuple[int, int] = (1224, 1584)) -> dict[str, Any]:
    """The page as it would look if the raster were reproduced 1:1: ink black, paper and margin white."""
    w, h = size
    buf = bytearray(b"\xff" * (w * h * 3))
    ox, oy = origin_px
    for y, row in enumerate(ink):
        for x, v in enumerate(row):
            if v:
                i = ((oy + y) * w + ox + x) * 3
                buf[i : i + 3] = b"\x00\x00\x00"
    return {"width": w, "height": h, "pixels": bytes(buf)}


def raster_region_check(render: dict[str, Any], ink: list[list[int]], origin_px: tuple[int, int]) -> dict[str, Any]:
    """Render inside the image rectangle must equal the raster exactly (ink black, paper white);
    everything outside must be white."""
    ox, oy = origin_px
    h, w = len(ink), len(ink[0])
    expected = raster_as_render(ink, origin_px, (render["width"], render["height"]))
    diff = diff_pixels(render, expected)
    inside_bad = outside_bad = 0
    inside_sample, outside_sample = [], []
    for x, y in diff.get("_coords", []):
        px = pixel(render, x, y)
        if ox <= x < ox + w and oy <= y < oy + h:
            inside_bad += 1
            if len(inside_sample) < 10:
                inside_sample.append([x, y, list(px), list(BLACK if ink[y - oy][x - ox] else WHITE)])
        else:
            outside_bad += 1
            if len(outside_sample) < 10:
                outside_sample.append([x, y, list(px)])
    return {
        "inside_mismatches": inside_bad,
        "outside_non_white": outside_bad,
        "inside_sample": inside_sample,
        "outside_sample": outside_sample,
        "exact": inside_bad == 0 and outside_bad == 0,
    }


def decode_cell(render: dict[str, Any], cell: dict[str, Any], font: dict[str, list[str]]) -> dict[str, Any]:
    """Exact template matching of the authored glyph grid (not OCR).

    Each 1 pt font pixel is a 2x2 device-pixel block; a block is ink only if all
    four pixels are pure black, paper only if all four are pure white, otherwise
    it is ambiguous and the glyph decodes to '?'.
    """
    lookup = {"".join(rows): ch for ch, rows in font.items()}
    x0, baseline = cell["origin_pt"]
    chars, ambiguous_blocks = [], 0
    for i in range(len(cell["text"])):
        bits, bad = [], False
        for r in range(9):
            row = []
            for c in range(5):
                left = (x0 + 6 * i + c) * PX_PER_PT
                top = (PAGE_H - (baseline + 7 - r)) * PX_PER_PT
                block = {pixel(render, left + dx, top + dy) for dx in (0, 1) for dy in (0, 1)}
                if block == {BLACK}:
                    row.append("#")
                elif block == {WHITE}:
                    row.append(".")
                else:
                    bad = True
                    ambiguous_blocks += 1
                    row.append("?")
            bits.append("".join(row))
        chars.append("?" if bad else lookup.get("".join(bits), "?"))
    return {"cell_id": cell["cell_id"], "decoded": "".join(chars), "ambiguous_blocks": ambiguous_blocks}


def ink_coverage(glyph: dict[str, Any], baseline: float, font: dict[str, list[str]], box: list[float]) -> float:
    """Fraction of a visible glyph's ink area (1x1 pt font pixels) inside box [x0, y0, x1, y1]."""
    gx = glyph["box_pt"][0]
    total = inside = 0.0
    bx0, by0, bx1, by1 = box
    for r, row in enumerate(font[glyph["char"]]):
        for c, v in enumerate(row):
            if v != "#":
                continue
            px0, py1 = gx + c, baseline + 7 - r
            px1, py0 = px0 + 1, py1 - 1
            total += 1
            iw = max(0.0, min(px1, bx1) - max(px0, bx0))
            ih = max(0.0, min(py1, by1) - max(py0, by0))
            inside += iw * ih
    return inside / total if total else 0.0


def assign_to_cells(items: list[dict[str, Any]], cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Assign extracted items (text + center point in pt) to the cell whose text box
    contains the center. Items outside every cell are kept as unassigned."""
    by_cell: dict[str, list[dict[str, Any]]] = {c["cell_id"]: [] for c in cells}
    unassigned = []
    for it in items:
        cx, cy = it["center"]
        hit = next(
            (
                c
                for c in cells
                if c["text_box_pt"][0] <= cx < c["text_box_pt"][2] and c["text_box_pt"][1] <= cy <= c["text_box_pt"][3]
            ),
            None,
        )
        if hit is None:
            unassigned.append(it)
        else:
            by_cell[hit["cell_id"]].append(it)
    strings = {
        cid: (" ".join if its and its[0].get("unit") == "word" else "".join)(
            i["text"] for i in sorted(its, key=lambda i: i["center"][0])
        )
        for cid, its in by_cell.items()
    }
    return {"cell_strings": strings, "unassigned": unassigned}


def cell_mismatches(strings: dict[str, str], cells: list[dict[str, Any]], key: str = "text") -> list[dict[str, str]]:
    return [
        {"cell_id": c["cell_id"], "expected": c[key], "observed": strings.get(c["cell_id"], "")}
        for c in cells
        if strings.get(c["cell_id"], "") != c[key]
    ]

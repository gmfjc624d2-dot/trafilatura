# SPDX-License-Identifier: Apache-2.0
"""Generator/manifest consistency and comparator behaviour.

These tests never run an extractor and never assert what an extractor
outputs. Expected glyph positions are re-derived here from independent
constants and an independent parse of the PDF bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import generate_fixtures as gen  # noqa: E402
import order_compare as oc  # noqa: E402

FIX = ROOT / "fixtures"
MANIFEST = json.loads((FIX / "manifest.json").read_text("ascii"))
FIXTURES = sorted(MANIFEST["fixtures"])

# Independent restatement of the fixture design (not imported from the generator).
ADVANCE = 600 / 1000 * 10  # Widths 600, Tf size 10, Tc = Tw = 0, Tz = 100
SOURCE = {
    "S1": ((72, 720), "If the blue latch is closed, do not move the crate more than 12 cm."),
    "S2": ((72, 696), "The green lamp remains on."),
    "R1": ((72, 672), "Span: 12 cm"),
    "R2": ((72, 648), "Delay: 7 s"),
}
BASE_FONTS = {"F1": "Courier", "F2": "Courier-Bold", "F3": "Courier-Oblique"}


def independent_expected() -> dict[str, tuple[str, float, float]]:
    out = {}
    for bid, ((x0, y0), text) in SOURCE.items():
        for i, ch in enumerate(text):
            out[f"{bid}:{i:02d}"] = (ch, x0 + i * ADVANCE, y0)
    return out


# ---------------------------------------------------------------------------
# Independent minimal PDF reader (only what these fixtures use)
# ---------------------------------------------------------------------------


def read_objects(pdf: bytes) -> dict[int, bytes]:
    objs = {int(n): body for n, body in re.findall(rb"(\d+) 0 obj\n(.*?)\nendobj\n", pdf, flags=re.DOTALL)}
    # cross-check the xref table
    xref_at = int(re.search(rb"startxref\n(\d+)\n%%EOF\n$", pdf).group(1))
    table = pdf[xref_at:].split(b"\n")
    assert table[0] == b"xref"
    count = int(table[1].split()[1])
    for num in range(1, count):
        off = int(table[2 + num].split()[0])
        assert pdf[off:].startswith(f"{num} 0 obj\n".encode())
    assert set(objs) == set(range(1, count))
    return objs


def content_of(objs: dict[int, bytes]) -> bytes:
    page = objs[3]
    num = int(re.search(rb"/Contents (\d+) 0 R", page).group(1))
    m = re.match(rb"<< /Length (\d+) >>\nstream\n", objs[num])
    length = int(m.group(1))
    data = objs[num][m.end() : m.end() + length]
    assert objs[num][m.end() + length :] == b"endstream"
    return data


def fonts_of(objs: dict[int, bytes]) -> dict[str, dict]:
    page = objs[3]
    fonts = {}
    for name, num in re.findall(rb"/(F\d) (\d+) 0 R", page):
        body = objs[int(num)]
        fonts[name.decode()] = {
            "BaseFont": re.search(rb"/BaseFont /([\w-]+)", body).group(1).decode(),
            "Subtype": re.search(rb"/Subtype /(\w+)", body).group(1).decode(),
            "Encoding": re.search(rb"/Encoding /(\w+)", body).group(1).decode(),
            "FirstChar": int(re.search(rb"/FirstChar (\d+)", body).group(1)),
            "LastChar": int(re.search(rb"/LastChar (\d+)", body).group(1)),
            "Widths": [int(w) for w in re.search(rb"/Widths \[([\d ]+)\]", body).group(1).split()],
            "raw": body,
        }
    return fonts


TOKEN = re.compile(rb"\((?:\\.|[^\\)])*\)|/[A-Za-z0-9]+|-?\d+(?:\.\d+)?|[A-Za-z*]+|\s+")


def simulate(content: bytes, fonts: dict[str, dict]) -> list[dict]:
    """Glyph origins from the PDF operators and the PDF's own /Widths."""
    glyphs, stack = [], []
    font = size = None
    tm = None
    pos = 0
    while pos < len(content):
        m = TOKEN.match(content, pos)
        assert m, content[pos : pos + 20]
        pos = m.end()
        tok = m.group()
        if tok.isspace():
            continue
        if tok[:1] in b"(/" or re.fullmatch(rb"-?\d+(?:\.\d+)?", tok):
            stack.append(tok)
            continue
        op = tok.decode()
        if op == "BT":
            tm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        elif op == "ET":
            tm = None
        elif op == "Tf":
            font, size = stack[0][1:].decode(), float(stack[1])
        elif op == "Tm":
            tm = [float(v) for v in stack]
            assert tm[:4] == [1.0, 0.0, 0.0, 1.0]
        elif op == "Tj":
            text = stack[0][1:-1].decode("ascii")
            f = fonts[font]
            for ch in text:
                adv = f["Widths"][ord(ch) - f["FirstChar"]] / 1000 * size
                glyphs.append({"char": ch, "origin": [tm[4], tm[5]], "base_font": f["BaseFont"], "advance": adv})
                tm[4] += adv
        else:
            raise AssertionError(f"unexpected operator {op} (fixtures use BT/ET/Tf/Tm/Tj only)")
        stack = []
    return glyphs


def parsed(name: str):
    pdf = (FIX / MANIFEST["fixtures"][name]["file"]).read_bytes()
    objs = read_objects(pdf)
    return pdf, objs, content_of(objs), fonts_of(objs)


# ---------------------------------------------------------------------------
# Generator / manifest consistency
# ---------------------------------------------------------------------------


def test_generator_reproduces_committed_files_byte_for_byte():
    _, first = gen.build_all()
    _, second = gen.build_all()
    assert first == second
    for rel, data in first.items():
        assert (FIX / rel).read_bytes() == data, rel
    on_disk = {p.relative_to(FIX).as_posix() for p in FIX.rglob("*") if p.is_file()}
    assert on_disk == set(first)


def test_declared_origins_match_independent_derivation():
    exp = independent_expected()
    chars = MANIFEST["declared_structure"]["characters"]
    assert [c["char_id"] for c in chars] == list(exp)
    for c in chars:
        ch, x, y = exp[c["char_id"]]
        assert (c["char"], c["expected_origin"], c["expected_advance"]) == (ch, [x, y], ADVANCE)
    # layout sanity: every glyph inside a 1-inch margin, baselines 24 pt apart
    for (x0, _), text in SOURCE.values():
        assert x0 >= 72 and x0 + len(text) * ADVANCE <= 612 - 72
    assert MANIFEST["page"]["MediaBox"] == [0, 0, 612, 792]


@pytest.mark.parametrize("name", FIXTURES)
def test_pdf_bytes_reparsed_independently_match_manifest(name):
    pdf, _, content, fonts = parsed(name)
    fx = MANIFEST["fixtures"][name]
    assert hashlib.sha256(pdf).hexdigest() == fx["pdf_sha256"]
    assert content.decode("ascii") == fx["content_stream"]
    sim = simulate(content, fonts)
    glyphs = fx["glyphs"]
    assert len(sim) == len(glyphs)
    for s, g in zip(sim, glyphs, strict=True):
        assert (s["char"], s["origin"], s["base_font"], s["advance"]) == (
            g["char"],
            g["origin"],
            g["base_font"],
            g["advance"],
        ), g["char_id"]
    # the PDF's geometry equals the independent expectation, glyph for glyph
    exp = independent_expected()
    assert Counter((s["char"], *s["origin"]) for s in sim) == Counter(exp.values())
    for g in glyphs:
        assert (g["char"], *g["origin"]) == exp[g["char_id"]]


def test_font_resources_declare_identical_fixed_advance():
    raws = []
    for name in FIXTURES:
        _, objs, _, fonts = parsed(name)
        assert {k: v["BaseFont"] for k, v in fonts.items()} == BASE_FONTS
        for f in fonts.values():
            assert f["Subtype"] == "Type1" and f["Encoding"] == "WinAnsiEncoding"
            assert (f["FirstChar"], f["LastChar"]) == (32, 126)
            assert f["Widths"] == [600] * 95
        raws.append({n: b for n, b in objs.items() if n != 4})
    # every object except the content stream is byte-identical across fixtures
    assert all(r == raws[0] for r in raws)


def test_only_the_declared_perturbations_differ():
    fx = MANIFEST["fixtures"]
    font_of = {n: {g["char_id"]: g["base_font"] for g in fx[n]["glyphs"]} for n in FIXTURES}
    geo = {n: sorted((g["char_id"], tuple(g["origin"])) for g in fx[n]["glyphs"]) for n in FIXTURES}
    assert all(geo[n] == geo["A"] for n in FIXTURES)
    assert set(font_of["A"].values()) == {"Courier"}
    styled = {f"S1:{i}": "Courier-Oblique" for i in (24, 25, 26)} | {f"S1:{i}": "Courier-Bold" for i in (32, 33, 34)}
    for n in ("B", "C", "D"):
        diff = {k: v for k, v in font_of[n].items() if v != "Courier"}
        assert diff == styled, n
        assert "".join(fx[n]["glyphs"][i]["char"] for i in range(24, 27)) == "sed"
    decl = MANIFEST["declared_structure"]["declared_order"]
    assert fx["A"]["drawing_order"] == fx["B"]["drawing_order"] == fx["D"]["drawing_order"] == decl
    suffix = [f"S1:{i}" for i in range(61, 67)]
    s2 = [c for c in decl if c.startswith("S2:")]
    rest = [c for c in decl if c not in suffix and c not in s2]
    head = [c for c in rest if c.startswith("S1:")]
    tail = [c for c in rest if c.startswith("R")]
    assert fx["C"]["drawing_order"] == head + s2 + suffix + tail
    lines = {n: fx[n]["content_stream"].splitlines() for n in FIXTURES}
    # C and D contain exactly the same operations, only in a different order
    assert sorted(lines["C"]) == sorted(lines["D"]) and lines["C"] != lines["D"]
    # D = B with the last S1 Tj split and one explicit Tm to the suffix origin
    assert [x for x in lines["D"] if x not in lines["B"]] == [
        "( move the crate more than ) Tj",
        "1 0 0 1 438 720 Tm",
        "(12 cm.) Tj",
    ]
    assert [x for x in lines["B"] if x not in lines["D"]] == ["( move the crate more than 12 cm.) Tj"]


@pytest.mark.parametrize("name", FIXTURES)
def test_order_fields_and_operation_indexes(name):
    fx = MANIFEST["fixtures"][name]
    content = fx["content_stream"].encode("ascii")
    glyphs = fx["glyphs"]
    assert [g["draw_seq"] for g in glyphs] == list(range(len(glyphs)))
    assert fx["drawing_order"] == [g["char_id"] for g in glyphs]
    assert fx["geometric_order"] == [g["char_id"] for g in sorted(glyphs, key=lambda g: (-g["origin"][1], g["origin"][0]))]
    assert fx["geometric_order"] == MANIFEST["declared_structure"]["declared_order"]
    assert fx["drawing_equals_declared"] == (name != "C")
    for op in fx["operations"]:
        start = op["byte_offset"]
        assert content[start : start + op["byte_length"]].decode() == op["source"]
    ops = fx["operations"]
    for run in fx["runs"]:
        op = ops[run["op_index"]]
        assert op["operator"] == "Tj" and op["operands"] == [f"({run['text']})"]
        assert [g["char_id"] for g in glyphs if g["run_id"] == run["run_id"]] == run["char_ids"]


def test_declared_tokens_are_explicit_and_fixture_independent():
    decl = MANIFEST["declared_structure"]
    for block in decl["blocks"]:
        toks = [t for t in decl["tokens"] if t["block_id"] == block["block_id"]]
        assert "".join(t["text"] for t in toks) == SOURCE[block["block_id"]][1]
    negations = [t for t in decl["tokens"] if "negation" in t["roles"]]
    assert [(t["block_id"], t["text"]) for t in negations] == [("S1", "not")]
    numbers = [(t["text"], t["measurement_id"]) for t in decl["tokens"] if t["kind"] == "number"]
    assert numbers == [("12", "S1.m1"), ("12", "R1.m1"), ("7", "R2.m1")]
    condition = "".join(t["text"] for t in decl["tokens"] if t["clause_id"] == "S1.cl1")
    assert condition == "If the blue latch is closed"
    all_roles = {r for t in decl["tokens"] for r in t["roles"]}
    assert not {r for r in all_roles if re.search(r"bold|oblique|late|split", r)}


# ---------------------------------------------------------------------------
# Comparator behaviour on synthetic strings (no extractor involved)
# ---------------------------------------------------------------------------

A_TEXT = "\n".join(text for _, text in SOURCE.values())


def test_comparator_reports_split_word_without_joining_it():
    text = A_TEXT.replace("closed", "clo sed")
    r = oc.compare_text(text, MANIFEST, "B")
    assert r["token_sequence_equals"]["declared"] is False and r["aligned_to"] is None
    assert r["identity_checks"]["closed_count"] == 0
    assert r["identity_checks"]["clo_whitespace_sed_count"] == 1
    assert {"op": "replace", "declared": ["closed"], "observed": ["clo", "sed"]} in r["diff_vs_declared"]


def test_comparator_keeps_whitespace_verbatim():
    text = A_TEXT.replace("do not", "do  not").replace("than 12", "than12")
    r = oc.compare_text(text, MANIFEST, "A")
    assert r["aligned_to"] == "declared"
    got = {tuple(m["texts"]): m["observed"] for m in r["separators"]["mismatches"]}
    assert got == {("do", "not"): "  ", ("than", "12"): ""}
    assert r["identity_checks"]["do_not_separators"] == ["  "]


def test_comparator_flags_missing_negation():
    text = A_TEXT.replace("do not move", "do move")
    r = oc.compare_text(text, MANIFEST, "A")
    assert r["identity_checks"]["not_count"] == 0
    assert r["nonspace_multiset"]["missing"] == {"n": 1, "o": 1, "t": 1}
    assert r["aligned_to"] is None


def test_comparator_detects_detached_limit_in_drawing_order_text():
    # Built from the manifest's drawing order of C, not from any extractor output.
    fx = MANIFEST["fixtures"]["C"]
    lines = []
    for run in fx["runs"]:
        if run["positioning"] == "Tm" and lines:
            lines.append("\n")
        lines.append(run["text"])
    text = "".join(lines)
    r = oc.compare_text(text, MANIFEST, "C")
    assert r["aligned_to"] == "drawing"
    ctx = r["s1_limit_context"]
    assert ctx["same_line_as_negation"] is False
    assert ctx["same_period_segment_as_negation"] is False
    assert r["period_segments"][0]["blocks"] == ["S1", "S2"]
    numbers = [m["number"] for m in r["identity_checks"]["number_unit_pairs_in_text_order"]]
    assert numbers == ["12", "12", "7"]


def test_comparator_reports_unexpected_text():
    r = oc.compare_text(A_TEXT.replace("lamp", "la�mp"), MANIFEST, "A")
    assert r["unexpected_text"] == [{"offset": A_TEXT.index("lamp") + 2, "char": "�", "codepoint": "U+FFFD"}]


def test_compare_chars_detects_moved_glyph_and_font_change():
    glyphs = MANIFEST["fixtures"]["B"]["glyphs"]

    def records(shift_index=None, font_index=None):
        out = []
        for i, g in enumerate(glyphs):
            x, y = g["origin"]
            if i == shift_index:
                x += 0.5
            out.append(
                {
                    "text": g["char"],
                    "origin": [x, y],
                    "advance": g["advance"],
                    "x0": x,
                    "x1": x + g["advance"],
                    "fontname": "Courier" if i == font_index else g["base_font"],
                }
            )
        return out

    clean = oc.compare_chars(records(), MANIFEST, "B")
    assert clean["all_checks_pass"] and clean["observed_order_equals"]["drawing"]
    moved = oc.compare_chars(records(shift_index=5), MANIFEST, "B")
    assert not moved["all_checks_pass"] and moved["unmatched_expected"] == ["S1:05"]
    refont = oc.compare_chars(records(font_index=33), MANIFEST, "B")
    assert refont["font_mismatches"] == [{"char_id": "S1:33", "observed": "Courier", "expected": "Courier-Bold"}]


# ---------------------------------------------------------------------------
# Integrity of preserved run outputs (hashes only; contents are not judged)
# ---------------------------------------------------------------------------

RUN_DIRS = sorted(p.parent for p in (ROOT / "runs").glob("*/extraction_runs.json"))


@pytest.mark.parametrize("run_dir", RUN_DIRS, ids=[p.name for p in RUN_DIRS])
def test_preserved_raw_outputs_match_recorded_hashes(run_dir):
    runs = json.loads((run_dir / "extraction_runs.json").read_text("utf-8"))
    checked = 0
    for fixture, rec in runs.items():
        assert rec["pdf_sha256"] == MANIFEST["fixtures"][fixture]["pdf_sha256"]
        for info in rec["methods"].values():
            files = info.get("raw_files") or ({info["raw_file"]: info["raw_sha256"]} if "raw_file" in info else {})
            for rel, sha in files.items():
                assert hashlib.sha256((run_dir / rel).read_bytes()).hexdigest() == sha, rel
                checked += 1
    assert checked > 0

# SPDX-License-Identifier: Apache-2.0
"""Comparison of extractor records against the fixture manifest.

Pure functions; no extractor is imported here. Nothing in this module
normalises an observed output: raw text is only *read*. Whitespace is
projected away only inside the explicitly named ``*_nonspace`` checks, and
every separator between tokens is reported verbatim in ``separators``.

Text outputs carry no glyph identity. When an observed token sequence equals
the declared (or the drawing-order) token sequence, tokens are mapped to
declared token ids *by sequence position*; that mapping is labelled with the
order it was aligned to. Otherwise no mapping is made and the mismatch is
reported with a diff.
"""

from __future__ import annotations

import difflib
import itertools
import re
from collections import Counter
from typing import Any

# Non-space token classes used by the fixture text. Anything else that is not
# whitespace is reported as unexpected text, never silently dropped.
TOKEN_RE = re.compile(r"[A-Za-z]+|[0-9]+|[.,:]")
ORIGIN_TOL = 1e-6


def observed_tokens(text: str) -> list[dict[str, Any]]:
    return [{"text": m.group(), "start": m.start(), "end": m.end()} for m in TOKEN_RE.finditer(text)]


def unexpected_text(text: str) -> list[dict[str, Any]]:
    """Characters that are neither whitespace nor part of a token."""
    out, last = [], 0
    for m in TOKEN_RE.finditer(text):
        out.extend(_odd(text, last, m.start()))
        last = m.end()
    out.extend(_odd(text, last, len(text)))
    return out


def _odd(text: str, a: int, b: int) -> list[dict[str, Any]]:
    return [{"offset": i, "char": text[i], "codepoint": f"U+{ord(text[i]):04X}"} for i in range(a, b) if not text[i].isspace()]


def declared_tokens(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in manifest["declared_structure"]["tokens"] if t["kind"] != "space"]


def token_order(manifest: dict[str, Any], fixture: str, order: str) -> list[dict[str, Any]]:
    """Non-space declared tokens in 'declared', 'drawing' or 'geometric' order."""
    toks = declared_tokens(manifest)
    if order == "declared":
        return toks
    fx = manifest["fixtures"][fixture]
    seq = fx["drawing_order"] if order == "drawing" else fx["geometric_order"]
    rank = {cid: i for i, cid in enumerate(seq)}
    return sorted(toks, key=lambda t: min(rank[c] for c in t["char_ids"]))


def _separator(text: str, a: dict[str, Any], b: dict[str, Any]) -> str:
    return text[a["end"] : b["start"]]


def compare_text(text: str, manifest: dict[str, Any], fixture: str) -> dict[str, Any]:
    decl = manifest["declared_structure"]
    obs = observed_tokens(text)
    obs_texts = [o["text"] for o in obs]
    orders = {name: token_order(manifest, fixture, name) for name in ("declared", "drawing", "geometric")}
    seq_eq = {name: obs_texts == [t["text"] for t in toks] for name, toks in orders.items()}

    result: dict[str, Any] = {
        "length": len(text),
        "newline_count": text.count("\n"),
        "unexpected_text": unexpected_text(text),
        "observed_token_texts": obs_texts,
        "token_sequence_equals": seq_eq,
    }

    # Character multiset and order, whitespace projected away (named check).
    declared_chars = [c["char"] for c in decl["characters"]]
    nonspace_obs = [ch for ch in text if not ch.isspace()]
    nonspace_decl = [ch for ch in declared_chars if not ch.isspace()]
    fx = manifest["fixtures"][fixture]
    by_id = {c["char_id"]: c["char"] for c in decl["characters"]}
    nonspace_draw = [by_id[c] for c in fx["drawing_order"] if not by_id[c].isspace()]
    c_obs, c_decl = Counter(nonspace_obs), Counter(nonspace_decl)
    result["nonspace_multiset"] = {
        "equal": c_obs == c_decl,
        "missing": dict(sorted((c_decl - c_obs).items())),
        "extra": dict(sorted((c_obs - c_decl).items())),
    }
    result["nonspace_order_equals"] = {"declared": nonspace_obs == nonspace_decl, "drawing": nonspace_obs == nonspace_draw}

    # Explicit identity checks on the raw text (regexes, no rewriting).
    result["identity_checks"] = identity_checks(text)

    # Token mapping by sequence alignment, if (and only if) an order matches.
    aligned_to = next((n for n in ("declared", "drawing") if seq_eq[n]), None)
    result["aligned_to"] = aligned_to
    if aligned_to is None:
        decl_texts = [t["text"] for t in orders["declared"]]
        result["diff_vs_declared"] = [
            {"op": op, "declared": decl_texts[i1:i2], "observed": obs_texts[j1:j2]}
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=decl_texts, b=obs_texts, autojunk=False).get_opcodes()
            if op != "equal"
        ]
        return result

    mapped = [dict(o, token_id=t["token_id"], block_id=t["block_id"]) for o, t in zip(obs, orders[aligned_to], strict=True)]
    pos_of = {m["token_id"]: i for i, m in enumerate(mapped)}
    result["separators"] = separators(text, mapped, pos_of, decl)
    result["line_membership"] = line_membership(text, mapped)
    result["period_segments"] = period_segments(text, mapped)
    result["s1_limit_context"] = limit_context(text, mapped, pos_of, decl)
    return result


def identity_checks(text: str) -> dict[str, Any]:
    do_not = [m.group(1) for m in re.finditer(r"\bdo(\s*)not\b", text)]
    measures = [
        {"number": m.group(1), "separator": m.group(2), "unit": m.group(3)}
        for m in re.finditer(r"(?<![0-9])([0-9]+)(\s*)(cm|s)\b", text)
    ]
    return {
        "not_count": len(re.findall(r"\bnot\b", text)),
        "do_not_separators": do_not,
        "closed_count": len(re.findall(r"\bclosed\b", text)),
        "clo_whitespace_sed_count": len(re.findall(r"\bclo\s+sed\b", text)),
        "numbers_in_text_order": re.findall(r"[0-9]+", text),
        "number_unit_pairs_in_text_order": measures,
    }


def separators(text: str, mapped: list[dict[str, Any]], pos_of: dict[str, int], decl: dict[str, Any]) -> dict[str, Any]:
    """Expected vs observed text between each declared adjacent token pair."""
    toks = list(decl["tokens"])
    pairs = []
    for block in decl["blocks"]:
        ids = block["token_ids"]
        nonspace = [t for t in toks if t["block_id"] == block["block_id"] and t["kind"] != "space"]
        for a, b in itertools.pairwise(nonspace):
            ia, ib = ids.index(a["token_id"]), ids.index(b["token_id"])
            expected = "".join(t["text"] for t in toks if t["token_id"] in ids[ia + 1 : ib])
            pa, pb = pos_of[a["token_id"]], pos_of[b["token_id"]]
            entry = {"pair": [a["token_id"], b["token_id"]], "texts": [a["text"], b["text"]], "expected": expected}
            if pb == pa + 1:
                entry["observed"] = _separator(text, mapped[pa], mapped[pb])
                entry["adjacent_in_output"] = True
            else:
                entry["observed"] = None
                entry["adjacent_in_output"] = False
                entry["output_positions"] = [pa, pb]
            entry["match"] = entry["observed"] == expected
            pairs.append(entry)
    return {"pairs_checked": len(pairs), "mismatches": [p for p in pairs if not p["match"]]}


def line_membership(text: str, mapped: list[dict[str, Any]]) -> dict[str, Any]:
    lines: dict[int, list[str]] = {}
    for m in mapped:
        lines.setdefault(text.count("\n", 0, m["start"]), []).append(m["block_id"])
    block_lines: dict[str, list[int]] = {}
    for ln, bids in lines.items():
        for b in dict.fromkeys(bids):
            block_lines.setdefault(b, []).append(ln)
    return {
        "lines": [
            {"line": ln, "blocks": list(dict.fromkeys(b)), "text": text.split("\n")[ln]} for ln, b in sorted(lines.items())
        ],
        "block_lines": block_lines,
        "blocks_split_across_lines": sorted(b for b, lns in block_lines.items() if len(lns) > 1),
        "lines_mixing_blocks": [ln for ln, b in sorted(lines.items()) if len(set(b)) > 1],
    }


def period_segments(text: str, mapped: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mechanical segmentation after each '.' token (not a semantic sentence model)."""
    segs, cur = [], []
    for m in mapped:
        cur.append(m)
        if m["text"] == ".":
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    return [
        {
            "blocks": list(dict.fromkeys(m["block_id"] for m in s)),
            "token_ids": [m["token_id"] for m in s],
            "text": text[s[0]["start"] : s[-1]["end"]],
        }
        for s in segs
    ]


def limit_context(text: str, mapped: list[dict[str, Any]], pos_of: dict[str, int], decl: dict[str, Any]) -> dict[str, Any]:
    """Where the S1 limit '12 cm' lands relative to its negation."""
    toks = {t["token_id"]: t for t in decl["tokens"]}
    neg = next(t for t in toks.values() if "negation" in t["roles"])
    limit = [t for t in toks.values() if t["measurement_id"] == "S1.m1" and t["kind"] != "space"]
    first, last = pos_of[limit[0]["token_id"]], pos_of[limit[-1]["token_id"]]
    pn = pos_of[neg["token_id"]]
    segs = period_segments(text, mapped)
    seg_of = {tid: i for i, s in enumerate(segs) for tid in s["token_ids"]}
    line = lambda p: text.count("\n", 0, mapped[p]["start"])  # noqa: E731
    before = mapped[first - 1] if first > 0 else None
    after = mapped[last + 1] if last + 1 < len(mapped) else None
    return {
        "negation_token": neg["token_id"],
        "limit_tokens": [t["token_id"] for t in limit],
        "same_line_as_negation": line(first) == line(pn),
        "same_period_segment_as_negation": seg_of[limit[0]["token_id"]] == seg_of[neg["token_id"]],
        "preceding_token": None
        if before is None
        else {"token_id": before["token_id"], "text": before["text"], "separator": _separator(text, before, mapped[first])},
        "following_token": None
        if after is None
        else {"token_id": after["token_id"], "text": after["text"], "separator": _separator(text, mapped[last], after)},
    }


def compare_layout_tjs(tjs: list[dict[str, Any]], manifest: dict[str, Any], fixture: str) -> dict[str, Any]:
    """pypdf layout-mode per-Tj tx/displaced_tx vs the declared run origins.

    Each fixture run is exactly one Tj operator, so Tj records pair with runs
    by stream position; the pairing is confirmed by comparing texts.
    """
    runs = manifest["fixtures"][fixture]["runs"]
    glyph = {g["char_id"]: g for g in manifest["fixtures"][fixture]["glyphs"]}
    rows = []
    # zip(strict=False) is deliberate: unequal counts are reported below, not raised.
    for tj, run in zip(tjs, runs, strict=False):
        first = glyph[run["char_ids"][0]]
        exp_tx = first["origin"][0]
        exp_end = exp_tx + sum(glyph[c]["advance"] for c in run["char_ids"])
        rows.append(
            {
                "run_id": run["run_id"],
                "positioning": run["positioning"],
                "text_matches_run": tj.get("text") == run["text"],
                "expected_tx": exp_tx,
                "observed_tx": tj.get("tx"),
                "expected_displaced_tx": exp_end,
                "observed_displaced_tx": tj.get("displaced_tx"),
                "expected_ty": first["origin"][1],
                "observed_ty": tj.get("ty"),
            }
        )
    for r in rows:
        r["tx_matches"] = r["observed_tx"] is not None and abs(r["observed_tx"] - r["expected_tx"]) <= ORIGIN_TOL
    return {
        "tj_count": len(tjs),
        "run_count": len(runs),
        "counts_match": len(tjs) == len(runs),
        "rows": rows,
        "runs_with_tx_mismatch": [r["run_id"] for r in rows if not r["tx_matches"]],
    }


# ---------------------------------------------------------------------------
# Character records (pdfplumber / pdfminer)
# ---------------------------------------------------------------------------


def compare_chars(chars: list[dict[str, Any]], manifest: dict[str, Any], fixture: str) -> dict[str, Any]:
    fx = manifest["fixtures"][fixture]
    glyphs = fx["glyphs"]
    decl_order = manifest["declared_structure"]["declared_order"]
    result: dict[str, Any] = {"count_observed": len(chars), "count_expected": len(glyphs)}

    # 1. identity by exact geometry: (char, origin) must match one glyph.
    index = {(g["char"], round(g["origin"][0], 6), round(g["origin"][1], 6)): g for g in glyphs}
    ids, unmatched = [], []
    for i, c in enumerate(chars):
        key = (c["text"], round(c["origin"][0], 6), round(c["origin"][1], 6))
        g = index.get(key)
        if g is None:
            unmatched.append({"observed_index": i, "text": c["text"], "origin": c["origin"]})
            ids.append(None)
        else:
            ids.append(g["char_id"])
    result["unmatched_observed"] = unmatched
    result["unmatched_expected"] = sorted({g["char_id"] for g in glyphs} - {i for i in ids if i})
    result["duplicate_matches"] = sorted(k for k, v in Counter(i for i in ids if i).items() if v > 1)

    # 2. per-glyph geometry and font, in observed order.
    g_by_id = {g["char_id"]: g for g in glyphs}
    dev_x = dev_y = dev_adv = dev_width = 0.0
    font_mismatch = []
    for c, cid in zip(chars, ids, strict=True):
        if cid is None:
            continue
        g = g_by_id[cid]
        dev_x = max(dev_x, abs(c["origin"][0] - g["origin"][0]))
        dev_y = max(dev_y, abs(c["origin"][1] - g["origin"][1]))
        dev_adv = max(dev_adv, abs(c["advance"] - g["advance"]))
        dev_width = max(dev_width, abs((c["x1"] - c["x0"]) - g["advance"]))
        if c["fontname"] != g["base_font"]:
            font_mismatch.append({"char_id": cid, "observed": c["fontname"], "expected": g["base_font"]})
    result["max_abs_deviation"] = {
        "origin_x": dev_x,
        "origin_y": dev_y,
        "advance": dev_adv,
        "x1_minus_x0_vs_advance": dev_width,
    }
    result["font_mismatches"] = font_mismatch

    # 3. order relations, by identity.
    result["observed_order_equals"] = {"drawing": ids == fx["drawing_order"], "declared": ids == decl_order}
    geo = [
        cid
        for (_, cid) in sorted(
            (((-c["origin"][1], c["origin"][0]), cid) for c, cid in zip(chars, ids, strict=True) if cid is not None)
        )
    ]
    result["geometric_sort_of_observed_equals_declared"] = geo == decl_order
    result["all_checks_pass"] = (
        not unmatched
        and not result["unmatched_expected"]
        and not result["duplicate_matches"]
        and not font_mismatch
        and len(chars) == len(glyphs)
        and max(dev_x, dev_y, dev_adv, dev_width) <= ORIGIN_TOL
    )
    return result

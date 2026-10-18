"""Run anchor_unit.select_unit() on every pre-registered case and grade it against expectations.

Usage: python run_experiment.py OUTPUT_DIR
Writes OUTPUT_DIR/results.json (every selection output: candidate unit, serializations, contexts,
parser diagnostics, checks) and OUTPUT_DIR/summary.md. Each check is PASS, FAIL or RECORDED (no
prediction was made). Exit code 1 if any check fails; failures are findings and are all kept.
"""

import json
import platform
import sys
from pathlib import Path

from anchor_unit import REPRESENTATIONS, select_unit

ROOT = Path(__file__).resolve().parent.parent
ORIGINS = {
    "source/numpy-2.5/numpy.where.html": "https://github.com/numpy/doc be1a2c96dd1e28fd5492efb9e9f7e3bce33bd7ab"
    " 2.5/reference/generated/numpy.where.html (published at https://numpy.org/doc/2.5/reference/generated/numpy.where.html)",
}


def check(name, ok, detail=None):
    return {"check": name, "result": "PASS" if ok else "FAIL", "detail": detail}


def recorded(name, detail):
    return {"check": name, "result": "RECORDED", "detail": detail}


def grade(case, out, regions):
    checks = []
    reasons, cand = out["reasons"], out["candidate"]
    if case["structural"] == "OK":
        checks.append(check("structural OK (no review reason)", not reasons, reasons))
    else:
        missing = [r for r in case["structural"] if r not in reasons]
        checks.append(check(f"reasons include {case['structural']}", not missing, reasons))
        extra = [r for r in reasons if r not in case["structural"]]
        if extra:
            checks.append(recorded("additional reasons", extra))
    if "unit" in case:
        want = case["unit"]
        got = cand and {k: cand[k] for k in ("signatures", "descriptions", "signature_ids")}
        checks.append(check("unit signatures/descriptions/ids", got == want, got))
    if cand:
        for rep in REPRESENTATIONS:
            payload = cand[rep]
            missing = [m for m in case.get("must_include", []) if m not in payload]
            leaked = [m for m in case.get("must_exclude", []) if m in payload]
            if case.get("must_include"):
                checks.append(check(f"{rep}: must_include", not missing, missing))
            if case.get("must_exclude"):
                checks.append(check(f"{rep}: must_exclude", not leaked, leaked))
    if case.get("raw_region"):
        region = regions[case["raw_region"]]
        expected = {"byte_start": region["byte_start"], "byte_end": region["byte_end"]}
        span = cand and cand["raw_byte_span"]
        prediction = case.get("dom_byte_identical")
        detail = {
            "raw_byte_span": span,
            "expected_region": expected,
            "occurrences": cand and cand["raw_occurrences_of_serialization"],
        }
        if prediction is True:
            checks.append(check("dom serialization byte-identical to the raw region", span == expected, detail))
        elif prediction is False:
            checks.append(check("dom serialization differs from the raw bytes", span is None, detail))
        else:
            checks.append(recorded("dom serialization vs raw region (not predicted)", detail))
    for rep, want in (case.get("budget") or {}).items():
        ctx = out["contexts"].get(rep)
        got = None if ctx is None else ("fits" if ctx["fits"] else "over")
        detail = ctx and {"context_bytes": ctx["context_bytes"], "budget_bytes": ctx["budget_bytes"]}
        if want is None:
            checks.append(recorded(f"{rep}: budget (not predicted)", {"observed": got, **(detail or {})}))
        else:
            checks.append(check(f"{rep}: budget {want}", got == want, {"observed": got, **(detail or {})}))
    return checks


def main():
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    exp = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
    regions = json.loads((ROOT / "fixtures" / "regions.json").read_text(encoding="utf-8"))["regions"]
    regions["public:numpy.where"] = json.loads((ROOT / "fixtures" / "expectations_resolved.json").read_text(encoding="utf-8"))[
        "public_region"
    ]
    results = []
    for case in exp["cases"]:
        data = (ROOT / case["file"]).read_bytes()
        origin = ORIGINS.get(case["file"], "synthetic fixture of this experiment")
        out = select_unit(data, case["anchor"], path=case["file"], origin=origin, budget=exp["budget_bytes"])
        out["case"] = case["id"]
        out["checks"] = grade(case, out, regions)
        results.append(out)
    env = {
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "machine": platform.machine(),
        **results[0]["parser"],
    }
    env.pop("diagnostics")
    env.pop("encoding")
    fails = [(r["case"], c) for r in results for c in r["checks"] if c["result"] == "FAIL"]
    (out_dir / "results.json").write_text(
        json.dumps({"environment": env, "results": results}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [
        "# Anchor-unit results (generated by scripts/run_experiment.py)",
        "",
        (
            f"Python {sys.version.split()[0]}, {platform.platform()}; lxml {env['lxml']}, libxml2 {env['libxml2_runtime']}. "
            "Status per representation: OK_STRUCTURAL_UNIT (structure only, not semantic sufficiency), REVIEW, REVIEW_OVER_BUDGET. "
            "Nothing was semantically reviewed."
        ),
        "",
        "| case | anchor | expected | reasons | dt/dd | raw span | text ctx B | text status | dom ctx B | dom status | failed checks |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for case, r in zip(exp["cases"], results, strict=True):
        cand = r["candidate"]
        failed = [c["check"] for c in r["checks"] if c["result"] == "FAIL"]
        span = cand and cand["raw_byte_span"]
        expected = case["structural"] if case["structural"] == "OK" else ", ".join(case["structural"])
        groups = f"{cand['signatures']}/{cand['descriptions']}" if cand else "-"
        span_text = f"{span['byte_start']}-{span['byte_end']}" if span else "-"
        lines.append(
            f"| {case['id']} | `{case['anchor']}` | {expected}"
            f" | {', '.join(r['reasons']) or '-'} | {groups}"
            f" | {span_text}"
            f" | {r['contexts'].get('text_content', {}).get('context_bytes', '-')} | {r['status']['text_content']}"
            f" | {r['contexts'].get('dom_serialization', {}).get('context_bytes', '-')} | {r['status']['dom_serialization']}"
            f" | {'; '.join(failed) or '-'} |"
        )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(env, indent=2))
    total = sum(len(r["checks"]) for r in results)
    print(
        f"cases: {len(results)}, checks: {total}, failed: {len(fails)}, recorded: {sum(c['result'] == 'RECORDED' for r in results for c in r['checks'])}"
    )
    for case_id, c in fails:
        print(f"  FAIL {case_id}: {c['check']} -> {c['detail']}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

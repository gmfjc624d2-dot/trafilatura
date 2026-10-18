"""Reproduce the three defects on the unmodified 7345bfe copies, before any repair exists.

Usage: python reproduce_baseline.py OUTPUT_DIR
1. the baseline helper on the five new cases: its predicted (defective) behaviour, and the
   repaired requirements, which it is predicted to fail as listed in baseline_fails;
2. the baseline helper on the 27 old cases: predicted to equal the committed results exactly;
3. the baseline comparator on the 32 mutation controls, applied to copies of the committed
   results.json in a temporary directory that the script creates and removes itself.
Writes OUTPUT_DIR/baseline_reproduction.json. Exit 1 if any observation differs from its
prediction (a finding); predicted baseline failures are kept and do not change the exit code.
"""

import json
import sys
import tempfile
from pathlib import Path

import anchor_unit_baseline_7345bfe as baseline
import grading as g

COMPARATOR = g.ROOT / "scripts" / "compare_results_baseline_7345bfe.py"


def main():
    out_dir = Path(sys.argv[1])
    problems = g.verify_inputs()
    if problems:
        print("\n".join(problems))
        return 1
    new = g.run_new_cases(baseline, "baseline", "baseline_fails")
    old = []
    for case, entry in g.old_cases():
        out = g.run_old_case(baseline, case, entry)
        committed = {k: v for k, v in entry.items() if k not in ("case", "checks")}
        same = g.strict_equal(out, committed)
        old.append({"case": case["id"], "check": g.check("baseline copy output equals the committed entry", same, "PASS")})
    mutations = []
    text = g.OLD_RESULTS.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="evidence-integrity-mutations-") as tmp:
        for m in g.EXP["mutation_controls"]["mutations"]:
            mutated = g.mutate(text, m["ops"])
            path = Path(tmp) / f"{m['id']}.json"
            path.write_text(mutated, encoding="utf-8", newline="\n")
            code, stderr, last = g.run_comparator(COMPARATOR, g.OLD_RESULTS, path)
            observed = g.classify(code, stderr, m["repaired"] == "allowed")
            mutations.append(
                {
                    "id": m["id"],
                    "what": m["what"],
                    "changes_text": mutated != text,
                    "baseline_exit": code,
                    "baseline_last_stderr_line": last if observed == "crash" else None,
                    "check": g.check(f"baseline comparator: {m['baseline']}", observed == m["baseline"], "PASS", observed),
                }
            )
    env = g.environment(baseline)
    checks = [c for r in new for c in r["checks"]] + [r["check"] for r in old] + [r["check"] for r in mutations]
    findings = [c for c in checks if c["result"] != c["predicted"]]
    # every mutation but M00 must change the text, or it controls nothing
    invalid = [m["id"] for m in mutations if m["changes_text"] != (m["id"] != "M00")]
    summary = {
        "checks": len(checks),
        "pass": sum(c["result"] == "PASS" for c in checks),
        "fail": sum(c["result"] == "FAIL" for c in checks),
        "fail_predicted (baseline failures, kept)": sum(c["result"] == "FAIL" == c["predicted"] for c in checks),
        "findings (result differs from prediction)": len(findings),
        "invalid mutations": invalid,
        "baseline comparator outcomes": {
            k: sum(m["check"]["detail"] == k for m in mutations) for k in sorted({m["check"]["detail"] for m in mutations})
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "environment": env,
        "summary": summary,
        "new_cases": new,
        "old_cases": old,
        "baseline_comparator_mutations": mutations,
    }
    (out_dir / "baseline_reproduction.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(env, indent=2))
    for r in new:
        o = r["output"]
        print(
            f"{r['case']} baseline: reasons={o['reasons']} status={o['status']} diagnostics={[(d['line'], d['type']) for d in o['parser']['diagnostics']]}"
        )
        print(f"   encoding={o['parser']['encoding']} span={(o['candidate'] or {}).get('raw_byte_span')}")
        for c in r["checks"]:
            mark = "FINDING " if c["result"] != c["predicted"] else ""
            print(
                f"   {mark}{c['result']} (predicted {c['predicted']}) {c['check']}: {json.dumps(c['detail'], ensure_ascii=False)[:150]}"
            )
    print(
        f"old cases: {sum(r['check']['result'] == 'PASS' for r in old)}/{len(old)} baseline outputs equal the committed entries"
    )
    for m in mutations:
        mark = "FINDING " if m["check"]["result"] != m["check"]["predicted"] else ""
        print(
            f"{mark}{m['id']} {m['what']}: exit {m['baseline_exit']} -> {m['check']['detail']} ({m['check']['check']}) {m['baseline_last_stderr_line'] or ''}"
        )
    print(json.dumps(summary, indent=2))
    for c in findings:
        print("FINDING", c["check"], json.dumps(c["detail"], ensure_ascii=False)[:300])
    return 1 if findings or invalid else 0


if __name__ == "__main__":
    sys.exit(main())

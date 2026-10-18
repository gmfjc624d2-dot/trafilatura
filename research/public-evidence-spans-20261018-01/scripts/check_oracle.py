"""Validate the hand-authored oracle against the fixtures, before any comparison is run.

Checks that every referenced passage exists in its case's fixture, computes each required
set's context bytes with the pre-registered block format (labels and separators included),
derives the expected decision from the rules in oracle.json and compares it with the decision
declared by hand. Writes fixtures/oracle_resolved.json (exact offsets and hashes per span).
Runs no retrieval method. Usage: python check_oracle.py   (exit code 1 on any problem)
"""

import json
import sys

from spans import BUDGET_BYTES, ROOT, context_bytes, load_passages


def decide(case, set_costs):
    if not case["answerable"]:
        return "REVIEW_EXTERNAL" if case.get("external_dependency") else "ABSTAIN_NO_EVIDENCE"
    return "SUFFICIENT_PER_ORACLE" if any(c <= BUDGET_BYTES for c in set_costs) else "ABSTAIN_BUDGET"


def main():
    passages = load_passages()
    oracle = json.loads((ROOT / "fixtures" / "oracle.json").read_text(encoding="utf-8"))
    problems, resolved = [], []
    for case in oracle["cases"]:
        fixture = case["fixture"]
        referenced = {pid for s in case["required_sets"] for pid in s["passages"]} | set(case["distractors"])
        problems.extend(
            f"{case['id']}: {pid} is not a passage of fixture {fixture}"
            for pid in sorted(referenced)
            if pid not in passages or passages[pid]["fixture_key"] != fixture
        )
        problems.extend(
            f"{case['id']}: roles do not match passages {s['passages']}"
            for s in case["required_sets"]
            if set(s["roles"]) != set(s["passages"])
        )
        if problems:
            continue
        set_costs = []
        for s in case["required_sets"]:
            ordered = sorted((passages[pid] for pid in s["passages"]), key=lambda p: p["byte_start"])
            set_costs.append(context_bytes(ordered))
        decision = decide(case, set_costs)
        if decision != case["expected_decision"]:
            problems.append(f"{case['id']}: computed {decision}, declared {case['expected_decision']}")
        resolved.append(
            {
                "case": case["id"],
                "expected_decision": decision,
                "required_sets": [
                    {"passages": s["passages"], "context_bytes_with_labels": cost, "fits_budget": cost <= BUDGET_BYTES}
                    for s, cost in zip(case["required_sets"], set_costs, strict=True)
                ],
                "spans": {
                    pid: {k: passages[pid][k] for k in ("fixture", "byte_start", "byte_end", "bytes", "chars", "sha256")}
                    for pid in sorted(referenced)
                },
            }
        )
        costs = ", ".join(f"{'+'.join(s['passages'])}={c}B" for s, c in zip(case["required_sets"], set_costs, strict=True))
        print(f"{case['id']:28} {decision:22} {costs or '(no required set)'}")
    s13, s15 = passages["S13"], passages["S15"]
    if not context_bytes([s13]) <= BUDGET_BYTES < context_bytes([s13, passages["S14"]]):
        problems.append("S13 must fit alone and not together with S14")
    if not s15["chars"] < BUDGET_BYTES < s15["bytes"]:
        problems.append("S15 must be under 2048 characters and over 2048 bytes")
    out = {"budget_bytes": BUDGET_BYTES, "budget_bytes_note": "labels and separators included", "cases": resolved}
    (ROOT / "fixtures" / "oracle_resolved.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    for p in problems:
        print("PROBLEM", p)
    print(f"cases: {len(oracle['cases'])}, problems: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

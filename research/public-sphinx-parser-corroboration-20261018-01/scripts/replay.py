"""Replay the pre-registered corroboration cases offline and grade them against their predictions.

Usage: python replay.py OUTPUT_DIR [--against COMMITTED_DIR]
Writes OUTPUT_DIR/reports/<case>.json (one per source/anchor), OUTPUT_DIR/summary.json and
OUTPUT_DIR/summary.md. Every prediction in fixtures/expectations.json becomes a check: PASS or
FAIL against the prediction, or RECORDED where none was made. Failures are kept; exit 1 if any
check fails. With --against, each written JSON is compared with the committed one by the pinned
recursive comparator of research/public-json-numeric-integrity-20261018-01, which lets only
environment.python, .platform and .machine differ; any other difference also gives exit 1.
"""

import hashlib
import json
import re
import sys
import types
from pathlib import Path

import corroborate as co

ROOT = co.ROOT
REPO = co.REPO
EXP = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
COMPARATOR = "research/public-json-numeric-integrity-20261018-01/scripts/compare_results.py"
COMPARATOR_SHA256 = "29267d535e66f03dca617b48650c83a601ba22e9d4383e50ca2af8c990596e19"
FORBIDDEN = re.compile(EXP["forbidden_report_keys"])


def keys(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k
            yield from keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from keys(v, f"{path}[{i}]")


def grade(case, rep):
    checks = []

    def chk(name, observed, predicted, *, prediction=True):
        if not prediction or predicted is None:
            checks.append({"check": name, "result": "RECORDED", "observed": observed})
        else:
            checks.append(
                {
                    "check": name,
                    "result": "PASS" if observed == predicted else "FAIL",
                    "observed": observed,
                    "predicted": predicted,
                }
            )

    def prop(name, ok, detail=None):
        checks.append({"check": f"property {name}", "result": "PASS" if ok else "FAIL", "observed": detail})

    helper = rep["existing_helper"]
    statuses = sorted(set(helper["status"].values()))
    chk("helper reasons", helper["reasons"], case["helper"]["reasons"])
    chk("helper status", statuses[0] if len(statuses) == 1 else statuses, case["helper"]["status"])
    units = {}
    for side, key in (("lxml", "diagnostics"), ("html5lib", "errors")):
        parsed, tree, want = rep["parsers"][side], rep["trees"][side], case[side]
        unit = units[side] = tree["unit"]
        chk(f"{side} encoding", parsed["selected_encoding"], want["encoding"])
        if side == "html5lib":
            chk("html5lib encoding certainty", parsed["encoding_certainty"], want["certainty"])
            observed = [[e["line"], e["code"], e["data"]] for e in parsed["errors"]]
        else:
            observed = [[d["line"], d["type"]] for d in parsed["diagnostics"]]
        chk(f"{side} {key} (line, code[, data])", observed, want[key])
        chk(f"{side} exact matches", tree["match_count"], want["matches"])
        chk(f"{side} rule reasons", tree["rule_reasons"], want["rule_reasons"])
        chk(f"{side} signatures", unit and unit["membership"]["signatures"], want["signatures"])
        chk(f"{side} descriptions", unit and unit["membership"]["descriptions"], want["descriptions"])
        chk(f"{side} unit text (exact)", unit and unit["text"], want["text"])
        chk(f"{side} links", unit and unit["links"], case["links"])
        for marker in case.get("absent_from_text", []):
            prop(f"{side} text lacks {marker}", unit is not None and marker not in unit["text"])
        prop(f"R3 {side}: more than one match gives no unit", tree["match_count"] <= 1 or unit is None)
    agreements = rep["comparison"]["agreements"]
    if units["lxml"] is not None and units["html5lib"] is not None:
        for aspect, predicted in case["agree"].items():
            chk(f"agree {aspect}", aspect in agreements, predicted)
    chk("disposition", rep["triage"]["disposition"], case["disposition"])
    pinned = EXP["pins"]["fixtures"][case["file"]]
    data = (REPO / case["file"]).read_bytes()
    prop("R1 complete original bytes", (rep["source"]["sha256"], rep["source"]["bytes"]) == (pinned, len(data)))
    for name, value in rep["checks"].items():
        prop(f"consistency {name}", value is not False, value)
    blocking = rep["parsers"]["lxml"]["diagnostics"] or rep["parsers"]["html5lib"]["errors"]
    blocking = blocking or any(rep["trees"][s]["match_count"] != 1 for s in ("lxml", "html5lib"))
    prop("R7 diagnostics or ambiguity keep REVIEW", not blocking or rep["triage"]["disposition"] == "REVIEW")
    prop(
        "R9 a helper REVIEW is never upgraded",
        all(s == "OK_STRUCTURAL_UNIT" for s in statuses) or rep["triage"]["disposition"] == "REVIEW",
    )
    bad = [p for p, k in keys(rep) if FORBIDDEN.search(k)]
    prop("R8 no forbidden report keys", not bad, bad)
    return checks


def load_comparator():
    data = (REPO / COMPARATOR).read_bytes()
    if hashlib.sha256(data).hexdigest() != COMPARATOR_SHA256:
        raise RuntimeError(f"{COMPARATOR} differs from its pinned sha256")
    module = types.ModuleType("compare_results_json_numeric")
    module.__file__ = str(REPO / COMPARATOR)
    exec(compile(data, module.__file__, "exec"), module.__dict__)  # the bytes just verified, no bytecode written
    return module


def against(out_dir, committed):
    cmp = load_comparator()
    differences = 0
    for path in sorted(committed.rglob("*.json")):
        rel = path.relative_to(committed)
        diffs = cmp.compare(cmp.load(path), cmp.load(out_dir / rel))
        differences += len(diffs)
        print(f"compare {rel}: {len(diffs)} difference(s) outside environment.python/.platform/.machine")
        for p, what, a, b in diffs[:20]:
            print(f"  DIFFERS {cmp.render(p)} ({what}): committed {cmp.short(a)} | replay {cmp.short(b)}")
    return differences


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out_dir = Path(argv[0])
    (out_dir / "reports").mkdir(parents=True, exist_ok=True)
    rows = []
    for case in EXP["cases"]:
        data = (REPO / case["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != EXP["pins"]["fixtures"][case["file"]]:
            print(f"{case['id']}: {case['file']} differs from its pin")
            return 1
        rep = co.report(data, case["anchor"], case["file"])
        (out_dir / "reports" / f"{case['id']}.json").write_text(
            json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        checks = grade(case, rep)
        rows.append(
            {
                "id": case["id"],
                "anchor": case["anchor"],
                "file": case["file"],
                "disposition": rep["triage"]["disposition"],
                "findings": [f["finding"] for f in rep["comparison"]["findings"]],
                "agreements": rep["comparison"]["agreements"],
                "checks": checks,
            }
        )
    every = [c for r in rows for c in r["checks"]]
    totals = {k: sum(c["result"] == k for c in every) for k in ("PASS", "FAIL", "RECORDED")}
    summary = {"environment": co.environment(), "request_id": EXP["request_id"], "totals": totals, "cases": rows}
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        "# Corroboration replay (generated by scripts/replay.py)",
        "",
        f"{json.dumps(summary['environment'])}",
        "",
        (
            f"checks: {totals['PASS']} pass, {totals['FAIL']} fail, {totals['RECORDED']} recorded. "
            "STRUCTURE_CORROBORATED is triage evidence only, never admission or consumer permission."
        ),
        "",
        "| case | anchor | disposition | findings | failed checks |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        failed = [c["check"] for c in r["checks"] if c["result"] == "FAIL"]
        lines.append(
            f"| {r['id']} | `{r['anchor']}` | {r['disposition']} | {', '.join(r['findings']) or '-'} | {'; '.join(failed) or '-'} |"
        )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for r in rows:
        print(f"{r['id']} {r['anchor']}: {r['disposition']} findings={r['findings']}")
        for c in r["checks"]:
            if c["result"] != "PASS":
                print(
                    f"   {c['result']} {c['check']}: observed {json.dumps(c.get('observed'), ensure_ascii=False)[:200]}"
                    + (f" predicted {json.dumps(c['predicted'], ensure_ascii=False)[:200]}" if "predicted" in c else "")
                )
    print(json.dumps(totals))
    status = 1 if totals["FAIL"] else 0
    if len(argv) == 3 and argv[1] == "--against":
        status = max(status, 1 if against(out_dir, Path(argv[2])) else 0)
    return status


if __name__ == "__main__":
    sys.exit(main())

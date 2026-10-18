"""Replay the successor once: the predecessor's eight cases and the budget witness W1, graded.

Usage: python replay.py OUTPUT_DIR [--against COMMITTED_DIR]
Needs lxml and the three retained wheels on PYTHONPATH through zipimport (REPORT.md). First every
pin in fixtures/expectations.json is checked; any mismatch stops the replay with exit 1. Then the
replay writes OUTPUT_DIR/reports/<case>.json in the order N1-N5, C17, C1, C2, W1, and also
OUTPUT_DIR/summary.json and OUTPUT_DIR/summary.md. Every prediction becomes a check: PASS or FAIL
against it, or RECORDED where none was made. Failures are kept, and any FAIL gives exit 1.

For the eight regression cases, the pre-registered unchanged fields are compared with the committed
predecessor report by the pinned json-numeric comparator. Mutation controls run on every unit.
With --against, each written JSON is compared with the committed one by the same comparator, which
lets only environment.python, .platform and .machine differ. Any other difference also gives exit 1.
"""

import hashlib
import json
import re
import sys
import types
from pathlib import Path

import text_policy as tp

co, ROOT, REPO = tp.co, tp.ROOT, tp.REPO
EXP = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
PINS = {**EXP["pins"]["code_and_wheels"], **EXP["pins"]["fixtures"], **EXP["pins"]["predecessor_results"]}
PREDECESSOR_EXP = "research/public-sphinx-parser-corroboration-20261018-01/fixtures/expectations.json"
PREDECESSOR_REPORTS = "research/public-sphinx-parser-corroboration-20261018-01/results/run1-linux-py3.12/reports"
COMPARATOR = "research/public-json-numeric-integrity-20261018-01/scripts/compare_results.py"
FORBIDDEN = re.compile(EXP["forbidden_report_keys"])
UNCHANGED = ("environment", "anchor", "source", "decoding_policy", "parsers", "name_mapping", "existing_helper", "trees")
PREDECESSOR_CHECKS = (
    "lxml_parse_diagnostics_equal_helper",
    "mirror_reasons_equal_helper",
    "mirror_membership_equals_helper",
    "lxml_text_rule_equals_helper_text_content",
)
LAYOUT = [
    "environment", "request_id", "anchor", "source", "decoding_policy", "parsers", "name_mapping", "existing_helper",
    "trees", "checks", "comparison", "observations", "text_ledger", "comparison_scope", "structural_corroboration",
    "consumer_gate",
]  # fmt: skip
NONE = object()  # no prediction


def keys(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k
            yield from keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from keys(v, f"{path}[{i}]")


def load_comparator():
    data = (REPO / COMPARATOR).read_bytes()
    if hashlib.sha256(data).hexdigest() != PINS[COMPARATOR]:
        raise RuntimeError(f"{COMPARATOR} differs from its pinned sha256")
    module = types.ModuleType("compare_results_json_numeric")
    module.__file__ = str(REPO / COMPARATOR)
    exec(compile(data, module.__file__, "exec"), module.__dict__)  # the bytes just verified, no bytecode written
    return module


def historical_r9(rep):
    "The predecessor replay's R9 (its scripts/replay.py lines 95-98), on the successor's structural axis."
    statuses = set(rep["existing_helper"]["status"].values())
    return all(s == "OK_STRUCTURAL_UNIT" for s in statuses) or rep["structural_corroboration"]["disposition"] == "REVIEW"


def corrected_r9(rep, fresh):
    "R9 as corrected_R9 in fixtures/expectations.json states it; fresh is a new pinned select_unit() result."
    helper = rep["existing_helper"]
    return {
        "a helper reasons and status unchanged": [helper["reasons"], helper["status"]] == [fresh["reasons"], fresh["status"]],
        "b any helper reason gives structural REVIEW": not helper["reasons"]
        or rep["structural_corroboration"]["disposition"] == "REVIEW",
        "c consumer_gate NOT_GRANTED": rep["consumer_gate"]["value"] == "NOT_GRANTED",
    }


def projection(doc, disposition):
    "The pre-registered unchanged fields of one report (loaded by the comparator's exact JSON loader)."
    return {
        **{k: doc[k] for k in UNCHANGED},
        "comparison": {
            "findings": [f for f in doc["comparison"]["findings"] if f["finding"] != "CONSISTENCY_CHECK_FAILED"],
            "agreements": doc["comparison"]["agreements"],
        },
        "checks": {k: doc["checks"][k] for k in PREDECESSOR_CHECKS},
        "disposition": disposition,
    }


def mutation_controls(rep, units):
    "Per tree: does the oracle tell each wrong text function apart from the rule (detected), and the M0 control."
    out = {}
    for side, unit in units.items():
        if unit is None:
            out[side] = None
            continue
        rule = rep["trees"][side]["unit"]["text"]
        oracle, _ = tp.oracle_text([n.native for n in unit])
        out[side] = {
            "oracle_equals_rule": oracle == rule,
            "M0_control_equals_rule": tp.mutant_text(unit, None) == rule,
            "detected": [m for m in tp.MUTATIONS if oracle is not None and tp.mutant_text(unit, m) != oracle],
            "equal_to_rule": [m for m in tp.MUTATIONS if tp.mutant_text(unit, m) == rule],
        }
    return out


def grade(case_id, rep, units, data, locator, predicted, cmp, written):
    checks = []

    def chk(name, observed, want=NONE):
        if want is NONE:
            checks.append({"check": name, "result": "RECORDED", "observed": observed})
        else:
            ok = "PASS" if observed == want else "FAIL"
            checks.append({"check": name, "result": ok, "observed": observed, "predicted": want})

    def prop(name, ok, detail=None):
        checks.append({"check": f"property {name}", "result": "PASS" if ok else "FAIL", "observed": detail})

    axis = rep["structural_corroboration"]
    findings = [f["finding"] for f in rep["comparison"]["findings"]]
    chk("structural disposition", axis["disposition"], predicted["disposition"])
    chk("comparison findings", findings, predicted["findings"])
    chk("helper status", rep["existing_helper"]["status"], predicted.get("helper_status", NONE))
    for side in ("lxml", "html5lib"):
        has_unit = rep["trees"][side]["unit"] is not None
        chk(f"{side}_text_rule_equals_oracle", rep["checks"][f"{side}_text_rule_equals_oracle"], True if has_unit else None)
        obs = rep["observations"]["itertext"][side]
        want = NONE if side == "lxml" or not has_unit else predicted["itertext_equals_rule"]
        chk(f"observation {side} itertext equals rule", obs and obs["equals_rule"], want)
        want = predicted.get("itertext_with_payload", NONE) if side == "html5lib" and has_unit else NONE
        chk(
            f"observation {side} itertext equals rule with comment payload",
            obs and obs["equals_rule_with_comment_payload"],
            want,
        )
    chk("observation elementtree_c_accelerated", rep["observations"]["itertext"]["elementtree_c_accelerated"])
    fresh = co.helper.select_unit(data, rep["anchor"], path=locator, origin="public fixture", budget=co.helper.BUDGET_BYTES)
    for name, ok in corrected_r9(rep, fresh).items():
        prop(f"R9 (corrected) {name}", ok)
    chk("historical R9 on the successor axes (not a requirement)", historical_r9(rep))
    prop("report layout (pre-registered changed fields)", list(rep) == LAYOUT, list(rep))
    prop(
        "checks: the four predecessor checks then the two oracle checks",
        list(rep["checks"]) == [*PREDECESSOR_CHECKS, *tp.ORACLE_CHECKS],
        list(rep["checks"]),
    )
    prop(
        "T1 itertext is no check and no finding",
        not any("itertext" in k for k in rep["checks"]) and "itertext" not in json.dumps(rep["comparison"]),
    )
    prop("T3 comparison_scope as pre-registered", rep["comparison_scope"] == EXP["comparison_scope"])
    prop("T3 the scope's attributes are the compared ones", co.SHOWN_ATTRS == ("id", "class", "href"), list(co.SHOWN_ATTRS))
    blocking = rep["parsers"]["lxml"]["diagnostics"] or rep["parsers"]["html5lib"]["errors"] or findings
    blocking = (
        blocking or any(rep["trees"][s]["match_count"] != 1 for s in ("lxml", "html5lib")) or rep["existing_helper"]["reasons"]
    )
    prop(
        "R7 diagnostics, errors, ambiguity, disagreement or helper reasons keep REVIEW",
        not blocking or axis["disposition"] == "REVIEW",
    )
    prop("R1 complete original bytes", (rep["source"]["sha256"], rep["source"]["bytes"]) == (PINS[locator], len(data)))
    bad = [p for p, k in keys(rep) if FORBIDDEN.search(k)]
    prop("R8 no forbidden report keys", not bad, bad)
    controls = mutation_controls(rep, units)
    for side, c in controls.items():
        if c is None:
            continue
        prop(f"mutation {side} oracle equals rule and M0 control", c["oracle_equals_rule"] and c["M0_control_equals_rule"])
        want = EXP["mutation_controls"]["predicted_detected"].get(case_id, {}).get(side, NONE)
        chk(f"mutation {side} detected", c["detected"], want)
        undetectable = EXP["mutation_controls"]["predicted_undetectable_by_construction"].get(case_id, NONE)
        chk(f"mutation {side} equal to the rule (undetectable by construction)", c["equal_to_rule"], undetectable)
    if "expected_text_sha256" in predicted:
        for side in ("lxml", "html5lib"):
            unit, parsed = rep["trees"][side]["unit"], rep["parsers"][side]
            chk(f"W1 {side} text identity", unit and [unit["text_utf8_bytes"], unit["text_sha256"]], predicted["text"])
            chk(f"W1 {side} links", unit and unit["links"], predicted["links"])
            chk(f"W1 {side} exact matches", rep["trees"][side]["match_count"], 1)
            chk(f"W1 {side} diagnostics/errors", parsed.get("diagnostics", parsed.get("errors")), [])
    if case_id != "W1":
        committed = cmp.load(REPO / PREDECESSOR_REPORTS / f"{case_id}.json")
        succ = cmp.load(written)  # the report as written, through the same exact loader
        diffs = cmp.compare(
            projection(committed, committed["triage"]["disposition"]),
            projection(succ, succ["structural_corroboration"]["disposition"]),
        )
        shown = [f"{cmp.render(p)} ({w}): predecessor {cmp.short(a)} | successor {cmp.short(b)}" for p, w, a, b in diffs[:20]]
        prop("unchanged fields equal the committed predecessor report", not diffs, shown)
        gone = [f["finding"] for f in committed["comparison"]["findings"] if f["finding"] == "CONSISTENCY_CHECK_FAILED"]
        chk("predecessor CONSISTENCY_CHECK_FAILED findings (removed in the successor if only itertext failed)", gone)
    return checks, controls


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out_dir = Path(argv[0])
    bad_pins = [rel for rel, pin in PINS.items() if hashlib.sha256((REPO / rel).read_bytes()).hexdigest() != pin]
    print(f"repository: {REPO}")
    print(f"pins: {len(PINS)} files checked, {len(bad_pins)} differ {bad_pins}")
    if bad_pins:
        return 1
    deps = tp.dependencies()
    for name, d in deps.items():
        print(
            f"dependency {name} {d['version']}: zipimported from {d['wheel']}={d['zipimported_from_wheel']} sha256 matches pin={d['matches_pin']}"
        )
    print(f"lxml {co.lxml.__version__} from {Path(co.lxml.__file__).parent} (not pinned by hash; platform binary)")
    cmp = load_comparator()
    regression = EXP["regression"]["predictions"]
    w = EXP["witness"]
    cases = [
        {
            "id": c["id"],
            "file": c["file"],
            "anchor": c["anchor"],
            "predicted": {
                **regression[c["id"]],
                "itertext_equals_rule": c["id"] != "C2",  # regression.itertext_observation
                **({"itertext_with_payload": True} if c["id"] == "C2" else {}),
            },
        }
        for c in json.loads((REPO / PREDECESSOR_EXP).read_text(encoding="utf-8"))["cases"]
    ]
    cases.append(
        {
            "id": w["id"],
            "file": w["file"],
            "anchor": w["anchor"],
            "predicted": {
                "disposition": w["successor_prediction"]["structural_disposition"],
                "findings": [],
                "helper_status": w["successor_prediction"]["helper_status"],
                "itertext_equals_rule": w["successor_prediction"]["itertext_equals_rule"]["html5lib"],
                "expected_text_sha256": w["expected_text_sha256"],
                "text": [w["expected_text_utf8_bytes"], w["expected_text_sha256"]],
                "links": w["expected_links"],
            },
        }
    )
    (out_dir / "reports").mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases:
        data = (REPO / case["file"]).read_bytes()
        rep, units = tp.analyse(data, case["anchor"], case["file"])
        written = out_dir / "reports" / f"{case['id']}.json"
        write(written, rep)
        checks, controls = grade(case["id"], rep, units, data, case["file"], case["predicted"], cmp, written)
        rows.append(
            {
                "id": case["id"],
                "anchor": case["anchor"],
                "file": case["file"],
                "structural_disposition": rep["structural_corroboration"]["disposition"],
                "existing_helper_status": rep["existing_helper"]["status"],
                "consumer_gate": rep["consumer_gate"]["value"],
                "findings": [f["finding"] for f in rep["comparison"]["findings"]],
                "mutation_controls": controls,
                "checks": checks,
            }
        )
    global_checks = [
        {
            "check": f"dependency {name} is the pinned wheel through zipimport",
            "result": "PASS" if d["matches_pin"] else "FAIL",
            "observed": d,
        }
        for name, d in deps.items()
    ]
    every = global_checks + [c for r in rows for c in r["checks"]]
    totals = {k: sum(c["result"] == k for c in every) for k in ("PASS", "FAIL", "RECORDED")}
    summary = {
        "environment": co.environment(),
        "request_id": EXP["request_id"],
        "implementation": {
            rel: hashlib.sha256((REPO / rel).read_bytes()).hexdigest()
            for rel in (
                f"{ROOT.relative_to(REPO).as_posix()}/scripts/text_policy.py",
                f"{ROOT.relative_to(REPO).as_posix()}/scripts/replay.py",
                tp.PREDECESSOR,
                co.HELPER,
                COMPARATOR,
            )
        },
        "dependencies": deps,
        "totals": totals,
        "global_checks": global_checks,
        "cases": rows,
    }
    write(out_dir / "summary.json", summary)
    lines = [
        "# Text-policy replay (generated by scripts/replay.py)",
        "",
        json.dumps(summary["environment"]),
        "",
        (
            f"checks: {totals['PASS']} pass, {totals['FAIL']} fail, {totals['RECORDED']} recorded. Three separate axes "
            "per case; consumer_gate is NOT_GRANTED everywhere: nothing here is admission, a size fit, semantic "
            "sufficiency or permission to dispatch a model."
        ),
        "",
        "| case | anchor | structural axis | existing helper status (dom / text) | consumer gate | findings | failed checks |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        failed = [c["check"] for c in r["checks"] if c["result"] == "FAIL"]
        st = r["existing_helper_status"]
        lines.append(
            f"| {r['id']} | `{r['anchor']}` | {r['structural_disposition']} | {st['dom_serialization']} / {st['text_content']} "
            f"| {r['consumer_gate']} | {', '.join(r['findings']) or '-'} | {'; '.join(failed) or '-'} |"
        )
    lines += ["", "| case | tree | oracle = rule | mutants detected | mutants equal to the rule |", "|---|---|---|---|---|"]
    for r in rows:
        for side, c in r["mutation_controls"].items():
            if c is not None:
                lines.append(
                    f"| {r['id']} | {side} | {c['oracle_equals_rule']} | {', '.join(c['detected']) or '-'} | {', '.join(c['equal_to_rule']) or '-'} |"
                )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for c in global_checks:
        if c["result"] != "PASS":
            print(f"   {c['result']} {c['check']}: {json.dumps(c['observed'])}")
    for r in rows:
        print(
            f"{r['id']} {r['anchor']}: structural={r['structural_disposition']} helper={r['existing_helper_status']} gate={r['consumer_gate']} findings={r['findings']}"
        )
        for side, c in r["mutation_controls"].items():
            if c is not None:
                print(
                    f"   mutation {side}: oracle=rule {c['oracle_equals_rule']} detected={c['detected']} equal_to_rule={c['equal_to_rule']}"
                )
        for c in r["checks"]:
            if c["result"] != "PASS":
                print(
                    f"   {c['result']} {c['check']}: observed {json.dumps(c.get('observed'), ensure_ascii=False)[:240]}"
                    + (f" predicted {json.dumps(c['predicted'], ensure_ascii=False)[:240]}" if "predicted" in c else "")
                )
    print(json.dumps(totals))
    status = 1 if totals["FAIL"] else 0
    if len(argv) == 3 and argv[1] == "--against":
        differences = 0
        committed = Path(argv[2])
        for path in sorted(committed.rglob("*.json")):
            rel = path.relative_to(committed)
            diffs = cmp.compare(cmp.load(path), cmp.load(out_dir / rel))
            differences += len(diffs)
            print(f"compare {rel.as_posix()}: {len(diffs)} difference(s) outside environment.python/.platform/.machine")
            for p, what, a, b in diffs[:20]:
                print(f"  DIFFERS {cmp.render(p)} ({what}): committed {cmp.short(a)} | replay {cmp.short(b)}")
        status = max(status, 1 if differences else 0)
    return status


if __name__ == "__main__":
    sys.exit(main())

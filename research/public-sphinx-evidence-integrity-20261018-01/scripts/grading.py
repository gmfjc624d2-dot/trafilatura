"""Grading shared by reproduce_baseline.py and run_experiment.py (written before the repair).

Every check is {"check", "result", "predicted", "detail"}: result is what happened (PASS or
FAIL), predicted is what fixtures/expectations.json said would happen. A check whose result
differs from its prediction is a finding. Baseline failures are checks with result FAIL that
were predicted to fail; they are kept, never removed.
"""

import codecs
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import lxml.html

ROOT = Path(__file__).resolve().parent.parent
EXP = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
FACTS = json.loads((ROOT / "fixtures" / "byte_facts.json").read_text(encoding="utf-8"))
FILES = json.loads((ROOT / "fixtures" / "files.json").read_text(encoding="utf-8"))["files"]
OLD_ROOT = (ROOT / EXP["old_inputs"]["root"]).resolve()
OLD_RESULTS = OLD_ROOT / "results/run1-linux-py3.12/results.json"
REPRESENTATIONS = ("dom_serialization", "text_content")
FORBIDDEN = re.compile(EXP["forbidden_output_key_pattern"])
REMOVED_CANDIDATE_KEYS = ("raw_byte_span", "raw_occurrences_of_serialization", "diagnostics_in_unit_lines")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check(name, ok, predicted, detail=None):
    return {"check": name, "result": "PASS" if ok else "FAIL", "predicted": predicted, "detail": detail}


def strict_equal(a, b):
    "Equality that keeps JSON types apart (true vs 1, 1 vs 1.0) and object key order."
    return json.dumps(a, ensure_ascii=False) == json.dumps(b, ensure_ascii=False)


def verify_inputs():
    "Pinned inputs of the previous increment, the baseline copies, and the fixture identities."
    problems = [
        f"old input {rel}: sha256 differs"
        for rel, digest in EXP["old_inputs"]["sha256"].items()
        if sha256((OLD_ROOT / rel).read_bytes()) != digest
    ]
    problems += [
        f"{copy_}: not byte-identical to the previous {orig}"
        for copy_, orig in EXP["baseline_copies"].items()
        if (ROOT / copy_).read_bytes() != (OLD_ROOT / orig).read_bytes()
    ]
    problems += [
        f"{rel}: identity differs from files.json"
        for rel, meta in FILES.items()
        if sha256((ROOT / rel).read_bytes()) != meta["sha256"]
    ]
    return problems


def environment(helper):
    import platform

    v = helper.versions()
    return {"python": sys.version.replace("\n", " "), "platform": platform.platform(), "machine": platform.machine(), **v}


def fresh_diagnostics(data):
    "The complete error log of an independent parse of the same bytes."
    parser = lxml.html.HTMLParser()
    lxml.html.document_fromstring(data, parser=parser)
    return [
        {"line": e.line, "column": e.column, "level": e.level_name, "type": e.type_name, "message": e.message.strip()}
        for e in parser.error_log
    ]


def forbidden_keys(obj, path="$"):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if FORBIDDEN.search(k):
                found.append(f"{path}.{k}")
            found += forbidden_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += forbidden_keys(v, f"{path}[{i}]")
    return found


def codec_name(encoding):
    try:
        return codecs.lookup(encoding).name
    except (LookupError, TypeError):
        return None


def requirement_checks(case, out, data, *, prefix, fails_expected):
    "The case's requirements, in their pre-registered order."
    cand, checks = out["candidate"], []
    for name, want in case["requirements"].items():
        predicted = "FAIL" if name in fails_expected else "PASS"
        if name in ("reasons", "status"):
            ok, detail = strict_equal(out[name], want), out[name]
        elif name == "unit":
            got = cand and {k: cand[k] for k in ("signatures", "descriptions", "signature_ids")}
            ok, detail = strict_equal(got, want), got
        elif name == "must_include":
            detail = [[rep, m] for rep in REPRESENTATIONS for m in want if not cand or m not in cand[rep]]
            ok = not detail
        elif name == "must_exclude":
            detail = [[rep, m] for rep in REPRESENTATIONS for m in want if cand and m in cand[rep]]
            ok = not detail
        elif name == "payloads":
            got = cand and {rep: cand[rep] for rep in want}
            ok, detail = strict_equal(got, want), got
        elif name == "diagnostics":
            got = out["parser"]["diagnostics"]
            ok = len(got) == len(want) and all(
                all(d.get(k) == v for k, v in w.items()) for d, w in zip(got, want, strict=False)
            )
            detail = got
        elif name == "diagnostics_complete":
            fresh = fresh_diagnostics(data)
            ok, detail = strict_equal(out["parser"]["diagnostics"], fresh), {"independent_parse": len(fresh)}
        elif name == "no_alignment_claim":
            detail = forbidden_keys(out)
            ok = not detail
        elif name == "identities":
            src = out["source"]
            bad = [] if (src["sha256"], src["bytes"]) == (sha256(data), len(data)) else ["file"]
            if cand:
                for rep, key in (("dom_serialization", "dom"), ("text_content", "text")):
                    raw = cand[rep].encode("utf-8")
                    if (cand[f"{key}_sha256"], cand[f"{key}_bytes"]) != (sha256(raw), len(raw)):
                        bad.append(rep)
            ok, detail = not bad, bad
        elif name == "identities_distinct":
            ids = [out["source"]["sha256"], cand and cand["dom_sha256"], cand and cand["text_sha256"]]
            ok, detail = None not in ids and len(set(ids)) == 3, ids
        elif name == "encoding_codec":
            got = codec_name(out["parser"]["encoding"])
            ok, detail = got == want, {"parser.encoding": out["parser"]["encoding"], "codec": got}
        elif name == "budget_scope":
            scopes = {rep: ctx.get("scope") for rep, ctx in out["contexts"].items()}
            ok = bool(scopes) and all(s == EXP["budget_scope"] for s in scopes.values())
            detail = scopes
        elif name == "context_withheld":
            shown = [
                rep for rep, ctx in out["contexts"].items() if out["status"][rep] != "OK_STRUCTURAL_UNIT" and ctx["context"]
            ]
            ok, detail = not shown, shown
        else:
            raise KeyError(name)
        checks.append(check(f"{prefix}requirement {name}", ok, predicted, detail))
    return checks


def baseline_prediction_checks(case, out, data):
    "What the pre-registration says the 7345bfe helper does on this case (the defect)."
    cand, checks = out["candidate"] or {}, []
    span = cand.get("raw_byte_span")
    for name, want in case["baseline_prediction"].items():
        if name in ("reasons", "status"):
            got = out[name]
        elif name in ("first_line", "last_line", "diagnostics_in_unit_lines", "raw_byte_span", "dom_serialization"):
            got = cand.get(name)
        elif name == "raw_occurrences_of_serialization":
            got = cand.get(name)
        elif name == "diagnostic_lines":
            got = [d["line"] for d in out["parser"]["diagnostics"]]
        elif name == "raw_byte_span_region":
            region = FACTS["regions"][want]
            want = {"byte_start": region["byte_start"], "byte_end": region["byte_end"]}
            got = span
        elif name == "encoding_codec":
            got = codec_name(out["parser"]["encoding"])
        elif name == "span_bytes_equal_utf8_serialization":
            got = span and data[span["byte_start"] : span["byte_end"]] == cand["dom_serialization"].encode("utf-8")
        elif name == "span_length_minus_dom_bytes":
            got = span and (span["byte_end"] - span["byte_start"]) - cand["dom_bytes"]
        else:
            raise KeyError(name)
        checks.append(
            check(f"baseline prediction {name}", strict_equal(got, want), "PASS", {"observed": got, "predicted": want})
        )
    return checks


def run_new_cases(helper, label, fails_key):
    "Select every new case with this helper and grade it; fails_key names the predicted requirement failures."
    rows = []
    for case in EXP["new_cases"]:
        data = (ROOT / case["file"]).read_bytes()
        out = helper.select_unit(data, case["anchor"], path=case["file"], origin=case["origin"], budget=EXP["budget_bytes"])
        checks = baseline_prediction_checks(case, out, data) if label == "baseline" else []
        fails = case["baseline_fails"] if fails_key == "baseline_fails" else []
        checks += requirement_checks(case, out, data, prefix=f"{label}: ", fails_expected=fails)
        rows.append({"case": case["id"], "helper": label, "output": out, "checks": checks})
    return rows


def old_cases():
    "The 27 old cases with the committed entries (inputs read from the previous directory)."
    old_exp = json.loads((OLD_ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
    committed = json.loads(OLD_RESULTS.read_text(encoding="utf-8"))["results"]
    return list(zip(old_exp["cases"], committed, strict=True))


def run_old_case(helper, case, entry):
    data = (OLD_ROOT / case["file"]).read_bytes()
    return helper.select_unit(
        data, case["anchor"], path=case["file"], origin=entry["source"]["origin"], budget=EXP["budget_bytes"]
    )


def transform_old(entry):
    "T of the pre-registration: the predicted repaired output for a committed old entry."
    out = {k: v for k, v in copy.deepcopy(entry).items() if k not in ("case", "checks")}
    reasons = [r for r in out["reasons"] if r != "PARSER_RECOVERY_IN_UNIT"]
    if out["parser"]["diagnostics"]:
        reasons.append("PARSER_DIAGNOSTICS_PRESENT")
    out["reasons"] = reasons
    if out["candidate"] is not None:
        for key in REMOVED_CANDIDATE_KEYS:
            del out["candidate"][key]
    for ctx in out["contexts"].values():
        ctx["scope"] = EXP["budget_scope"]
    return out


def old_regrade(case, out):
    "The previous expectations re-evaluated unedited (raw_region is not applicable after R2)."
    predicted_fail = {(f["case"], f["check"]) for f in EXP["old_cases"]["predicted_regrade_failures"]}

    def c(name, ok, detail):
        return check(name, ok, "FAIL" if (case["id"], name) in predicted_fail else "PASS", detail)

    checks, reasons, cand = [], out["reasons"], out["candidate"]
    if case["structural"] == "OK":
        checks.append(c("structural OK (no review reason)", not reasons, reasons))
    else:
        missing = [r for r in case["structural"] if r not in reasons]
        checks.append(c(f"reasons include {case['structural']}", not missing, reasons))
        extra = [r for r in reasons if r not in case["structural"]]
        want = EXP["old_cases"]["predicted_regrade_additional_reasons"].get(case["id"], [])
        if extra or want:
            checks.append(c("additional reasons as predicted", extra == want, extra))
    if "unit" in case:
        got = cand and {k: cand[k] for k in ("signatures", "descriptions", "signature_ids")}
        checks.append(c("unit signatures/descriptions/ids", got == case["unit"], got))
    if cand:
        for rep in REPRESENTATIONS:
            if case.get("must_include"):
                missing = [m for m in case["must_include"] if m not in cand[rep]]
                checks.append(c(f"{rep}: must_include", not missing, missing))
            if case.get("must_exclude"):
                leaked = [m for m in case["must_exclude"] if m in cand[rep]]
                checks.append(c(f"{rep}: must_exclude", not leaked, leaked))
    if case.get("raw_region"):
        checks.append({"check": "raw region", "result": "NOT_APPLICABLE", "predicted": "NOT_APPLICABLE", "detail": "R2"})
    for rep, want in (case.get("budget") or {}).items():
        ctx = out["contexts"].get(rep)
        got = None if ctx is None else ("fits" if ctx["fits"] else "over")
        detail = {"observed": got, "context_bytes": ctx and ctx["context_bytes"]}
        if want is not None:
            checks.append(c(f"{rep}: budget {want}", got == want, detail))
    return checks


def resolve(doc, path):
    for p in path:
        doc = doc[p]
    return doc


def apply_op(doc, op):
    kind, path = op["op"], op.get("path", [])
    if kind == "add":
        resolve(doc, path)[op["key"]] = op["value"]
    elif kind == "swap":
        lst = resolve(doc, path)
        lst[op["i"]], lst[op["j"]] = lst[op["j"]], lst[op["i"]]
    elif kind == "pop":
        resolve(doc, path).pop()
    elif kind == "reverse":
        resolve(doc, path).reverse()
    elif kind == "reorder_keys":
        obj = resolve(doc, path)
        items = list(obj.items())[::-1]
        obj.clear()
        obj.update(items)
    else:
        parent, key = resolve(doc, path[:-1]), path[-1]
        if kind == "set":
            parent[key] = op["value"]
        elif kind == "delete":
            del parent[key]
        elif kind == "bool_to_int":
            assert type(parent[key]) is bool
            parent[key] = int(parent[key])
        elif kind == "to_float":
            assert type(parent[key]) is int
            parent[key] = float(parent[key])
        elif kind == "append_text":
            parent[key] += op["text"]
        else:
            raise KeyError(kind)


def mutate(text, ops):
    "Apply the dict operations to a parsed copy, then the text replacements to its serialization."
    dict_ops = [o for o in ops if o["op"] != "text_replace"]
    if dict_ops:
        doc = json.loads(text)
        for op in dict_ops:
            apply_op(doc, op)
        text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    for op in ops:
        if op["op"] == "text_replace":
            assert text.count(op["old"]) == 1, op
            text = text.replace(op["old"], op["new"], 1)
    return text


def classify(exit_code, stderr, permitted):
    if "Traceback (most recent call last)" in stderr:
        return "crash"
    if exit_code == 0:
        return "allowed" if permitted else "missed"
    if exit_code == 2:
        return "rejected"
    return "false_alarm" if permitted else "detected"


def run_comparator(script, a, b):
    proc = subprocess.run([sys.executable, str(script), str(a), str(b)], capture_output=True, text=True, check=False)
    last = (proc.stderr.strip().splitlines() or [""])[-1]
    return proc.returncode, proc.stderr, last

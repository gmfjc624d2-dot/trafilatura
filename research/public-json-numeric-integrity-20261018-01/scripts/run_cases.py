"""Run one comparator on every pre-registered case and grade it (written before the repair).

Usage: python run_cases.py {baseline|repaired} OUTPUT_DIR
* CLI cases: the comparator script as a subprocess on each fixture pair (PYTHONIOENCODING=utf-8, strict);
  the four generated inputs are rebuilt in a temporary directory that this script creates and removes.
* in-process cases A01-A16, the retained-JSON self-comparison and the derived mutations.
Writes OUTPUT_DIR/cases.json (compared on replay) and OUTPUT_DIR/interpreter_observations.json
(executed evidence about this interpreter; versions differ, so it is not part of the replay
comparison). Each check has a result and its pre-registered prediction; exit 1 if any differs.
Standard library only.
"""

import decimal
import hashlib
import importlib
import json
import json.scanner
import math
import os
import platform
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import build_fixtures

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
EXP = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
FILES = json.loads((ROOT / "fixtures" / "files.json").read_text(encoding="utf-8"))
MODULES = {"baseline": "compare_results_baseline_9a7933f", "repaired": "compare_results"}
INT_DIGITS_AT_START = sys.get_int_max_str_digits()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check(name, ok, predicted, detail=None):
    return {"check": name, "result": "PASS" if ok else "FAIL", "predicted": predicted, "detail": detail}


def same(a, b):
    return json.dumps(a, sort_keys=False) == json.dumps(b, sort_keys=False)


def verify_inputs():
    problems = [p for p, m in FILES["files"].items() if sha256((ROOT / p).read_bytes()) != m["sha256"]]
    problems += [k for k, d in build_fixtures.generated().items() if sha256(d) != FILES["generated"][k]["sha256"]]
    base = ROOT / EXP["baseline"]["file"]
    if sha256(base.read_bytes()) != EXP["baseline"]["sha256"]:
        problems.append(EXP["baseline"]["file"])
    return problems


def classify(code, stderr):
    if "Traceback (most recent call last)" in stderr:
        return "crash"
    return {0: "equal", 1: "different", 2: "invalid"}.get(code, f"exit:{code}")


def run_cli(script, a, b, subs):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(script), str(a), str(b)], capture_output=True, env=env, timeout=300, check=False
    )
    out = proc.stdout.decode("utf-8", "backslashreplace")
    err = proc.stderr.decode("utf-8", "backslashreplace")
    for old, new in subs:
        out, err = out.replace(old, new), err.replace(old, new)
    lines = [ln if len(ln) <= 2000 else ln[:2000] + f"... ({len(ln)} chars)" for ln in out.splitlines()]
    return proc.returncode, classify(proc.returncode, err), lines, (err.strip().splitlines() or [""])[-1]


def cli_rows(label, script, tmp):
    paths = {f"generated:{k}": Path(tmp) / f"{k}.json" for k in build_fixtures.generated()}
    for k, data in build_fixtures.generated().items():
        paths[f"generated:{k}"].write_bytes(data)
    subs = [(str(Path(tmp)), "<generated>"), (str(ROOT), "<root>")]
    rows = []
    for case in EXP["cli_cases"]:
        a = paths.get(case["committed"], ROOT / case["committed"])
        b = paths.get(case["replay"], ROOT / case["replay"])
        code, observed, lines, last = run_cli(script, a, b, subs)
        text = "\n".join(lines) + "\n" + last
        req, pred = case["requirement"], case["baseline_prediction"]
        checks = []
        if label == "repaired":
            checks.append(check("requirement outcome", observed == req["outcome"], "PASS", observed))
            missing = [s for s in req["stdout_contains"] if not any(s in ln for ln in lines)]
            checks.append(check("requirement diagnostics", not missing, "PASS", missing))
        else:
            checks.append(check("baseline prediction outcome", observed == pred["outcome"], "PASS", observed))
            missing = [s for s in pred["output_contains"] if s not in text]
            checks.append(check("baseline prediction output", not missing, "PASS", missing))
            meets = pred["outcome"] == req["outcome"]
            checks.append(check("requirement outcome", observed == req["outcome"], "PASS" if meets else "FAIL", observed))
        rows.append(
            {
                "id": case["id"],
                "exit": code,
                "observed": observed,
                "stdout": lines,
                "stderr_last_line": last if observed == "crash" else None,
                "checks": checks,
            }
        )
    return rows


def outcome(fn):
    try:
        value = fn()
    except Exception as err:
        return f"error:{type(err).__name__}"
    return value if isinstance(value, str) else "ok"


def verdict(mod, a, b):
    return outcome(lambda: "different" if mod.compare(a, b) else "equal")


def text_verdict(mod, a, b):
    return outcome(lambda: "different" if mod.compare(mod.loads(a), mod.loads(b)) else "equal")


def nested(depth):
    value = []
    for _ in range(depth - 1):
        value = [value]
    return value


def a01(mod, label):
    cases = {c["id"]: c for c in EXP["cli_cases"]}
    ids = [i for i in cases if i[0] in "KEZ"]
    texts = {i: [(ROOT / cases[i][side]).read_text(encoding="utf-8") for side in ("committed", "replay")] for i in ids}
    key = "requirement" if label == "repaired" else "baseline_prediction"
    expected = {i: cases[i][key]["outcome"] for i in ids}
    default = {i: text_verdict(mod, *texts[i]) for i in ids}
    with decimal.localcontext() as ctx:
        ctx.prec, ctx.Emax, ctx.Emin = 1, 1, -1
        ctx.clear_flags()
        for signal in list(ctx.traps):
            ctx.traps[signal] = True

        def state():
            return (ctx.prec, ctx.Emax, ctx.Emin, ctx.rounding, ctx.capitals, ctx.clamp, dict(ctx.traps), dict(ctx.flags))

        before = state()
        low = {i: text_verdict(mod, *texts[i]) for i in ids}
        unchanged = state() == before and decimal.getcontext() is ctx
    obs = {"verdicts": default, "low_precision_equals_default": low == default, "caller_context_unchanged": unchanged}
    exp = {"verdicts": expected, "low_precision_equals_default": True, "caller_context_unchanged": True}
    return obs, exp


def api_observations(mod):
    env_a = '{"environment":{"python":"3.12.3","platform":"p","machine":"m","lxml":"6.1.3"}}'
    env_b = '{"environment":{"python":"3.12.14","platform":"p","machine":"m","lxml":"6.1.3"}}'
    limit = EXP["limits"]["MAX_INPUT_BYTES"]

    class S(str):  # stands in for lxml's str subclasses
        __slots__ = ()

    def a03():
        tenth = 0.1
        x = mod.as_json({"x": tenth})["x"]
        return {
            "collision_after_as_json": verdict(
                mod, mod.as_json({"x": 9007199254740993.0}), mod.as_json({"x": 9007199254740992.0})
            ),
            "x_type": mod.json_type(x),
            "x_text": str(x),
            "emitted_equals_binary_exact": x == Decimal(tenth),  # Decimal(float) is the exact binary value
        }

    def a14():
        v = mod.loads("-0.0")
        return {
            "type": mod.json_type(v),
            "negative_sign": v.is_signed() if isinstance(v, Decimal) else math.copysign(1.0, v) < 0,
        }

    def a15():
        a, b = mod.loads(env_a), mod.loads(env_b)
        return {
            "default": [mod.render(p) for p, *_ in mod.compare(a, b)],
            "no_exceptions": [mod.render(p) for p, *_ in mod.compare(a, b, exceptions=())],
        }

    before = sys.get_int_max_str_digits()
    mod.compare(mod.loads('{"x":12,"y":1.5}'), mod.loads('{"x":12,"y":1.5}'))
    return {
        "A02": {"unchanged": INT_DIGITS_AT_START == before == sys.get_int_max_str_digits()},
        "A03": a03(),
        "A04": outcome(lambda: mod.as_json({"x": float("nan")})),
        "A05": outcome(lambda: mod.as_json({"x": float("inf")})),
        "A06": outcome(lambda: mod.as_json({"x": Decimal("1.5")})),
        "A07": outcome(lambda: type(mod.as_json({"x": S("a")})["x"]).__name__),
        "A08": verdict(mod, {"x": 1.0}, {"x": 1.0}),
        "A09": verdict(mod, {"x": Decimal("NaN")}, {"x": Decimal("NaN")}),
        "A10": verdict(mod, nested(5000), nested(5000)),
        "A11": verdict(mod, nested(33), nested(33)),
        "A12": verdict(mod, nested(32), nested(32)),
        "A13": {"type": mod.json_type(mod.loads("-0")), "text": str(mod.loads("-0"))},
        "A14": a14(),
        "A15": a15(),
        "A16": outcome(lambda: mod.loads('{"x":"' + "a" * (limit - 7) + '"}') and "ok"),
    }


def api_rows(mod, label):
    obs = api_observations(mod)
    rows = []
    for cid, spec in EXP["api_cases"].items():
        if cid == "A01":
            got, want = a01(mod, label)
            req_want = a01(mod, "repaired")[1] if label == "baseline" else want
        else:
            got, want, req_want = obs[cid], spec[label], spec["repaired"]
        checks = [check(f"{label} expectation", same(got, want), "PASS", got)]
        if label == "baseline":
            checks.append(check("requirement", same(got, req_want), "PASS" if same(want, req_want) else "FAIL", got))
        rows.append({"id": cid, "observed": got, "checks": checks})
    return rows


def number_types(mod, doc):
    counts, stack = {}, [doc]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack += node.values()
        elif isinstance(node, list):
            stack += node
        elif type(node) is not bool and isinstance(node, (int, float, Decimal)):
            counts[mod.json_type(node)] = counts.get(mod.json_type(node), 0) + 1
    return dict(sorted(counts.items()))


def no_float(token):
    raise ValueError(f"float token {token} in a file mutated through a plain json round trip")


def retained_rows(mod, script, label, tmp):
    listed = json.loads((ROOT / "results" / "measurement" / "retained_json.json").read_text(encoding="utf-8"))["files"]
    rows = []
    for rel, meta in listed.items():
        data = (REPO / rel).read_bytes()
        obs = {"sha256_pinned": sha256(data) == meta["sha256"]}
        try:
            doc = mod.loads(data.decode("utf-8"))
            obs.update(loads="ok", self_equal=mod.compare(doc, doc) == [], numbers=number_types(mod, doc))
        except Exception as err:
            obs.update(loads=f"error:{type(err).__name__}", self_equal=None, numbers=None)
        ok = obs["sha256_pinned"] and obs["loads"] == "ok" and obs["self_equal"]
        rows.append({"file": rel, "observed": obs, "checks": [check("self-comparison", ok, "PASS")]})
    largest = sorted(listed, key=lambda r: -listed[r]["bytes"])[:2]
    for rel in largest:
        code, observed, _, _ = run_cli(script, REPO / rel, REPO / rel, [])
        rows.append(
            {"file": rel, "cli": observed, "checks": [check("CLI self-comparison", observed == "equal", "PASS", code)]}
        )
    for m in EXP["derived_mutations"]:
        text = (REPO / m["file"]).read_text(encoding="utf-8")
        op = m["mutation"]
        if op["op"] == "set":
            doc = json.loads(text, parse_float=no_float)  # a plain round trip is exact only without floats
            node = doc
            for p in op["path"][:-1]:
                node = node[p]
            node[op["path"][-1]] = op["value"]
            mutated = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
        else:
            assert op["old"] in text, op
            mutated = text.replace(op["old"], op["new"], 1)
        path = Path(tmp) / f"{m['id']}.json"
        path.write_text(mutated, encoding="utf-8", newline="\n")
        code, observed, lines, _ = run_cli(script, REPO / m["file"], path, [(str(Path(tmp)), "<generated>")])
        diffs = [ln for ln in lines if ln.startswith("DIFFERS")]
        checks = [check(f"{label} outcome", observed == m[label], "PASS", observed)]
        if label == "baseline":
            checks.append(
                check("requirement", observed == m["repaired"], "PASS" if m["baseline"] == m["repaired"] else "FAIL")
            )
        rows.append({"id": m["id"], "file": m["file"], "observed": observed, "differs": diffs, "checks": checks})
    return rows


def interpreter_observations(mod):
    "Executed evidence about this interpreter; predictions are stated for v3.12.3 and v3.12.14 only."
    version = sys.version_info[:3]
    hooks = getattr(mod, "PARSE_HOOKS", {})
    results = {}
    for name, kw in (("default hooks", {}), ("module hooks", hooks)):
        dec = json.JSONDecoder(**kw)
        dec.scan_once = json.scanner.py_make_scanner(dec)
        results[name] = outcome(lambda dec=dec: json.dumps(dec.decode("[١]")))
    o1_pred = None
    if version == (3, 12, 3):
        o1_pred = {"default hooks": "[1]", "module hooks": "error:InvalidJSONError" if hooks else "[1]"}
    elif version == (3, 12, 14):
        o1_pred = {"default hooks": "error:JSONDecodeError", "module hooks": "error:JSONDecodeError"}
    try:
        o2 = {"adjusted": Decimal("1e999999999999999999").adjusted(), "context_Emax": decimal.getcontext().Emax}
    except Exception as err:
        o2 = f"error:{type(err).__name__}"
    o3 = {"default context": outcome(lambda: str(Decimal("1e9999999999999999999")))}
    with decimal.localcontext() as ctx:
        ctx.traps[decimal.InvalidOperation] = False
        o3["InvalidOperation not trapped"] = outcome(lambda: str(Decimal("1e9999999999999999999")))
    try:
        json.loads("[" * 100_000 + "]" * 100_000)
        o4 = "no error"
    except RecursionError as err:
        o4 = f"RecursionError: {err}"
    obs = {
        "python": sys.version.replace("\n", " "),
        "O1": {"observed": results, "predicted": o1_pred},
        "O2": {"observed": o2, "predicted": {"adjusted": 999999999999999999, "context_Emax": 999999}},
        "O3": {
            "observed": o3,
            "predicted": {"default context": "error:InvalidOperation", "InvalidOperation not trapped": "NaN"},
        },
        "O4": {"observed": o4, "predicted": "RecursionError"},
    }
    checks = [
        check(
            "O1", o1_pred is None or results == o1_pred, "PASS", "no prediction for this version" if o1_pred is None else None
        ),
        check("O2", o2 == obs["O2"]["predicted"], "PASS"),
        check("O3", o3 == obs["O3"]["predicted"], "PASS"),
        check("O4", o4.startswith("RecursionError"), "PASS"),
    ]
    return {**obs, "checks": checks}


def main():
    label, out_dir = sys.argv[1], Path(sys.argv[2])
    problems = verify_inputs()
    if problems:
        print("input identity differs:", problems)
        return 1
    mod = importlib.import_module(MODULES[label])
    script = ROOT / "scripts" / f"{MODULES[label]}.py"
    with tempfile.TemporaryDirectory(prefix="json-numeric-cases-") as tmp:
        cli = cli_rows(label, script, tmp)
        retained = retained_rows(mod, script, label, tmp)
    doc = {
        "environment": {
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "decimal": decimal.__version__,
            "libmpdec": decimal.__libmpdec_version__,
            "int_max_str_digits": INT_DIGITS_AT_START,
        },
        "comparator": {"label": label, "file": script.name, "sha256": sha256(script.read_bytes())},
        "summary": {},
        "cli_cases": cli,
        "api_cases": api_rows(mod, label),
        "retained": retained,
    }
    checks = [c for part in ("cli_cases", "api_cases", "retained") for r in doc[part] for c in r["checks"]]
    findings = [c for c in checks if c["result"] != c["predicted"]]
    doc["summary"] = {
        "checks": len(checks),
        "pass": sum(c["result"] == "PASS" for c in checks),
        "fail": sum(c["result"] == "FAIL" for c in checks),
        "fail, predicted (kept)": sum(c["result"] == "FAIL" == c["predicted"] for c in checks),
        "findings (result differs from prediction)": len(findings),
        "cli outcomes": {k: sum(r["observed"] == k for r in cli) for k in sorted({r["observed"] for r in cli})},
    }
    interp = interpreter_observations(mod)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cases.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "interpreter_observations.json").write_text(
        json.dumps(interp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(doc["environment"], indent=2))
    for r in cli:
        failed = [c["check"] for c in r["checks"] if c["result"] == "FAIL"]
        print(f"{r['id']} {r['observed']:9} exit {r['exit']} {'FAILED ' + ', '.join(failed) if failed else ''}")
        for ln in r["stdout"]:
            if ln.startswith(("DIFFERS", "INVALID")) or (ln.startswith("exempt") and r["id"].startswith("X05")):
                print(f"      {ln[:220]}")
        if r["stderr_last_line"]:
            print(f"      stderr: {r['stderr_last_line'][:220]}")
    for r in doc["api_cases"]:
        print(f"{r['id']} {json.dumps(r['observed'])[:200]} {[c['result'] for c in r['checks']]}")
    for r in retained:
        print(
            f"{r.get('id', 'self')} {r.get('file')} {json.dumps(r.get('observed', r.get('cli')))[:160]} {[c['result'] for c in r['checks']]}"
        )
    print("interpreter:", json.dumps({k: v["observed"] for k, v in interp.items() if k.startswith("O")})[:600])
    print(json.dumps(doc["summary"], indent=2))
    for c in findings + [c for c in interp["checks"] if c["result"] != c["predicted"]]:
        print("FINDING", c["check"], json.dumps(c["detail"])[:300])
    interp_findings = sum(c["result"] != c["predicted"] for c in interp["checks"])
    print(f"interpreter observations: {len(interp['checks'])} checks, findings {interp_findings}")
    return 1 if findings or interp_findings else 0


if __name__ == "__main__":
    sys.exit(main())

"""Run the unchanged predecessor corroborator on the budget witness W1 (before any successor code existed).

Usage: python witness_predecessor.py OUTPUT_JSON     (the retained wheels on PYTHONPATH, e.g. through zipimport)
Loads research/public-sphinx-parser-corroboration-20261018-01/scripts/corroborate.py from its pinned
bytes, calls its report() on fixtures/w1_long_clean.html and evaluates the predecessor replay's
historical R9 expression, copied verbatim from its scripts/replay.py lines 95-98. Writes the
predecessor report and the R9 result. Exit 0 whatever the outcome; the outcome is the evidence.
"""

import hashlib
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
EXP = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
PREDECESSOR = "research/public-sphinx-parser-corroboration-20261018-01/scripts/corroborate.py"


def load_pinned(rel, name):
    data = (REPO / rel).read_bytes()
    if hashlib.sha256(data).hexdigest() != EXP["pins"]["code_and_wheels"][rel]:
        raise RuntimeError(f"{rel} differs from its pin")
    module = types.ModuleType(name)
    module.__file__ = str(REPO / rel)
    sys.modules[name] = module
    exec(compile(data, module.__file__, "exec"), module.__dict__)  # the bytes just verified, no bytecode written
    return module


def main():
    co = load_pinned(PREDECESSOR, "corroborate")
    w = EXP["witness"]
    data = (REPO / w["file"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != w["sha256"]:
        raise RuntimeError("witness fixture differs from its pin")
    rep = co.report(data, w["anchor"], w["file"])
    statuses = sorted(set(rep["existing_helper"]["status"].values()))
    historical_r9 = all(s == "OK_STRUCTURAL_UNIT" for s in statuses) or rep["triage"]["disposition"] == "REVIEW"
    out = {"predecessor_report": rep, "historical_R9": historical_r9}
    Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[1]).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    t = {s: rep["trees"][s] for s in ("lxml", "html5lib")}
    print("environment:", json.dumps(rep["environment"]))
    print("modules:", {m: Path(sys.modules[m].__file__).parts[-3:] for m in ("html5lib", "six", "webencodings")})
    print(
        "lxml diagnostics:", rep["parsers"]["lxml"]["diagnostics"], "| html5lib errors:", rep["parsers"]["html5lib"]["errors"]
    )
    print("matches:", [t[s]["match_count"] for s in t], "rule reasons:", [t[s]["rule_reasons"] for s in t])
    print("membership:", [[t[s]["unit"]["membership"]["signatures"], t[s]["unit"]["membership"]["descriptions"]] for s in t])
    print("unit text bytes / sha256:", [(t[s]["unit"]["text_utf8_bytes"], t[s]["unit"]["text_sha256"]) for s in t])
    print("helper reasons:", rep["existing_helper"]["reasons"], "| helper status:", rep["existing_helper"]["status"])
    print("predecessor disposition:", rep["triage"]["disposition"], "| findings:", rep["comparison"]["findings"])
    print("historical R9 (a helper REVIEW is never upgraded):", historical_r9)
    return 0


if __name__ == "__main__":
    sys.exit(main())

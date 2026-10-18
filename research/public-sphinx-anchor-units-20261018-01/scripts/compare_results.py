"""Compare two results.json files of run_experiment.py, ignoring only the platform fields.

Usage: python compare_results.py COMMITTED_RESULTS_JSON REPLAY_RESULTS_JSON
Prints the environments side by side, then every case whose reasons, statuses, candidate
counts, payload hashes/sizes, raw byte span, parser diagnostics or check results differ.
Exit code 0 when nothing but the environment differs, 1 otherwise (a difference is a finding).
"""

import json
import sys
from pathlib import Path

FIELDS = ("reasons", "status", "matches", "near_matches")
CANDIDATE_FIELDS = (
    "signatures",
    "descriptions",
    "signature_ids",
    "first_line",
    "last_line",
    "dom_sha256",
    "dom_bytes",
    "text_sha256",
    "text_bytes",
    "raw_byte_span",
)


def digest(result):
    cand = result["candidate"] or {}
    return {
        **{k: result[k] for k in FIELDS},
        "candidate": {k: cand.get(k) for k in CANDIDATE_FIELDS} if cand else None,
        "contexts": {k: (v["context_bytes"], v["fits"], v["context_sha256"]) for k, v in result["contexts"].items()},
        "diagnostics": [(d["line"], d["type"]) for d in result["parser"]["diagnostics"]],
        "checks": [(c["check"], c["result"]) for c in result["checks"]],
    }


def main():
    a, b = (json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:3])
    print("committed:", json.dumps(a["environment"]))
    print("replay:   ", json.dumps(b["environment"]))
    differences = 0
    for ra, rb in zip(a["results"], b["results"], strict=True):
        da, db = digest(ra), digest(rb)
        if da != db:
            differences += 1
            changed = [k for k in da if da[k] != db[k]]
            print(f"DIFFERS {ra['case']}: {changed}")
            for k in changed:
                print(f"  committed {k}: {da[k]}")
                print(f"  replay    {k}: {db[k]}")
    print(f"cases compared: {len(a['results'])}, differing: {differences}")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())

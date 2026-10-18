"""Compare literal whole-passage selection with SQLite FTS5/BM25 for a 2048-byte context.

Python 3.12 standard library only; offline. Methods, assembly and outcome levels are the
pre-registered ones in fixtures/oracle.json. FTS5 availability is detected per tokenizer: an
unavailable method is reported as NOT_RUN, never replaced by another algorithm.

Usage: python evidence_bench.py OUTPUT_DIR
Writes OUTPUT_DIR/environment.json, results.json (every result, with its assembled context and
the exact byte offsets and sha256 of each passage) and summary.md. Exit code 1 if any result's
decision differs from the oracle's expected decision (those are findings, all recorded).
"""

import json
import platform
import sqlite3
import sys
from pathlib import Path

from spans import BUDGET_BYTES, ROOT, block, block_bytes, context_bytes, load_passages, sha256

TOKENIZERS = {"fts5_unicode61": "unicode61", "fts5_unicode61_underscore": "unicode61 tokenchars '_'"}
METHODS = ("literal", *TOKENIZERS)
ASSEMBLIES = ("plain", "oracle_dependencies")
CORRECT = {
    "SUFFICIENT_PER_ORACLE": {"ORACLE_COMPLETE"},
    "ABSTAIN_BUDGET": {"ABSTAIN_BUDGET"},
    "REVIEW_EXTERNAL": {"HITS_NOT_SUFFICIENT_REVIEW"},
    "ABSTAIN_NO_EVIDENCE": {"ABSTAIN_NO_HITS"},
}


def sql_string(value):
    return "'" + value.replace("'", "''") + "'"


def fts_query(terms):
    "Every term as an FTS5 string (a phrase), implicitly ANDed: no operator or syntax leaks in."
    return " ".join('"' + term.replace('"', '""') + '"' for term in terms)


def fts5_status():
    con = sqlite3.connect(":memory:")
    options = [row[0] for row in con.execute("PRAGMA compile_options")]
    status = {
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "sqlite_library_version": sqlite3.sqlite_version,
        "compile_option_ENABLE_FTS5": "ENABLE_FTS5" in options,
        "tokenizers": {},
    }
    for i, (method, tokenizer) in enumerate(TOKENIZERS.items()):
        status["tokenizers"][method] = {"tokenize": tokenizer, **probe(con, f"probe{i}", tokenizer)}
    con.close()
    return status


def probe(con, table, tokenizer):
    try:
        con.execute(f"CREATE VIRTUAL TABLE {table} USING fts5(body, tokenize={sql_string(tokenizer)})")
    except sqlite3.OperationalError as err:
        return {"available": False, "error": str(err)}
    return {"available": True}


class Index:
    "One FTS5 table per (fixture, tokenizer); rowid = position of the passage in its fixture."

    def __init__(self, by_fixture, status):
        self.con = sqlite3.connect(":memory:")
        self.by_fixture = by_fixture
        self.available = {m for m, t in status["tokenizers"].items() if t["available"]}
        for fixture, passages in by_fixture.items():
            for method in self.available:
                table = f"{fixture}_{method}"
                self.con.execute(f"CREATE VIRTUAL TABLE {table} USING fts5(body, tokenize={sql_string(TOKENIZERS[method])})")
                self.con.executemany(
                    f"INSERT INTO {table}(rowid, body) VALUES (?, ?)", [(n, p["text"]) for n, p in enumerate(passages, 1)]
                )

    def search(self, method, fixture, terms):
        table = f"{fixture}_{method}"
        rows = self.con.execute(
            f"SELECT rowid, bm25({table}) FROM {table} WHERE {table} MATCH ? ORDER BY bm25({table}), rowid",
            (fts_query(terms),),
        )
        return [(self.by_fixture[fixture][rowid - 1], score) for rowid, score in rows]


def literal_search(passages, terms):
    return [(p, None) for p in passages if all(term in p["text"] for term in terms)]


def fill(ranked, start=()):
    "Greedy whole-passage assembly: dedupe by sha256, skip what does not fit, never truncate."
    included, suppressed, omitted = list(start), [], []
    seen = {p["sha256"] for p in included}
    used = context_bytes(included)
    for p in ranked:
        if p in included:
            continue
        if p["sha256"] in seen:
            suppressed.append(p)
            continue
        cost = block_bytes(len(included) + 1, p)
        if used + cost > BUDGET_BYTES:
            omitted.append(p)
            continue
        included.append(p)
        seen.add(p["sha256"])
        used += cost
    return included, suppressed, omitted


def assemble(assembly, ranked, case, passages):
    if assembly == "plain":
        return (*fill(ranked), None)
    ranked_ids = {p["id"] for p in ranked}
    for req in case["required_sets"]:
        if ranked_ids & set(req["passages"]):
            required = sorted((passages[pid] for pid in req["passages"]), key=lambda p: p["byte_start"])
            if context_bytes(required) > BUDGET_BYTES:
                return [], [], [], {"set": req["passages"], "fits": False, "bytes": context_bytes(required)}
            return (*fill(ranked, required), {"set": req["passages"], "fits": True, "bytes": context_bytes(required)})
    return (*fill(ranked), {"set": None, "fits": None, "bytes": None})


def span(p):
    return {k: p[k] for k in ("id", "fixture", "byte_start", "byte_end", "bytes", "chars", "sha256")}


def evaluate(case, method, assembly, hits, assembled, ran):
    included, suppressed, omitted, dep = assembled
    ranked = [p for p, _ in hits]
    ranked_ids = [p["id"] for p in ranked]
    included_ids = {p["id"] for p in included}
    sets = [set(s["passages"]) for s in case["required_sets"]]
    text = "".join(block(n, p) for n, p in enumerate(included, 1))
    oracle_complete = any(s <= included_ids for s in sets)
    if not ran:
        decision = "NOT_RUN"
    elif dep is not None and dep["fits"] is False:
        decision = "ABSTAIN_BUDGET"
    elif not case["answerable"]:
        decision = "HITS_NOT_SUFFICIENT_REVIEW" if ranked else "ABSTAIN_NO_HITS"
    elif oracle_complete:
        decision = "ORACLE_COMPLETE"
    else:
        decision = "ORACLE_INCOMPLETE_REVIEW" if ranked else "ABSTAIN_NO_HITS"
    # a worker that takes any non-empty budget-fitting context as sufficient evidence is wrong
    # whenever the case is unanswerable from the fixture or the context is not oracle-complete
    naive_sufficient = bool(included)
    naive_wrong = naive_sufficient and not (case["answerable"] and oracle_complete)
    return {
        "case": case["id"],
        "method": method,
        "assembly": assembly,
        "query_terms": case["query_terms"],
        "query_fts5": fts_query(case["query_terms"]) if method != "literal" else None,
        "ran": ran,
        "retrieved": {
            "any": bool(ranked),
            "ranked_passages": [{"id": p["id"], "rank": n, "bm25": score} for n, (p, score) in enumerate(hits, 1)],
            "required_set_fully_retrieved": any(s <= set(ranked_ids) for s in sets),
            "required_passages_retrieved": sorted({pid for s in sets for pid in s} & set(ranked_ids)),
        },
        "budget_fitting": {
            "budget_bytes": BUDGET_BYTES,
            "context_bytes": len(text.encode("utf-8")),
            "fits": len(text.encode("utf-8")) <= BUDGET_BYTES,
            "omitted_for_budget": [span(p) for p in omitted],
            "suppressed_duplicates": [span(p) for p in suppressed],
        },
        "oracle_dependencies": dep,
        "oracle_complete": oracle_complete,
        "semantically_reviewed": False,
        "decision": decision,
        "expected_decision": case["expected_decision"],
        "agrees_with_oracle": decision in CORRECT[case["expected_decision"]],
        "naive_hit_means_sufficient": naive_sufficient,
        "naive_false_sufficiency": naive_wrong,
        "selected_passages": [span(p) for p in included],
        "context_sha256": sha256(text.encode("utf-8")),
        "context": text,
    }


def run(passages, oracle, status):
    by_fixture = {}
    for p in sorted(passages.values(), key=lambda p: (p["fixture_key"], p["byte_start"])):
        by_fixture.setdefault(p["fixture_key"], []).append(p)
    index = Index(by_fixture, status)
    results = []
    for case in oracle["cases"]:
        for method in METHODS:
            ran = method == "literal" or method in index.available
            if method == "literal":
                hits = literal_search(by_fixture[case["fixture"]], case["query_terms"])
            elif ran:
                hits = index.search(method, case["fixture"], case["query_terms"])
            else:
                hits = []
            ranked = [p for p, _ in hits]
            for assembly in ASSEMBLIES:
                assembled = assemble(assembly, ranked, case, passages) if ran else ([], [], [], None)
                results.append(evaluate(case, method, assembly, hits, assembled, ran))
    return results


def verify(results, passages, root=ROOT):
    "Every selected passage is a whole fixture slice with its hash; every context fits the budget."
    files = {}
    for r in results:
        assert r["budget_fitting"]["context_bytes"] <= BUDGET_BYTES, r["case"]
        assert sha256(r["context"].encode("utf-8")) == r["context_sha256"]
        for n, sp in enumerate(r["selected_passages"], 1):
            data = files.setdefault(sp["fixture"], (root / sp["fixture"]).read_bytes())
            raw = data[sp["byte_start"] : sp["byte_end"]]
            assert sha256(raw) == sp["sha256"] == passages[sp["id"]]["sha256"], sp
            assert block(n, passages[sp["id"]]) in r["context"]


def summary(results, status):
    lines = [
        "# Results summary (generated by scripts/evidence_bench.py)",
        "",
        f"SQLite {status['sqlite_library_version']}, ENABLE_FTS5={status['compile_option_ENABLE_FTS5']}; "
        + ", ".join(f"{m}: {'available' if t['available'] else 'NOT AVAILABLE'}" for m, t in status["tokenizers"].items()),
        "",
        (
            "Outcome columns: hits = passages retrieved; req = required passages retrieved (* = a whole required set);"
            " ctx = context bytes (labels and separators included) / passages; complete = oracle-complete;"
            " naive = a 'hit means sufficient' worker would be wrong. Nothing is semantically reviewed."
        ),
        "",
        "| case | expected | method | assembly | hits | req | ctx | complete | decision | agrees | naive wrong |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        req = ",".join(r["retrieved"]["required_passages_retrieved"]) or "-"
        if r["retrieved"]["required_set_fully_retrieved"]:
            req += "*"
        lines.append(
            f"| {r['case']} | {r['expected_decision']} | {r['method']} | {r['assembly']} | {len(r['retrieved']['ranked_passages'])}"
            f" | {req} | {r['budget_fitting']['context_bytes']}/{len(r['selected_passages'])} | {'yes' if r['oracle_complete'] else 'no'}"
            f" | {r['decision']} | {'yes' if r['agrees_with_oracle'] else '**no**'} | {'**yes**' if r['naive_false_sufficiency'] else 'no'} |"
        )
    lines += [
        "",
        "| method | assembly | agrees with oracle | oracle-complete | naive false sufficiency |",
        "|---|---|---|---|---|",
    ]
    for method in METHODS:
        for assembly in ASSEMBLIES:
            rs = [r for r in results if r["method"] == method and r["assembly"] == assembly]
            lines.append(
                f"| {method} | {assembly} | {sum(r['agrees_with_oracle'] for r in rs)}/{len(rs)}"
                f" | {sum(r['oracle_complete'] for r in rs)}/{len(rs)} | {sum(r['naive_false_sufficiency'] for r in rs)}/{len(rs)} |"
            )
    return "\n".join(lines) + "\n"


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    passages = load_passages()
    oracle = json.loads((ROOT / "fixtures" / "oracle.json").read_text(encoding="utf-8"))
    status = fts5_status()
    results = run(passages, oracle, status)
    verify(results, passages)
    status["oracle_sha256"] = sha256((ROOT / "fixtures" / "oracle.json").read_bytes())
    (out / "environment.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (out / "summary.md").write_text(summary(results, status), encoding="utf-8", newline="\n")
    disagree = [r for r in results if not r["agrees_with_oracle"]]
    print(json.dumps({k: v for k, v in status.items() if k != "tokenizers"}, indent=2))
    for m, t in status["tokenizers"].items():
        print(f"{m}: tokenize={t['tokenize']!r} available={t['available']}")
    print(f"results: {len(results)}, disagreeing with the oracle: {len(disagree)}")
    for r in disagree:
        print(f"  {r['case']:28} {r['method']:26} {r['assembly']:19} {r['decision']:27} expected {r['expected_decision']}")
    return 1 if disagree else 0


if __name__ == "__main__":
    sys.exit(main())

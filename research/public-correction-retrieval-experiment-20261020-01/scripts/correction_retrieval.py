"""Find candidate later-change passages for a public agreement: content words, literal identifier, SQLite FTS5.

Usage: python correction_retrieval.py OUTPUT_DIR [--against COMMITTED_RESULT_JSON]
Standard library only, Python 3.9+, offline. The steps:

1. Read the declared corpus (corpus/corpus.json and the record files, every sha256 checked) and the
   queries (fixtures/queries.json).
2. Run six candidate-discovery strategies per query. Two helpers come from
   research/public-evidence-spans-20261018-01/scripts/evidence_bench.py, executed from their pinned
   bytes: literal_search, reused unchanged, and fts_query, the FTS5 quoting.
3. Write OUTPUT_DIR/reader.md, which keeps the original passages, every candidate passage verbatim
   with a stable locator, and explicit uncertainty.
4. Write OUTPUT_DIR/result.json, with `environment` (interpreter, platform, SQLite build) apart from
   `result` (everything else, platform-independent).
5. Only then grade against fixtures/expectations.json (pre-registered). Discovery never reads
   that file.

Nothing decides whether a candidate changes the target: determination is always NOT_MADE.

Exit codes:
* 0: every graded check passes, and with --against the `result` section equals the committed one;
* 1: a check fails or a difference is found;
* 2: a pinned input differs.
"""

import hashlib
import json
import platform
import re
import sqlite3
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
PREFIX = ROOT.relative_to(REPO).as_posix()
REQUEST_ID = "public-correction-retrieval-experiment-20261020-01"
CORPUS_SHA256 = "43e9ad338a465ab4a8aa49a37db069772048c603f3172caa38fc8c4221f58cb0"
HELPERS = (
    ("spans", "research/public-evidence-spans-20261018-01/scripts/spans.py", "6bc15cee4920d91cd5c3afe2b4a3f4fa1a0591fbfdd75915c18bf710b8bb19d8"),
    ("evidence_bench", "research/public-evidence-spans-20261018-01/scripts/evidence_bench.py", "b74774f13bc2d6d534ade87e7ab537c80c5c9668df31a33706006f7d9bf3b9d4"),
)  # fmt: skip
STOPWORDS = frozenset("a an and do does for in is it of still the to".split())
TOKENIZERS = {"unicode61": "unicode61", "unicode61_slash": "unicode61 tokenchars '/'"}
STRATEGIES = (
    "content_words_python",
    "literal_substring_reused",
    "literal_bounded",
    "fts5_content_unicode61",
    "fts5_identifier_unicode61",
    "fts5_identifier_slash",
)
FTS = {
    "fts5_content_unicode61": "unicode61",
    "fts5_identifier_unicode61": "unicode61",
    "fts5_identifier_slash": "unicode61_slash",
}
IDENTIFIER = re.compile(r"(?<![0-9A-Za-z])[0-9]{1,4}/[0-9]{4}(?![0-9A-Za-z])")
WORD = re.compile(r"[a-z]+")
FORBIDDEN_KEYS = re.compile(r"revo|valid|current|in_force|accept|authori|correct|supersed")
SCOPE_LIMIT = (
    "A declared scope does not prove completeness, the absence of changes outside it, or current normative "
    "validity; no match inside it is not evidence that the target is current."
)
NOT_MADE = (
    "Determination: NOT MADE. Whether any candidate changes, confirms or is unrelated to the target is not "
    "decided here; a matching identifier, hash, issuer or later declared date asserts nothing."
)


class PinError(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_helpers():
    "Execute the pinned earlier helper bytes as modules (spans first: evidence_bench imports it)."
    modules = {}
    for name, rel, pin in HELPERS:
        data = (REPO / rel).read_bytes()
        if sha256(data) != pin:
            raise PinError(f"{rel} differs from its pinned sha256")
        module = types.ModuleType(name)
        module.__file__ = str(REPO / rel)
        sys.modules[name] = module
        exec(compile(data, module.__file__, "exec"), module.__dict__)  # the bytes just verified, no bytecode written
        modules[name] = module
    return modules["evidence_bench"]


def load_corpus():
    "Records and passages of the declared corpus, each read back from its bytes and checked against the manifest."
    raw = (ROOT / "corpus" / "corpus.json").read_bytes()
    if sha256(raw) != CORPUS_SHA256:
        raise PinError("corpus/corpus.json differs from its pinned sha256")
    manifest = json.loads(raw.decode("utf-8"))
    records, passages = {}, []
    for rec in manifest["records"]:
        data = (ROOT / rec["file"]).read_bytes()
        if (len(data), sha256(data)) != (rec["bytes"], rec["sha256"]):
            raise PinError(f"{rec['file']} differs from the manifest")
        records[rec["record_id"]] = rec
        for p in rec["passages"]:
            chunk = data[p["byte_start"] : p["byte_end"]]
            if sha256(chunk) != p["sha256"]:
                raise PinError(f"{rec['file']} passage {p['n']} differs from the manifest")
            passages.append(
                {
                    "locator": f"{rec['record_id']}#p{p['n']}",
                    "file": rec["file"],
                    "byte_start": p["byte_start"],
                    "byte_end": p["byte_end"],
                    "sha256": p["sha256"],
                    "record_id": rec["record_id"],
                    "issuer": rec["issuer"],
                    "declared_date": rec["declared_date"],
                    "text": chunk.decode("utf-8"),
                }
            )
    return manifest, records, passages


def content_words(question):
    words = []
    for w in WORD.findall(question.casefold()):
        if w not in STOPWORDS and w not in words:
            words.append(w)
    return words


class Fts:
    "One FTS5 table per tokenizer over every passage; rowid = position in the corpus order."

    def __init__(self, eb, passages):
        self.con = sqlite3.connect(":memory:")
        self.probe = {}
        for i, (key, tokenize) in enumerate(TOKENIZERS.items()):
            self.probe[key] = eb.probe(self.con, f"probe{i}", tokenize)
            if self.probe[key]["available"]:
                self.con.execute(f"CREATE VIRTUAL TABLE t_{key} USING fts5(body, tokenize={eb.sql_string(tokenize)})")
                self.con.executemany(
                    f"INSERT INTO t_{key}(rowid, body) VALUES (?, ?)", [(n, p["text"]) for n, p in enumerate(passages, 1)]
                )

    def search(self, key, query):
        sql = f"SELECT rowid FROM t_{key} WHERE t_{key} MATCH ? ORDER BY bm25(t_{key}), rowid"
        return [rowid for (rowid,) in self.con.execute(sql, (query,))]


def run_strategy(name, eb, fts, passages, identifier, words):
    "Ordered candidate locators of one strategy over all passages, or None when its tokenizer is unavailable."
    if name == "content_words_python":
        wanted = set(words)
        scored = [(-len(wanted & set(WORD.findall(p["text"].casefold()))), p["locator"]) for p in passages]
        return [loc for score, loc in sorted(scored) if score < 0]
    if name == "literal_substring_reused":
        return [p["locator"] for p, _ in eb.literal_search(passages, [identifier])]
    if name == "literal_bounded":
        pattern = re.compile(r"(?<![0-9A-Za-z])" + re.escape(identifier) + r"(?![0-9A-Za-z])")
        return [p["locator"] for p in passages if pattern.search(p["text"])]
    key = FTS[name]
    if not fts.probe[key]["available"]:
        return None
    query = " OR ".join(eb.fts_query([w]) for w in words) if name == "fts5_content_unicode61" else eb.fts_query([identifier])
    return [passages[rowid - 1]["locator"] for rowid in fts.search(key, query)] if query else []


def relation(date, target_date):
    if target_date is None:
        return "no_target_record"
    return "earlier" if date < target_date else "same" if date == target_date else "later"


def detail(p, target_date, records):
    "One passage as shown to a reader: identity, declared metadata, identifier mentions resolved by string only."
    mentions = []
    for ident in sorted(set(IDENTIFIER.findall(p["text"])), key=p["text"].index):
        issued = [
            {"record_id": r["record_id"], "issuer": r["issuer"]} for r in records.values() if ident in r["issues_identifiers"]
        ]
        mentions.append(
            {
                "identifier": ident,
                "issued_by_in_declared_corpus": issued,
                "resolution": "ISSUED_IN_DECLARED_CORPUS" if issued else "UNRESOLVED_IN_DECLARED_CORPUS",
            }
        )
    return {
        "locator": p["locator"],
        "file": f"{PREFIX}/{p['file']}",
        "byte_start": p["byte_start"],
        "byte_end": p["byte_end"],
        "sha256": p["sha256"],
        "record_id": p["record_id"],
        "issuer": p["issuer"],
        "declared_date": p["declared_date"],
        "date_relation": relation(p["declared_date"], target_date),
        "identifier_mentions": mentions,
        "text": p["text"],
    }


def discover(eb, manifest, records, passages, queries):
    "Candidate discovery for every query. Reads only the corpus and the queries."
    fts = Fts(eb, passages)
    by_locator = {p["locator"]: p for p in passages}
    dates = sorted(r["declared_date"] for r in records.values())
    out = []
    for q in queries:
        ident, issuer, words = q["identifier"], q["issuer"], content_words(q["question"])
        targets = [r for r in records.values() if r["issuer"] == issuer and ident in r["issues_identifiers"]]
        target_ids = [r["record_id"] for r in targets]
        target_date = min(r["declared_date"] for r in targets) if targets else None
        others = [
            {"record_id": r["record_id"], "issuer": r["issuer"]}
            for r in records.values()
            if r["issuer"] != issuer and ident in r["issues_identifiers"]
        ]
        strategies, found_by = {}, {}
        for name in STRATEGIES:
            hits = run_strategy(name, eb, fts, passages, ident, words)
            if hits is None:
                strategies[name] = {
                    "status": "NOT_RUN",
                    "candidates": None,
                    "note": "tokenizer unavailable in this SQLite build; not substituted",
                }
                continue
            hits = [loc for loc in hits if by_locator[loc]["record_id"] not in target_ids]
            strategies[name] = {"status": "RUN", "candidates": hits}
            for loc in hits:
                found_by.setdefault(loc, []).append(name)
        ran = [n for n in STRATEGIES if strategies[n]["status"] == "RUN"]
        union = sorted(found_by, key=lambda loc: (by_locator[loc]["declared_date"], loc))
        candidates = []
        for loc in union:
            d = detail(by_locator[loc], target_date, records)
            d["found_by"] = found_by[loc]
            d["not_found_by"] = [n for n in ran if n not in found_by[loc]]
            candidates.append(d)
        returned = {by_locator[loc]["record_id"] for loc in union}
        silent = [
            {
                "record_id": r["record_id"],
                "issuer": r["issuer"],
                "declared_date": r["declared_date"],
                "date_relation": relation(r["declared_date"], target_date),
            }
            for r in records.values()
            if r["record_id"] not in returned and r["record_id"] not in target_ids
        ]
        unresolved = sorted(
            {
                m["identifier"]
                for c in candidates
                for m in c["identifier_mentions"]
                if m["resolution"] != "ISSUED_IN_DECLARED_CORPUS"
            }
        )
        uncertainty = [NOT_MADE, SCOPE_LIMIT]
        if not targets:
            uncertainty.append(f"No record in the declared corpus issues {ident} for {issuer}: the target is unresolved.")
        if others:
            names = ", ".join(f"{o['issuer']} ({o['record_id']})" for o in others)
            uncertainty.append(
                f"{ident} is also issued by {names}: a mention of {ident} does not say which body's act is meant."
            )
        if unresolved:
            uncertainty.append(
                "Mentioned in a candidate but issued by no record in the declared corpus: " + ", ".join(unresolved) + "."
            )
        if not union:
            uncertainty.append(
                "No strategy returned a candidate passage. This is not evidence that the target is current, unchanged or valid."
            )
        skipped = [n for n in STRATEGIES if strategies[n]["status"] != "RUN"]
        if skipped:
            uncertainty.append("Not run (tokenizer unavailable): " + ", ".join(skipped) + ".")
        out.append(
            {
                "id": q["id"],
                "identifier": ident,
                "issuer": issuer,
                "question": q["question"],
                "content_words": words,
                "target_records": target_ids,
                "same_identifier_other_issuers": others,
                "original": [detail(p, target_date, records) for p in passages if p["record_id"] in target_ids],
                "strategies": strategies,
                "candidates": candidates,
                "records_without_returned_passage": silent,
                "determination": "NOT_MADE",
                "uncertainty": uncertainty,
                "declared_scope": {
                    "corpus_id": manifest["corpus_id"],
                    "statement": manifest["declared_scope"],
                    "records": [r["record_id"] for r in records.values()],
                    "declared_dates": [dates[0], dates[-1]],
                    "manifest_sha256": CORPUS_SHA256,
                },
            }
        )
    return out, fts.probe


def quote(text):
    return "\n".join("> " + line for line in text.split("\n"))


def where(d):
    return f"`{d['locator']}` ({d['file']}, bytes {d['byte_start']}-{d['byte_end']}, sha256 {d['sha256'][:16]}...)"


def reader(found):
    "The downstream reader output: original, candidates verbatim, uncertainty. Deterministic Markdown."
    lines = [
        "# Candidate passages for later changes (generated by scripts/correction_retrieval.py)",
        "",
        "Candidate discovery only. Every passage below is quoted verbatim from the declared corpus at its locator.",
        "No relation, correction, acceptance, authority or current validity is asserted.",
    ]
    for q in found:
        lines += ["", f"## {q['id']}: {q['issuer']} {q['identifier']}", "", f"Question: {q['question']}", ""]
        lines += [f"Content words: {', '.join(q['content_words'])}", "", "Uncertainty:", ""] + [
            f"* {u}" for u in q["uncertainty"]
        ]
        s = q["declared_scope"]
        lines += [
            "",
            (
                f"Declared scope: {len(s['records'])} records ({', '.join(s['records'])}), declared dates "
                f"{s['declared_dates'][0]} to {s['declared_dates'][1]}, manifest sha256 {s['manifest_sha256'][:16]}..."
            ),
            "",
            "### Original",
            "",
        ]
        if not q["original"]:
            lines.append("No record in the declared corpus issues this identifier for this issuer.")
        for d in q["original"]:
            lines += [f"{where(d)}, {d['issuer']}, declared {d['declared_date']}", "", quote(d["text"]), ""]
        lines += ["### Candidates", ""]
        if not q["candidates"]:
            lines.append("None returned by any strategy that ran.")
        for d in q["candidates"]:
            mentions = "; ".join(
                f"{m['identifier']}: "
                + (
                    ", ".join(f"{i['issuer']} {i['record_id']}" for i in m["issued_by_in_declared_corpus"])
                    or "UNRESOLVED_IN_DECLARED_CORPUS"
                )
                for m in d["identifier_mentions"]
            )
            lines += [
                f"{where(d)}, {d['issuer']}, declared {d['declared_date']} ({d['date_relation']} than the target's declared date)"
                if d["date_relation"] in ("earlier", "later")
                else f"{where(d)}, {d['issuer']}, declared {d['declared_date']} ({d['date_relation']})",
                f"found by: {', '.join(d['found_by'])}; not found by: {', '.join(d['not_found_by']) or '-'}",
                f"identifier mentions: {mentions or 'none of the form n/yyyy'}",
                "",
                quote(d["text"]),
                "",
            ]
        lines += ["### Records with no returned passage", ""]
        silent = q["records_without_returned_passage"]
        lines.append(
            ", ".join(f"{r['record_id']} ({r['issuer']}, {r['declared_date']}, {r['date_relation']})" for r in silent)
            or "none"
        )
        lines += ["", "### Per strategy", "", "| strategy | status | candidates |", "|---|---|---|"]
        for name, st in q["strategies"].items():
            lines.append(f"| {name} | {st['status']} | {', '.join(st['candidates'] or []) or '-'} |")
    return "\n".join(lines) + "\n"


def environment(probe):
    con = sqlite3.connect(":memory:")
    options = [row[0] for row in con.execute("PRAGMA compile_options")]
    con.close()
    return {
        "python": sys.version.replace("\n", " "),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "sqlite_library_version": sqlite3.sqlite_version,
        "sqlite_compile_option_ENABLE_FTS5": "ENABLE_FTS5" in options,
        "fts5_tokenizer_probe": {TOKENIZERS[k]: v for k, v in probe.items()},
    }


def keys(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k
            yield from keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from keys(v, f"{path}[{i}]")


def grade(found, again, text, output):
    "Compare with the pre-registered expectations (read here, after discovery) and check the properties."
    exp = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
    checks = []

    def chk(name, observed, predicted):
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

    by_id = {q["id"]: q for q in found}
    for qid, per in exp["expected_candidates"].items():
        for name, want in per.items():
            st = by_id[qid]["strategies"][name]
            if st["status"] != "RUN":
                checks.append({"check": f"{qid} {name} candidates", "result": "NOT_RUN", "observed": None, "predicted": want})
            else:
                chk(f"{qid} {name} candidates", sorted(st["candidates"]), want)
    facts = exp["expected_reader_facts"]
    for qid in ("Q1", "Q2", "Q3"):
        q = by_id[qid]
        chk(f"{qid} target records", q["target_records"], facts[qid]["target_records"])
        chk(
            f"{qid} same identifier, other issuers",
            [o["record_id"] for o in q["same_identifier_other_issuers"]],
            facts[qid]["same_identifier_other_issuers"],
        )
        silent = q["records_without_returned_passage"]
        if "later_records_not_returned" in facts[qid]:
            chk(
                f"{qid} later records not returned",
                [r["record_id"] for r in silent if r["date_relation"] == "later"],
                facts[qid]["later_records_not_returned"],
            )
        if "records_not_returned" in facts[qid]:
            chk(f"{qid} records not returned", [r["record_id"] for r in silent], facts[qid]["records_not_returned"])
        if "unresolved_mentions" in facts[qid]:
            observed = sorted(
                {
                    m["identifier"]
                    for c in q["candidates"]
                    for m in c["identifier_mentions"]
                    if m["resolution"] != "ISSUED_IN_DECLARED_CORPUS"
                }
            )
            chk(f"{qid} unresolved mentions", observed, facts[qid]["unresolved_mentions"])
        if "candidates" in facts[qid]:
            chk(f"{qid} number of candidates", len(q["candidates"]), facts[qid]["candidates"])
    pred = exp["predicted_findings"]
    q1 = {n: st["candidates"] for n, st in by_id["Q1"]["strategies"].items() if st["status"] == "RUN"}
    chk(
        "finding: strategies missing the identifier-only change R07#p1",
        [n for n in q1 if "R07#p1" not in q1[n]],
        pred["misses_identifier_only_change_Q1_R07#p1"],
    )
    chk(
        "finding: strategies missing the change without identifier R12#p1",
        [n for n in q1 if "R12#p1" not in q1[n]],
        pred["misses_change_without_identifier_Q1_R12#p1"],
    )
    off_target = {
        "R06#p1",
        "R08#p1",
        "R09#p1",
        "R10#p1",
    }  # evaluation_annotations: other body, other form, other agreement, substring
    chk(
        "finding: irrelevant or ambiguous candidates per strategy (Q1)",
        {n: sorted(off_target & set(c)) for n, c in q1.items()},
        pred["irrelevant_or_ambiguous_candidates_Q1"],
    )
    identifier_strategies = [n for n in q1 if "identifier" in n or n.startswith("literal")]
    chk(
        "finding: non-changing mentions returned by every identifier strategy (Q1)",
        sorted(set.intersection(*(set(q1[n]) for n in identifier_strategies)) & {"R03#p1", "R05#p1"}),
        pred["non_changing_mentions_returned_by_every_identifier_strategy_Q1"],
    )
    changes = {"R04#p1", "R07#p1", "R12#p1"}
    chk(
        "finding: no single strategy returns R04, R07 and R12",
        not any(changes <= set(c) for c in q1.values()),
        pred["no_single_strategy_returns_all_of_R04_R07_R12"],
    )
    chk(
        "finding: the union returns R04, R07 and R12",
        changes <= {c["locator"] for c in by_id["Q1"]["candidates"]},
        pred["union_returns_R04_R07_R12"],
    )
    bad = []
    for q in found:
        for d in q["original"] + q["candidates"]:
            chunk = (REPO / d["file"]).read_bytes()[d["byte_start"] : d["byte_end"]]
            if sha256(chunk) != d["sha256"] or chunk.decode("utf-8") != d["text"]:
                bad.append(d["locator"])
    prop("P1 every shown passage equals the bytes at its locator", not bad, bad)
    forbidden = [p for p, k in keys(output) if FORBIDDEN_KEYS.search(k)]
    prop("P2 no assertion-like key in the result", not forbidden, forbidden)
    prop(
        "P3 determination NOT_MADE and the scope limitation in every query",
        all(q["determination"] == "NOT_MADE" and SCOPE_LIMIT in q["uncertainty"] for q in found)
        and text.count(SCOPE_LIMIT) == len(found),
        text.count(SCOPE_LIMIT),
    )
    prop("P4 discovery is deterministic within one process", again == found)
    not_run = [(q["id"], n) for q in found for n, st in q["strategies"].items() if st["status"] != "RUN"]
    prop(
        "P5 unavailable tokenizers are NOT_RUN, never substituted",
        all(by_id[i]["strategies"][n]["candidates"] is None for i, n in not_run),
        not_run,
    )
    totals = {k: sum(c["result"] == k for c in checks) for k in ("PASS", "FAIL", "NOT_RUN")}
    return checks, totals


def differences(a, b, path="$"):
    if type(a) is not type(b):
        return [f"{path}: type {type(a).__name__} != {type(b).__name__}"]
    if isinstance(a, dict):
        if list(a) != list(b):
            return [f"{path}: keys {list(a)} != {list(b)}"]
        return [d for k in a for d in differences(a[k], b[k], f"{path}.{k}")]
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in differences(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def write(path, text):
    with Path(path).open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (1, 3) or (len(argv) == 3 and argv[1] != "--against"):
        print("usage: correction_retrieval.py OUTPUT_DIR [--against COMMITTED_RESULT_JSON]")
        return 2
    try:
        eb = load_helpers()
        manifest, records, passages = load_corpus()
    except PinError as e:
        print(f"PIN MISMATCH: {e}")
        return 2
    queries = json.loads((ROOT / "fixtures" / "queries.json").read_text(encoding="utf-8"))["queries"]
    found, probe = discover(eb, manifest, records, passages, queries)
    again, _ = discover(eb, manifest, records, passages, queries)
    text = reader(found)
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    write(out / "reader.md", text)
    paths = [rel for _, rel, _ in HELPERS] + [
        f"{PREFIX}/{rel}" for rel in ("corpus/corpus.json", "fixtures/queries.json", "fixtures/expectations.json")
    ]
    paths += [f"{PREFIX}/{r['file']}" for r in records.values()] + [f"{PREFIX}/scripts/correction_retrieval.py"]
    inputs = [{"path": rel, "sha256": sha256((REPO / rel).read_bytes())} for rel in paths]
    result = {
        "schema": 1,
        "request_id": REQUEST_ID,
        "inputs": inputs,
        "queries": found,
        "reader_md_sha256": sha256(text.encode("utf-8")),
    }
    env = environment(probe)
    checks, totals = grade(found, again, text, {"environment": env, "result": result})
    result["grading"] = {"totals": totals, "checks": checks}
    write(out / "result.json", json.dumps({"environment": env, "result": result}, indent=2, ensure_ascii=False) + "\n")
    print("environment:", json.dumps(env))
    for q in found:
        print(
            f"{q['id']} {q['issuer']} {q['identifier']}: target={q['target_records']} candidates={len(q['candidates'])} determination={q['determination']}"
        )
        for name, st in q["strategies"].items():
            print(f"   {name:27} {st['status']:7} {st['candidates']}")
    for c in checks:
        if c["result"] != "PASS":
            print(
                f"   {c['result']} {c['check']}: observed {json.dumps(c.get('observed'))} predicted {json.dumps(c.get('predicted'))}"
            )
    print(json.dumps(totals))
    status = 1 if totals["FAIL"] else 0
    if len(argv) == 3:
        committed = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        diffs = differences(committed["result"], result)
        print(f"against {argv[2]}: {len(diffs)} difference(s) in the result section (environment not compared)")
        for d in diffs[:20]:
            print("  DIFFERS " + d)
        status = max(status, 1 if diffs else 0)
    return status


if __name__ == "__main__":
    sys.exit(main())

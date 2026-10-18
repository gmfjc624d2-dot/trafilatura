"""Focused tests and negative controls for the evidence-span benchmark (stdlib unittest).

Run from the research directory: python -m unittest discover -s scripts -v
"""
# ruff: noqa: PT009, PT027 -- stdlib unittest on purpose: no pytest dependency

import json
import re
import sqlite3
import unittest

import evidence_bench as bench
from spans import BUDGET_BYTES, ROOT, block, block_bytes, context_bytes, load_passages, sha256

PASSAGES = load_passages()
ORACLE = json.loads((ROOT / "fixtures" / "oracle.json").read_text(encoding="utf-8"))
STATUS = bench.fts5_status()
RESULTS = bench.run(PASSAGES, ORACLE, STATUS)
FTS5 = all(t["available"] for t in STATUS["tokenizers"].values())


def result(case, method, assembly="plain"):
    return next(r for r in RESULTS if r["case"] == case and r["method"] == method and r["assembly"] == assembly)


def fts_ids(tokenizer, texts, terms):
    con = sqlite3.connect(":memory:")
    con.execute(f"CREATE VIRTUAL TABLE t USING fts5(body, tokenize={bench.sql_string(tokenizer)})")
    con.executemany("INSERT INTO t(rowid, body) VALUES (?, ?)", list(enumerate(texts, 1)))
    return [row[0] for row in con.execute("SELECT rowid FROM t WHERE t MATCH ? ORDER BY rowid", (terms,))]


class Offsets(unittest.TestCase):
    def test_offsets_are_utf8_byte_offsets_into_the_plain_text_fixture(self):
        for p in PASSAGES.values():
            data = (ROOT / p["fixture"]).read_bytes()
            self.assertEqual(data[p["byte_start"] : p["byte_end"]].decode("utf-8"), p["text"])
            self.assertEqual(sha256(data[p["byte_start"] : p["byte_end"]]), p["sha256"])
            self.assertNotIn("\n", p["text"])
        multibyte = [p for p in PASSAGES.values() if p["bytes"] != p["chars"]]
        self.assertGreaterEqual(len(multibyte), 6)
        self.assertEqual(PASSAGES["S11"]["bytes"], 3 * PASSAGES["S11"]["chars"])

    def test_repeated_paragraphs_keep_their_own_offsets(self):
        s06, s07 = PASSAGES["S06"], PASSAGES["S07"]
        self.assertEqual(s06["sha256"], s07["sha256"])
        self.assertNotEqual((s06["byte_start"], s06["byte_end"]), (s07["byte_start"], s07["byte_end"]))


class Budget(unittest.TestCase):
    def test_labels_and_separators_are_counted(self):
        p = PASSAGES["D04"]
        text = block(1, p)
        self.assertRegex(text, r"^\[1\] docs \d+-\d+ sha256:[0-9a-f]{12}\n")
        self.assertTrue(text.endswith(p["text"] + "\n\n"))
        self.assertEqual(block_bytes(1, p), len(text.encode("utf-8")))
        self.assertGreater(block_bytes(1, p), p["bytes"])

    def test_every_context_fits_and_holds_whole_passages_only(self):
        bench.verify(RESULTS, PASSAGES)
        for r in RESULTS:
            ids = [sp["id"] for sp in r["selected_passages"]]
            rebuilt = "".join(block(n, PASSAGES[pid]) for n, pid in enumerate(ids, 1))
            self.assertEqual(rebuilt, r["context"])
            self.assertEqual(len(rebuilt.encode("utf-8")), r["budget_fitting"]["context_bytes"])
            self.assertLessEqual(r["budget_fitting"]["context_bytes"], BUDGET_BYTES)

    def test_character_budget_would_admit_an_oversized_passage(self):
        "negative control: S15 is under 2048 characters, so a character budget would take it"
        s15 = PASSAGES["S15"]
        self.assertLess(len(block(1, s15)), BUDGET_BYTES)
        self.assertGreater(block_bytes(1, s15), BUDGET_BYTES)
        for r in RESULTS:
            self.assertNotIn("S15", [sp["id"] for sp in r["selected_passages"]])

    def test_oracle_dependencies_never_assemble_a_partial_required_set(self):
        self.assertLessEqual(context_bytes([PASSAGES["S13"]]), BUDGET_BYTES)
        for method in bench.METHODS:
            r = result("S8-quota-readonly-budget", method, "oracle_dependencies")
            if r["retrieved"]["any"]:
                self.assertEqual(r["decision"], "ABSTAIN_BUDGET")
                self.assertEqual(r["selected_passages"], [])

    def test_duplicates_are_suppressed_with_their_offsets(self):
        r = result("S3-retries-repeated", "literal")
        self.assertEqual([sp["id"] for sp in r["selected_passages"]], ["S06"])
        self.assertEqual([sp["id"] for sp in r["budget_fitting"]["suppressed_duplicates"]], ["S07"])
        self.assertEqual(r["budget_fitting"]["suppressed_duplicates"][0]["byte_start"], PASSAGES["S07"]["byte_start"])


class Sufficiency(unittest.TestCase):
    def test_a_hit_is_not_sufficiency(self):
        "negative control: every method finds check_hostname, the meaning is in another document"
        for method in bench.METHODS:
            for assembly in bench.ASSEMBLIES:
                r = result("D5-check-hostname-meaning", method, assembly)
                if r["ran"]:
                    self.assertTrue(r["retrieved"]["any"])
                    self.assertFalse(r["oracle_complete"])
                    self.assertEqual(r["decision"], "HITS_NOT_SUFFICIENT_REVIEW")
                    self.assertTrue(r["naive_false_sufficiency"])

    def test_nothing_is_semantically_reviewed(self):
        self.assertFalse(any(r["semantically_reviewed"] for r in RESULTS))

    def test_absent_answer_gives_no_hits(self):
        for method in bench.METHODS:
            r = result("S11-socks5-absent", method)
            if r["ran"]:
                self.assertEqual(r["decision"], "ABSTAIN_NO_HITS")


@unittest.skipUnless(FTS5, "FTS5 not available in this SQLite build")
class Tokenizers(unittest.TestCase):
    def test_underscore_identifier_collides_with_two_words_by_default(self):
        texts = [PASSAGES["D10"]["text"], PASSAGES["D12"]["text"]]
        self.assertEqual(fts_ids("unicode61", texts, '"no_proxy"'), [1, 2])
        self.assertEqual(fts_ids("unicode61 tokenchars '_'", texts, '"no_proxy"'), [2])
        texts = [PASSAGES["S02"]["text"], PASSAGES["S03"]["text"]]
        self.assertEqual(fts_ids("unicode61", texts, '"check_hostname"'), [1, 2])
        self.assertEqual(fts_ids("unicode61 tokenchars '_'", texts, '"check_hostname"'), [1])

    def test_unquoted_query_syntax_leaks_operators(self):
        "negative control for the quoting in fts_query()"
        texts = [PASSAGES["S04"]["text"], PASSAGES["S05"]["text"]]
        self.assertEqual(fts_ids("unicode61", texts, bench.fts_query(["cache", "not", "shared"])), [2])
        self.assertEqual(fts_ids("unicode61", texts, "cache NOT shared"), [])  # NOT is an operator
        with self.assertRaises(sqlite3.OperationalError):
            fts_ids("unicode61", [PASSAGES["S14"]["text"]], "read-only")
        self.assertEqual(fts_ids("unicode61", [PASSAGES["S14"]["text"]], bench.fts_query(["read-only"])), [1])

    def test_query_is_quoted_per_term(self):
        self.assertEqual(bench.fts_query(['say "hi"', "no_proxy"]), '"say ""hi""" "no_proxy"')
        self.assertRegex(result("D2-proxyhandler-empty-dict", "fts5_unicode61")["query_fts5"], r'^"empty dictionary"$')


class Availability(unittest.TestCase):
    def test_missing_fts5_is_reported_not_substituted(self):
        status = json.loads(json.dumps(STATUS))
        for t in status["tokenizers"].values():
            t["available"] = False
        results = bench.run(PASSAGES, ORACLE, status)
        for r in results:
            if r["method"] == "literal":
                self.assertTrue(r["ran"])
            else:
                self.assertFalse(r["ran"])
                self.assertEqual(r["decision"], "NOT_RUN")
                self.assertEqual(r["selected_passages"], [])
                self.assertFalse(r["agrees_with_oracle"])

    def test_status_names_the_library_version(self):
        self.assertRegex(STATUS["sqlite_library_version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(set(STATUS["tokenizers"]), {"fts5_unicode61", "fts5_unicode61_underscore"})


class Literal(unittest.TestCase):
    def test_literal_is_case_sensitive_and_unnormalised(self):
        self.assertEqual(bench.literal_search([PASSAGES["S13"]], ["quota"]), [])
        self.assertEqual(len(bench.literal_search([PASSAGES["S13"]], ["Quota"])), 1)
        self.assertEqual(bench.literal_search([PASSAGES["S12"]], ["résumé"]), [])
        self.assertTrue(re.search("résumé", PASSAGES["S12"]["text"]))


if __name__ == "__main__":
    unittest.main()

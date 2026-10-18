"""Focused tests and negative controls for anchor_unit.py (stdlib unittest, offline).

Run from the research directory: python -m unittest discover -s scripts -v
These test structure and evidence handling only; they say nothing about factual sufficiency.
"""

import json
import re
import unittest
from pathlib import Path

import anchor_unit as au
import lxml.html

ROOT = Path(__file__).resolve().parent.parent
EXP = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
CASES = {c["id"]: c for c in EXP["cases"]}


def run(case_id, anchor=None):
    case = CASES[case_id]
    data = (ROOT / case["file"]).read_bytes()
    return data, au.select_unit(data, anchor if anchor is not None else case["anchor"], path=case["file"], origin="test")


class Contract(unittest.TestCase):
    def test_context_template_is_the_preregistered_one(self):
        self.assertEqual(au.CONTEXT_TEMPLATE, EXP["context_template"])
        self.assertEqual(au.BUDGET_BYTES, EXP["budget_bytes"])

    def test_selection_is_deterministic(self):
        self.assertEqual(run("C12")[1], run("C12")[1])

    def test_nothing_is_semantically_reviewed(self):
        self.assertFalse(any(run(cid)[1]["semantically_reviewed"] for cid in CASES))


class Evidence(unittest.TestCase):
    def test_raw_span_is_claimed_only_for_exact_unique_bytes(self):
        for cid in CASES:
            data, out = run(cid)
            cand = out["candidate"]
            if not cand:
                continue
            dom = cand["dom_serialization"].encode("utf-8")
            if cand["raw_byte_span"]:
                span = cand["raw_byte_span"]
                self.assertEqual(data[span["byte_start"] : span["byte_end"]], dom, cid)
                self.assertEqual(data.count(dom), 1, cid)
            else:
                self.assertNotEqual(data.count(dom), 1, cid)

    def test_payloads_are_rebuilt_from_whole_elements_without_normalisation(self):
        data, out = run("P01")
        doc = lxml.html.document_fromstring(data)
        dt = doc.xpath("//*[@id=$a]", a="numpy.where")[0]
        dd = dt.getnext()
        self.assertEqual(out["candidate"]["text_content"], dt.text_content() + (dt.tail or "") + dd.text_content())
        self.assertIn("array([ 0,  1,  2,  3,  4, 50, 60, 70, 80, 90])", out["candidate"]["text_content"])
        self.assertIn("loadTryExamplesConfig", out["candidate"]["text_content"])  # script text stays: nothing removed

    def test_tail_after_the_last_element_is_excluded(self):
        "negative control (H3): lxml's default tostring() would carry the stray text after the dd"
        data, out = run("C02")
        doc = lxml.html.document_fromstring(data)
        dd = doc.xpath("//*[@id=$a]", a="pkg.store")[0].getnext()
        self.assertIn("MARK-STORE-STRAY", lxml.html.tostring(dd, encoding="unicode"))
        self.assertNotIn("MARK-STORE-STRAY", out["candidate"]["dom_serialization"])
        self.assertIn("STRAY_CONTENT_IN_OBJECT_DL", out["reasons"])


class Budget(unittest.TestCase):
    def test_context_counts_query_source_labels_and_payload(self):
        _, out = run("C13")
        ctx = out["contexts"]["text_content"]
        text = ctx["context"]
        self.assertEqual(len(text.encode("utf-8")), ctx["context_bytes"])
        self.assertLessEqual(ctx["context_bytes"], au.BUDGET_BYTES)
        payload = out["candidate"]["text_content"]
        self.assertEqual(text.count(payload), 1)
        self.assertGreater(ctx["context_bytes"], len(payload.encode("utf-8")))
        for label in (
            "query: anchor_id=pkg.Client.open",
            f"sha256={out['source']['sha256']}",
            "not byte offsets",
            "BEGIN UNIT",
        ):
            self.assertIn(label, text)
        self.assertIn(f"sha256={au.sha256(payload.encode('utf-8'))} bytes={len(payload.encode('utf-8'))}", text)

    def test_over_budget_unit_stays_whole_and_is_review(self):
        _, out = run("C14")
        for rep in au.REPRESENTATIONS:
            self.assertEqual(out["status"][rep], "REVIEW_OVER_BUDGET")
            self.assertIsNone(out["contexts"][rep]["context"])
            self.assertGreater(out["contexts"][rep]["context_bytes"], au.BUDGET_BYTES)
            self.assertIn("MARK-BIG-22", out["candidate"][rep])

    def test_multibyte_budget_is_counted_in_bytes(self):
        _, out = run("C18")
        payload = out["candidate"]["text_content"]
        self.assertGreater(len(payload.encode("utf-8")), len(payload))
        self.assertEqual(out["candidate"]["text_bytes"], len(payload.encode("utf-8")))


class Review(unittest.TestCase):
    def test_duplicate_id_is_never_resolved(self):
        "negative control (H2): get_element_by_id picks one of the two silently"
        data, out = run("C17")
        self.assertIsNone(out["candidate"])
        self.assertEqual(len(out["matches"]), 2)
        chosen = lxml.html.document_fromstring(data).get_element_by_id("pkg.dup")
        self.assertIn(chosen.sourceline, [m["sourceline"] for m in out["matches"]])

    def test_normalised_spellings_are_reported_not_selected(self):
        for cid in ("C19", "C20"):
            _, out = run(cid)
            self.assertIsNone(out["candidate"])
            self.assertEqual(out["near_matches"], ["pkg.naïve"])
            self.assertEqual(out["reasons"], ["ID_NORMALIZATION_MISMATCH"])

    def test_anchor_is_data_not_xpath(self):
        for anchor in ('pkg.fetch"] | //*[@id="pkg.store', "x' or '1'='1", "//dt"):
            _, out = run("C01", anchor)
            self.assertEqual(out["reasons"], ["MISSING_ID"], anchor)
            self.assertEqual(out["matches"], [])

    def test_parser_diagnostics_are_kept(self):
        _, out = run("C23")
        types = {d["type"] for d in out["parser"]["diagnostics"]}
        self.assertIn("ERR_INVALID_ENCODING", types)
        self.assertTrue(out["candidate"]["diagnostics_in_unit_lines"])

    def test_generic_ancestor_rule_is_not_applied(self):
        "an id inside the dd (a div) or on the section is review, not the enclosing unit"
        for cid in ("P03", "P04", "C04"):
            _, out = run(cid)
            self.assertEqual(out["reasons"], ["NOT_A_SIGNATURE"], cid)
            self.assertIsNone(out["candidate"], cid)


class ExistingApis(unittest.TestCase):
    def test_trafilatura_structured_output_has_no_ids(self):
        "H1: trafilatura.extract() XML keeps no id attributes"
        try:
            import trafilatura
        except ImportError as err:  # macOS replay may lack Trafilatura's other dependencies
            self.skipTest(f"trafilatura not importable: {err}")
        xml = trafilatura.extract((ROOT / CASES["P01"]["file"]).read_bytes(), output_format="xml", include_formatting=True)
        self.assertIsNotNone(xml)
        self.assertIsNone(re.search(r"\sid=", xml))


if __name__ == "__main__":
    unittest.main()

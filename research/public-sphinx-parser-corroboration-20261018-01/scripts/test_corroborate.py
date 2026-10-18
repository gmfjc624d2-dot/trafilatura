"""Focused offline tests of corroborate.py (stdlib unittest; lxml and the retained html5lib wheels).

Run from the research directory with the retained wheels on PYTHONPATH:
    python -m unittest discover -s scripts -v
The expected texts and boundaries below are written from the fixture bytes, not from a run.
"""

import hashlib
import json
import re
import unittest
import xml.etree.ElementTree as ET
from functools import cache

import corroborate as co
import html5lib
import six
import webencodings
from html5lib.html5parser import ParseError

EXP = json.loads((co.ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
CASES = {c["id"]: c for c in EXP["cases"]}


@cache
def rep(case_id):
    case = CASES[case_id]
    return co.report((co.REPO / case["file"]).read_bytes(), case["anchor"], case["file"])


def unit(case_id, side):
    return rep(case_id)["trees"][side]["unit"]


class Policy(unittest.TestCase):
    def test_retained_wheels_and_pinned_helper_are_in_use(self):
        self.assertEqual((html5lib.__version__, six.__version__, webencodings.VERSION), ("1.1", "1.17.0", "0.5.1"))
        self.assertIs(co.ET, ET)  # html5lib's etree builder uses the stdlib ElementTree here
        self.assertEqual(hashlib.sha256((co.REPO / co.HELPER).read_bytes()).hexdigest(), co.HELPER_SHA256)

    def test_mirror_rule_agrees_with_the_helper_on_lxml(self):
        for cid in CASES:
            checks = rep(cid)["checks"]
            for name in (
                "lxml_parse_diagnostics_equal_helper",
                "mirror_reasons_equal_helper",
                "mirror_membership_equals_helper",
            ):
                self.assertIs(checks[name], True, (cid, name))
            self.assertIn(checks["lxml_text_rule_equals_helper_text_content"], (True, None), cid)

    def test_any_diagnostic_keeps_review_and_the_helper_is_unchanged(self):
        n1 = rep("N1")
        self.assertIn("PARSER_DIAGNOSTICS_PRESENT", n1["existing_helper"]["reasons"])
        self.assertEqual(n1["triage"]["disposition"], "REVIEW")
        for cid in CASES:
            r = rep(cid)
            if r["parsers"]["lxml"]["diagnostics"] or r["parsers"]["html5lib"]["errors"]:
                self.assertEqual(r["triage"]["disposition"], "REVIEW", cid)

    def test_complete_bytes_and_no_implied_claims(self):
        forbidden = re.compile(EXP["forbidden_report_keys"])
        for cid, case in CASES.items():
            data = (co.REPO / case["file"]).read_bytes()
            r = rep(cid)
            self.assertEqual((r["source"]["sha256"], r["source"]["bytes"]), (hashlib.sha256(data).hexdigest(), len(data)))
            text = json.dumps(r)
            self.assertEqual([k for k in re.findall(r'"([^"]+)":', text) if forbidden.search(k)], [], cid)


class TextRule(unittest.TestCase):
    def test_comment_and_pi_data_excluded_tails_kept_final_tail_dropped(self):
        want = "tail()¶\nAlpha Beta Gamma Delta Epsilon, see pkg.other."
        for side in ("lxml", "html5lib"):
            u = unit("C2", side)
            self.assertEqual(u["text"], want, side)
            self.assertEqual(u["text_utf8_bytes"], len(want.encode("utf-8")))
            self.assertEqual(u["links"], [{"href": "#pkg.tail", "text": "¶"}, {"href": "#pkg.other", "text": "pkg.other"}])
        self.assertIs(rep("C2")["checks"]["html5lib_text_rule_equals_itertext"], True)

    def test_rule_on_a_hand_built_elementtree(self):
        p = ET.Element(co.XHTML + "p")
        p.text = "a"
        comment = ET.Comment("hidden")
        comment.tail = "b"
        em = ET.SubElement(p, co.XHTML + "em")
        p.insert(0, comment)
        em.text, em.tail = "c", "d"
        node = co.view(p, co.et_kind)
        self.assertEqual(co.text_of(node), "abcd")
        self.assertEqual("".join(p.itertext()), "abcd")
        dt, dd = ET.Element(co.XHTML + "dt"), ET.Element(co.XHTML + "dd")
        dt.text, dt.tail, dd.text, dd.tail = "x", "\n", "y", "TRAILING"
        self.assertEqual(co.unit_text([co.view(dt, co.et_kind), co.view(dd, co.et_kind)]), "x\ny")

    def test_independent_expected_texts(self):
        for cid in ("N1", "N2", "N3", "N4", "N5", "C1"):
            for side in ("lxml", "html5lib"):
                self.assertEqual(unit(cid, side)["text"], CASES[cid][side]["text"], (cid, side))


class Structure(unittest.TestCase):
    def test_namespace_mapping_is_explicit(self):
        self.assertEqual(co.et_kind(ET.Element(co.XHTML + "dt")), ("element", "dt"))
        svg = ET.Element("{http://www.w3.org/2000/svg}dt", {"class": "sig sig-object"})
        self.assertEqual(co.et_kind(svg), ("element", "{http://www.w3.org/2000/svg}dt"))
        self.assertFalse(co.is_signature(co.view(svg, co.et_kind)))
        self.assertEqual(rep("N5")["parsers"]["html5lib"]["returned_root"], co.XHTML + "html")

    def test_duplicate_live_ids_are_never_resolved(self):
        r = rep("C17")
        for side in ("lxml", "html5lib"):
            tree = r["trees"][side]
            self.assertEqual((tree["match_count"], tree["unit"], tree["rule_reasons"]), (2, None, ["DUPLICATE_ID"]), side)
            self.assertEqual(len(tree["exact_matches"]), 2)
        self.assertEqual(r["triage"]["disposition"], "REVIEW")

    def test_comment_lookalike_is_not_a_match(self):
        r = rep("N2")
        self.assertEqual([r["trees"][s]["match_count"] for s in ("lxml", "html5lib")], [1, 1])
        self.assertEqual(unit("N2", "html5lib")["text"], "target()A")

    def test_reparenting_disagreement_is_review_even_with_equal_text(self):
        r = rep("C1")
        self.assertEqual(unit("C1", "lxml")["text"], unit("C1", "html5lib")["text"])
        self.assertNotEqual(unit("C1", "lxml")["membership"], unit("C1", "html5lib")["membership"])
        self.assertIn("MEMBERSHIP_DIFFERS", [f["finding"] for f in r["comparison"]["findings"]])
        self.assertEqual(r["triage"]["disposition"], "REVIEW")

    def test_encoding_disagreement_is_review(self):
        data = (co.REPO / CASES["N5"]["file"]).read_bytes()
        lx, lx_tree = co.parse_lxml(data, "pkg.clean")
        h5, h5_tree = co.parse_html5lib(data, "pkg.clean")
        for tree in (lx_tree, h5_tree):
            del tree["unit"]["_unit_nodes"]
        self.assertEqual(co.compare(lx, h5, lx_tree, h5_tree)[0], [])
        h5["encoding"] = "windows-1252"  # what html5lib would report had the meta prescan found nothing
        self.assertEqual([f["finding"] for f in co.compare(lx, h5, lx_tree, h5_tree)[0]], ["ENCODING_DISAGREEMENT"])

    def test_strict_mode_would_stop_at_the_first_error(self):
        "negative control: strict=True raises on N1, so the experiment uses strict=False and keeps every error"
        data = (co.REPO / CASES["N1"]["file"]).read_bytes()
        with self.assertRaises(ParseError):
            html5lib.HTMLParser(tree=html5lib.getTreeBuilder("etree"), strict=True).parse(data, useChardet=False)
        self.assertGreaterEqual(len(rep("C1")["parsers"]["html5lib"]["errors"]), 2)


if __name__ == "__main__":
    unittest.main()

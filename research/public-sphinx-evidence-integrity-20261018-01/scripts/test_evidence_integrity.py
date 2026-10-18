"""Focused offline tests of the evidence-integrity repair (stdlib unittest, lxml only).

Run from the research directory: python -m unittest discover -s scripts -v
Negative controls run the unmodified 7345bfe copies and assert that they still show the defect.
The comparator tests start the two comparators as subprocesses on mutated copies of the
committed old results.json, written to a temporary directory that the test removes itself.
"""

import codecs
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import anchor_unit as au
import anchor_unit_baseline_7345bfe as baseline
import compare_results as cmp
import grading as g

NEW = {c["id"]: c for c in g.EXP["new_cases"]}
OLD = g.old_cases()
MUTATIONS = g.EXP["mutation_controls"]["mutations"]


def run(helper, case_id):
    case = NEW[case_id]
    data = (g.ROOT / case["file"]).read_bytes()
    return data, helper.select_unit(data, case["anchor"], path=case["file"], origin=case["origin"])


def region(name):
    r = g.FACTS["regions"][name]
    return r["byte_start"], r["byte_end"]


class ParserDiagnostics(unittest.TestCase):
    def test_late_diagnostic_inside_the_dd_requires_review(self):
        data, out = run(au, "N1")
        self.assertEqual(out["reasons"], ["PARSER_DIAGNOSTICS_PRESENT"])
        self.assertEqual(set(out["status"].values()), {"REVIEW"})
        self.assertIn("Third line of description.", out["candidate"]["text_content"])  # candidate kept whole
        self.assertTrue(g.strict_equal(out["parser"]["diagnostics"], g.fresh_diagnostics(data)))  # every field kept
        self.assertEqual([(d["line"], d["type"]) for d in out["parser"]["diagnostics"]], [(3, "ERR_TAG_NAME_MISMATCH")])

    def test_baseline_still_accepts_it(self):
        "negative control (D1): the start-line filter drops the line 3 diagnostic"
        _, out = run(baseline, "N1")
        self.assertEqual(out["reasons"], [])
        self.assertEqual(set(out["status"].values()), {"OK_STRUCTURAL_UNIT"})

    def test_start_lines_are_no_end_range(self):
        "the dd's text runs to line 5 of the file while every unit element starts on line 1"
        data, out = run(au, "N1")
        self.assertEqual((out["candidate"]["first_line"], out["candidate"]["last_line"]), (1, 1))
        self.assertEqual(g.FACTS["cases"]["N1"]["token_lines"]["Third line"], 4)
        self.assertEqual(data.count(b"\n"), 4)

    def test_any_diagnostic_on_the_page_requires_review(self):
        _, outside = run(au, "N4")
        _, control = run(au, "N5")
        self.assertEqual(outside["reasons"], ["PARSER_DIAGNOSTICS_PRESENT"])
        self.assertEqual(outside["parser"]["diagnostics"][0]["line"], 12)
        self.assertNotIn("MARK-OUTSIDE-FOOTER", outside["candidate"]["text_content"])
        self.assertEqual((control["reasons"], control["parser"]["diagnostics"]), ([], []))
        self.assertEqual(set(control["status"].values()), {"OK_STRUCTURAL_UNIT"})
        self.assertEqual(run(baseline, "N4")[1]["reasons"], [])  # negative control (D1)

    def test_reason_also_without_candidate_and_old_reason_gone(self):
        outs = {case["id"]: g.run_old_case(au, case, entry) for case, entry in OLD}
        self.assertEqual(outs["C17"]["reasons"], ["DUPLICATE_ID", "PARSER_DIAGNOSTICS_PRESENT"])
        self.assertIsNone(outs["C17"]["candidate"])
        self.assertFalse(any("PARSER_RECOVERY_IN_UNIT" in o["reasons"] for o in outs.values()))


class NoSourceAlignment(unittest.TestCase):
    def test_no_span_offset_or_count_in_any_output(self):
        outs = [run(au, cid)[1] for cid in NEW] + [g.run_old_case(au, case, entry) for case, entry in OLD]
        self.assertEqual([k for o in outs for k in g.forbidden_keys(o)], [])

    def test_comment_copy_is_not_the_live_node(self):
        data, out = run(au, "N2")
        dom = out["candidate"]["dom_serialization"].encode("utf-8")
        live_start, live_end = region("N2.live_unit")
        self.assertNotEqual(data[live_start:live_end], dom)  # the live source has &#65;, the DOM has A
        self.assertIn(b"&#65;", data[live_start:live_end])
        self.assertEqual(out["candidate"]["text_content"], "target()A")
        _, old = run(baseline, "N2")  # negative control (D2): the baseline's unique match is the comment
        comment = g.FACTS["cases"]["N2"]["comment"]
        span = old["candidate"]["raw_byte_span"]
        self.assertEqual((span["byte_start"], span["byte_end"]), region("N2.comment_copy"))
        self.assertTrue(comment["byte_start"] < span["byte_start"] < span["byte_end"] <= comment["byte_end"])

    def test_identities_are_distinct_and_recomputable(self):
        for cid in ("N2", "N3"):
            data, out = run(au, cid)
            cand = out["candidate"]
            self.assertEqual((out["source"]["sha256"], out["source"]["bytes"]), (g.sha256(data), len(data)))
            for rep, key in (("dom_serialization", "dom"), ("text_content", "text")):
                raw = cand[rep].encode("utf-8")
                self.assertEqual((cand[f"{key}_sha256"], cand[f"{key}_bytes"]), (g.sha256(raw), len(raw)))
            self.assertEqual(len({out["source"]["sha256"], cand["dom_sha256"], cand["text_sha256"]}), 3)

    def test_windows_1252_document(self):
        data, out = run(au, "N3")
        self.assertEqual(codecs.lookup(out["parser"]["encoding"]).name, "cp1252")
        self.assertIn("Café costs 5 €, “quoted”.", out["candidate"]["text_content"])
        start, end = region("N3.live_unit")
        dom = out["candidate"]["dom_serialization"]
        self.assertEqual(out["candidate"]["dom_bytes"], len(dom.encode("utf-8")))
        self.assertEqual(dom.encode("cp1252"), data[start:end])  # same DOM, other encoding: not the identity
        self.assertEqual(out["candidate"]["dom_bytes"] - (end - start), 7)
        _, old = run(baseline, "N3")  # negative control (D2b): the span holds cp1252 bytes
        span = old["candidate"]["raw_byte_span"]
        self.assertNotEqual(data[span["byte_start"] : span["byte_end"]], dom.encode("utf-8"))


class Budget(unittest.TestCase):
    def test_template_budget_and_scope_as_preregistered(self):
        self.assertEqual(au.CONTEXT_TEMPLATE, g.EXP["context_template"])
        self.assertEqual(au.BUDGET_BYTES, g.EXP["budget_bytes"])
        self.assertEqual(au.BUDGET_SCOPE, g.EXP["budget_scope"])
        self.assertEqual(au.IDENTITIES, g.EXP["repaired_rules"]["R3_identities"])
        _, out = run(au, "N5")
        self.assertEqual({c["scope"] for c in out["contexts"].values()}, {au.BUDGET_SCOPE})
        self.assertNotIn(au.BUDGET_SCOPE, out["contexts"]["text_content"]["context"])  # a label, not counted text

    def test_old_contexts_stay_byte_identical(self):
        for case, entry in OLD:
            out = g.run_old_case(au, case, entry)
            got = {rep: {k: v for k, v in c.items() if k != "scope"} for rep, c in out["contexts"].items()}
            self.assertTrue(g.strict_equal(got, entry["contexts"]), case["id"])


class OldCases(unittest.TestCase):
    def test_baseline_copy_reproduces_the_committed_entries(self):
        for case, entry in OLD:
            committed = {k: v for k, v in entry.items() if k not in ("case", "checks")}
            out = cmp.as_json(g.run_old_case(baseline, case, entry))
            self.assertEqual(cmp.compare(out, committed, exceptions=()), [], case["id"])

    def test_repaired_output_is_the_preregistered_transform(self):
        for case, entry in OLD:
            out = cmp.as_json(g.run_old_case(au, case, entry))
            self.assertEqual(cmp.compare(out, g.transform_old(entry), exceptions=()), [], case["id"])

    def test_in_memory_output_is_not_json_typed(self):
        "found by the first run: near_matches come from xpath() as lxml str subclasses; the strict comparator refuses them"
        case, entry = next((c, e) for c, e in OLD if c["id"] == "C19")
        out = g.run_old_case(au, case, entry)
        self.assertIsNot(type(out["near_matches"][0]), str)
        with self.assertRaises(TypeError):
            cmp.compare(out, out)
        self.assertIs(type(cmp.as_json(out)["near_matches"][0]), str)


class Comparator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = g.OLD_RESULTS.read_text(encoding="utf-8")
        cls.doc = cmp.loads(cls.text)

    def test_json_types_are_distinct(self):
        for a, b in ((True, 1), (1, 1.0), (0.0, -0.0), (None, False), ("1", 1), ([], {})):
            self.assertNotEqual(cmp.compare(a, b), [], (a, b))

    def test_invalid_inputs_are_rejected(self):
        for text in ('{"a": 1, "a": 1}', '{"a": NaN}', '{"a": Infinity}'):
            with self.assertRaises(cmp.InvalidJSONError):
                cmp.loads(text)

    def test_difference_paths_as_preregistered(self):
        for m in MUTATIONS:
            mutated = g.mutate(self.text, m["ops"])
            self.assertEqual(mutated != self.text, m["id"] != "M00", m["id"])
            if m["repaired"] == "rejected":
                self.assertRaises(cmp.InvalidJSONError, cmp.loads, mutated)
                continue
            paths = sorted({cmp.render(p) for p, *_ in cmp.compare(self.doc, cmp.loads(mutated))})
            self.assertEqual(paths == [], m["repaired"] == "allowed", m["id"])
            if m["repaired_paths"] is not None:
                self.assertEqual(paths, sorted(m["repaired_paths"]), m["id"])

    def test_both_command_lines_classify_as_preregistered(self):
        "the repaired CLI meets each control; the baseline CLI (negative control) misses what was predicted"
        scripts = {"repaired": "compare_results.py", "baseline": "compare_results_baseline_7345bfe.py"}
        with tempfile.TemporaryDirectory(prefix="evidence-integrity-test-") as tmp:
            for m in MUTATIONS:
                path = Path(tmp) / f"{m['id']}.json"
                path.write_text(g.mutate(self.text, m["ops"]), encoding="utf-8", newline="\n")
                for name, script in scripts.items():
                    code, stderr, _ = g.run_comparator(g.ROOT / "scripts" / script, g.OLD_RESULTS, path)
                    self.assertEqual(g.classify(code, stderr, m["repaired"] == "allowed"), m[name], (m["id"], name))

    def test_exceptions_are_exactly_three_environment_values(self):
        self.assertEqual([list(p) for p in cmp.ENVIRONMENT_EXCEPTIONS], g.EXP["environment_exceptions"])
        other = json.loads(self.text)
        for key in ("python", "platform", "machine"):
            other["environment"][key] = "different"
        self.assertEqual(cmp.compare(self.doc, other), [])
        other["environment"]["libxml2_compiled"] = "2.14.7"
        self.assertEqual([cmp.render(p) for p, *_ in cmp.compare(self.doc, other)], ["$.environment.libxml2_compiled"])

    def test_cli_exit_codes(self):
        script = str(g.ROOT / "scripts" / "compare_results.py")
        same = subprocess.run(
            [sys.executable, script, str(g.OLD_RESULTS), str(g.OLD_RESULTS)], capture_output=True, check=False
        )
        self.assertEqual(same.returncode, 0)
        missing = subprocess.run(
            [sys.executable, script, str(g.OLD_RESULTS), "no-such-file.json"], capture_output=True, check=False
        )
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()

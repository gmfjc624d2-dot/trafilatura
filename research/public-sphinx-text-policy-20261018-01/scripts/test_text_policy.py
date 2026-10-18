"""Focused tests of the changed surface only (text oracle, axes and gate, scope, dependencies).

Run from the experiment directory, with the retained wheels on PYTHONPATH through zipimport:
    python -m unittest discover -s scripts -v
Fixtures are read by their pinned paths and sha256 values in fixtures/expectations.json.
"""

import hashlib
import json
import unittest

import replay
import text_policy as tp

co = tp.co
EXP = replay.EXP
CASES = {c["id"]: c for c in json.loads((tp.REPO / replay.PREDECESSOR_EXP).read_text(encoding="utf-8"))["cases"]}
CASES["W1"] = EXP["witness"]


def run(case_id):
    case = CASES[case_id]
    data = (tp.REPO / case["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXP["pins"]["fixtures"][case["file"]], case["file"]
    return tp.analyse(data, case["anchor"], case["file"])


class Patched:
    "Replace one name in the exec'd predecessor (or this) module for one block, then restore it."

    def __init__(self, module, name, value):
        self.module, self.name, self.value = module, name, value

    def __enter__(self):
        self.saved = getattr(self.module, self.name)
        setattr(self.module, self.name, self.value)

    def __exit__(self, *exc):
        setattr(self.module, self.name, self.saved)


class Oracle(unittest.TestCase):
    def test_oracle_equals_the_rule_and_tells_every_mutant_apart_on_c2(self):
        rep, units = run("C2")
        for side, unit in units.items():
            oracle, refused = tp.oracle_text([n.native for n in unit])
            self.assertIsNone(refused)
            self.assertEqual(oracle, rep["trees"][side]["unit"]["text"], side)
            for marker in ("MARK-COMMENT-DATA", "MARK-PI-DATA", "MARK-TAIL-TAIL"):
                self.assertNotIn(marker, oracle)
            self.assertIn("MARK-COMMENT-DATA", tp.mutant_text(unit, "M1"))
            self.assertIn("MARK-TAIL-TAIL", tp.mutant_text(unit, "M3"))
            for m in tp.MUTATIONS:
                self.assertNotEqual(tp.mutant_text(unit, m), oracle, (side, m))

    def test_each_mutated_rule_fails_both_oracle_checks_on_c2(self):
        for m in tp.MUTATIONS:
            with Patched(co, "unit_text", lambda unit, m=m: tp.mutant_text(unit, m)):
                rep, _ = run("C2")
            self.assertEqual([rep["checks"][k] for k in tp.ORACLE_CHECKS], [False, False], m)
            failed = [f for f in rep["comparison"]["findings"] if f["finding"] == "CONSISTENCY_CHECK_FAILED"]
            self.assertEqual(len(failed), 1, m)
            self.assertTrue(set(tp.ORACLE_CHECKS) <= set(failed[0]["checks"]), m)
            self.assertEqual(rep["structural_corroboration"]["disposition"], "REVIEW")

    def test_a_wrong_final_tail_turns_the_clean_witness_to_review(self):
        rep, _ = run("W1")
        self.assertEqual(rep["structural_corroboration"]["disposition"], "STRUCTURE_CORROBORATED")
        with Patched(co, "unit_text", lambda unit: tp.mutant_text(unit, "M3")):
            rep, _ = run("W1")
        self.assertEqual([rep["checks"][k] for k in tp.ORACLE_CHECKS], [False, False])
        self.assertIn("CONSISTENCY_CHECK_FAILED", rep["structural_corroboration"]["because"])
        self.assertEqual(rep["structural_corroboration"]["disposition"], "REVIEW")

    def test_the_oracle_runs_without_the_rule_functions(self):
        rep, units = run("C2")

        def refuse(*_):
            raise AssertionError("the oracle called the rule")

        with Patched(co, "text_of", refuse), Patched(co, "unit_text", refuse):
            for side, unit in units.items():
                self.assertEqual(tp.oracle_text([n.native for n in unit])[0], rep["trees"][side]["unit"]["text"])

    def test_an_oracle_refusal_is_review_never_a_pass(self):
        el = co.ET.Element("p")
        el.text = "form\x0cfeed"
        oracle, refused = tp.oracle_text([el])
        self.assertIsNone(oracle)
        self.assertIn("XML compatible", refused)
        with Patched(tp, "oracle_text", lambda _top: (None, "refused for the test")):
            rep, _ = run("W1")
        self.assertEqual([rep["checks"][k] for k in tp.ORACLE_CHECKS], [None, None])
        self.assertIn(
            {"finding": "CONSISTENCY_CHECK_UNAVAILABLE", "checks": list(tp.ORACLE_CHECKS)}, rep["comparison"]["findings"]
        )
        self.assertEqual(rep["structural_corroboration"]["disposition"], "REVIEW")


class Axes(unittest.TestCase):
    def test_w1_structural_axis_helper_status_and_gate_are_separate(self):
        rep, _ = run("W1")
        self.assertEqual(rep["structural_corroboration"]["disposition"], "STRUCTURE_CORROBORATED")
        self.assertEqual(rep["existing_helper"]["reasons"], [])
        self.assertEqual(
            rep["existing_helper"]["status"], {"dom_serialization": "REVIEW_OVER_BUDGET", "text_content": "REVIEW_OVER_BUDGET"}
        )
        gate = rep["consumer_gate"]
        self.assertEqual(gate["value"], "NOT_GRANTED")
        for word in ("admission", "size limit", "semantic sufficiency", "to a model", "REVIEW_OVER_BUDGET"):
            self.assertIn(word, gate["prohibition"])
        self.assertNotIn("triage", rep)

    def test_corrected_r9_holds_where_the_historical_r9_does_not(self):
        case = CASES["W1"]
        data = (tp.REPO / case["file"]).read_bytes()
        rep, _ = run("W1")
        fresh = co.helper.select_unit(
            data, case["anchor"], path=case["file"], origin="public fixture", budget=co.helper.BUDGET_BYTES
        )
        self.assertEqual(set(replay.corrected_r9(rep, fresh).values()), {True})
        self.assertFalse(replay.historical_r9(rep))

    def test_diagnostics_ambiguity_and_structural_differences_stay_review(self):
        for case_id, finding in (("N1", "LXML_DIAGNOSTICS_PRESENT"), ("C17", "ID_NOT_UNIQUE"), ("C1", "TOPOLOGY_DIFFERS")):
            rep, _ = run(case_id)
            self.assertIn(finding, [f["finding"] for f in rep["comparison"]["findings"]], case_id)
            self.assertEqual(rep["structural_corroboration"]["disposition"], "REVIEW", case_id)
            self.assertEqual(rep["consumer_gate"]["value"], "NOT_GRANTED", case_id)
        rep, _ = run("N1")
        self.assertIn("EXISTING_HELPER_REASONS_PRESENT", rep["structural_corroboration"]["because"])


class Observation(unittest.TestCase):
    def test_itertext_is_recorded_and_never_a_check_or_finding(self):
        rep, _ = run("C2")
        obs = rep["observations"]["itertext"]
        self.assertEqual(obs["html5lib"]["equals_rule"], not obs["elementtree_c_accelerated"])
        self.assertEqual(obs["html5lib"]["equals_rule_with_comment_payload"], bool(obs["elementtree_c_accelerated"]))
        self.assertFalse([k for k in rep["checks"] if "itertext" in k])
        self.assertEqual([f["finding"] for f in rep["comparison"]["findings"]], ["HTML5LIB_ERRORS_PRESENT"])


class Scope(unittest.TestCase):
    def test_the_stated_scope_is_the_compared_one(self):
        rep, _ = run("N5")
        self.assertEqual(rep["comparison_scope"], EXP["comparison_scope"])
        self.assertEqual(co.SHOWN_ATTRS, ("id", "class", "href"))
        self.assertIn("only the id, class and href attributes", rep["comparison_scope"])
        self.assertIn("the full DOM", rep["comparison_scope"])

    def test_dependencies_are_the_pinned_wheels(self):
        for name, d in tp.dependencies().items():
            self.assertTrue(d["zipimported_from_wheel"], name)
            self.assertEqual(d["wheel_sha256"], EXP["pins"]["code_and_wheels"][d["wheel"]], name)


if __name__ == "__main__":
    unittest.main()

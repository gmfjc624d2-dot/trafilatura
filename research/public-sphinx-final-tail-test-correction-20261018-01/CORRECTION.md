# Correction of one wrong test assertion (written before execution)

Request: `public-sphinx-final-tail-test-correction-20261018-01`. This directory is additive. It
continues from `d8126f57ceb34a3d455a04881b606d2d86220fd7` (`logs/00_recovery.log`): at the start,
local and remote were equal, there were no commits on either side, and the tree was clean, so there
was no concurrent divergence.

Nothing earlier is edited. That covers:
* the producer (`text_policy.py`, `replay.py`), the oracle and the fixtures;
* the earlier test, reports, logs and manifests.

The historical failure stays exactly as recorded in
`research/public-sphinx-text-policy-20261018-01/logs/21_unittest_run1.log`.

## What was wrong

`test_oracle_equals_the_rule_and_tells_every_mutant_apart_on_c2`, in the earlier
`scripts/test_text_policy.py` (sha256 `deaf6ffa…7100`, introduced in `c38a2a2`), asserted that the
M3 mutant contains `MARK-TAIL-TAIL`:

    self.assertIn("MARK-TAIL-TAIL", tp.mutant_text(unit, "M3"))

M3 is "the last unit element's tail appended". The selected C2 unit is `dt` + `dd`, and its last
element is the `dd`. In `research/public-sphinx-parser-corroboration-20261018-01/fixtures/c2_text_tail.html`
(the retained inspection, `research/public-sphinx-text-policy-20261018-01/logs/22_posthoc_c2_final_tail.log`):

    10: <dd>…</dd>
    11: </dl>
    12: <p>Closing paragraph. MARK-TAIL-TAIL</p>

* **The dd's tail is the single LF between `</dd>` and `</dl>`.** That LF is the dd's tail in both
  trees: the committed C2 report gives `excluded_final_tail_utf8_bytes = 1` for lxml and for
  html5lib.
* **`MARK-TAIL-TAIL` is not part of any unit tail.** It is text inside the next `<p>`, after the
  `dl` has closed, so it is outside the `dl`.

The fixture's own description (`absent_from_text`) was right that the marker is excluded from the
unit text. The wrong step was the test's: it inferred that M3 would bring the marker in. M3 can only
bring in the dd's own tail.

The module was right. The replay graded M3 as detected on C2 for both trees, because the mutant ends
with that extra LF.

## The correction (only that assertion)

`patch/test_text_policy.diff` (sha256 `597f314b…0ee0`) is applied to `baseline/test_text_policy.py`
(byte-identical to the earlier file). It gives `corrected/test_text_policy.py` (sha256
`fc722920…1fca`):

```diff
--- baseline/test_text_policy.py
+++ corrected/test_text_policy.py
@@ -49,7 +49,8 @@
             for marker in ("MARK-COMMENT-DATA", "MARK-PI-DATA", "MARK-TAIL-TAIL"):
                 self.assertNotIn(marker, oracle)
             self.assertIn("MARK-COMMENT-DATA", tp.mutant_text(unit, "M1"))
-            self.assertIn("MARK-TAIL-TAIL", tp.mutant_text(unit, "M3"))
+            self.assertEqual(unit[-1].native.tail, "\n", side)
+            self.assertEqual(tp.mutant_text(unit, "M3"), oracle + "\n", side)
             for m in tp.MUTATIONS:
                 self.assertNotEqual(tp.mutant_text(unit, m), oracle, (side, m))
```

For each parser side (the enclosing loop runs over lxml and html5lib), the corrected test now checks
two things:
1. The selected unit's final *native* node has tail LF. `unit[-1]` is the dd's node, and `.native`
   is the lxml or ElementTree element itself.
2. The M3 mutant is exactly the unchanged oracle's text plus that LF.

Everything else in the file is unchanged, byte for byte:
* the oracle = rule assertion and the marker-absence assertions (`MARK-TAIL-TAIL` included);
* M1 containing the comment payload, and the M1-M4 loop;
* the other 10 tests: report-level mutations, oracle independence, refusal, axes and gate,
  corrected and historical R9, REVIEW retention, itertext observation, scope, dependency identity.

The docstring's old run command is unchanged too. In this directory, the entry point below is the
command.

## Prediction (before execution)

**11 tests run, all ok, exit 0.**

The reasons for the corrected test:
* the dd tail is LF in both trees (above);
* the oracle equals the rule there (asserted just before, and true in the replay);
* M3 is the rule plus that tail;
* the M1-M4 loop holds, because the replay graded all four as detected on C2 for both trees.

That loop never executed in the earlier run, which stopped at the wrong assertion. This run is its
first execution in a unit test.

The other 10 tests are unchanged and passed in `logs/21`. If anything fails, it is kept and reported
as it is; there is no further edit and no re-run.

## Entry point and dependencies

`scripts/run_corrected_suite.py [RECORD_JSON]`. It works in three steps:
1. It verifies every pin in `sources.json`:
   * 17 earlier public files: the test, `text_policy.py`, `replay.py`, both `expectations.json`,
     `corroborate.py`, `anchor_unit.py`, the comparator, three wheels and six fixtures;
   * the baseline copy, also byte for byte against the earlier test;
   * the corrected copy and the patch.

   Any mismatch gives exit 2 before any test runs.
2. It executes `text_policy.py` and `replay.py` from their verified bytes as importable modules.
   replay's `main()` is never called, so the earlier replay is not re-run.
3. It loads the corrected test module the same way and runs it with unittest at verbosity 2. It
   writes no bytecode.

The dependencies are only the ones already retained:
* html5lib 1.1, six 1.17.0 and webencodings 0.5.1, as the `.whl` files in
  `research/public-sphinx-parser-corroboration-20261018-01/wheels/`, through zipimport on
  `PYTHONPATH`;
* the existing lxml (Linux: 6.1.3, libxml2 2.14.6).

There is no install, no new dependency, and no network: the Linux run uses `unshare -rn`.

## Platform statement

The execution here is **Linux evidence only** (x86_64, Python 3.12.3). It is not macOS
qualification. `RESULT.md` gives the native macOS commands and the comparison criteria.

# Design addendum (before the successor code was written or run)

Written after `a5b6a4d` (the budget witness on the unchanged predecessor) and before
`scripts/text_policy.py`, `scripts/replay.py` and `scripts/test_text_policy.py` existed.
`fixtures/expectations.json` stays as pre-registered in `db51165`; these are implementation
choices that the pre-registration leaves open, recorded now so that none of them is chosen
after seeing successor output.

1. **Oracle input.** `oracle_text()` walks the *native* trees (lxml elements, or the
   ElementTree elements html5lib built), starting from the unit's top-level natives, and not
   the predecessor's node view. A node is copied as an element when its tag is a `str`,
   otherwise (comment, PI, entity) as an empty comment. Its result is libxml2's XPath
   `string()` of the container. It calls nothing from the predecessor's `text_of()` or
   `unit_text()`.
2. **Oracle refusal.** lxml refuses some strings (for example NUL, U+000C or lone surrogates).
   The oracle then returns no text and the reason. The check value is `null`, and a new finding
   `CONSISTENCY_CHECK_UNAVAILABLE` names the check. That finding makes the result REVIEW: a check
   that cannot be made never passes. This finding is not predicted for any of the nine cases.
3. **Explicit R9(b) guard.** The structural disposition is STRUCTURE_CORROBORATED only when
   there is no finding, both trees have a unit, *and* the pinned helper has no reason. Through
   the existing checks, the third condition is already implied by the first two, so no
   disposition is predicted to change. When the helper has a reason,
   `structural_corroboration.because` also lists `EXISTING_HELPER_REASONS_PRESENT`; that entry
   is not a comparison finding.
4. **Mutation controls.** The replay computes them for every unit, but they are not written into
   the reports. They are graded for C2 and W1 as pre-registered, recorded for the rest, and run
   with an M0 control (the mutant function with no mutation must equal the rule). The focused
   tests also show the mutations at report level. They patch the predecessor's `unit_text` inside
   the exec'd module for one call and restore it afterwards:
   * M1-M4 on C2 must make both oracle checks false.
   * M3 (wrong final tail) on W1 must turn STRUCTURE_CORROBORATED into REVIEW.
5. **Report layout.** The predecessor's keys keep their order, with `triage` replaced. The six
   checks are the four predecessor checks in their order, then `lxml_text_rule_equals_oracle`
   and `html5lib_text_rule_equals_oracle`. After `comparison` come `observations`,
   `text_ledger`, `comparison_scope`, `structural_corroboration` and `consumer_gate`.
   `existing_helper` stays at its predecessor position, unchanged. The oracle's text identity
   and any refusal reason are kept in `text_ledger`.
6. **Unchanged-field projection.** For each of the eight regression cases, the replay loads the
   committed predecessor report and the new report with the pinned json-numeric loader. It
   projects both onto the pre-registered unchanged fields and compares them with that
   comparator's `compare()`, which exempts only environment.python, .platform and .machine. The
   projection removes `CONSISTENCY_CHECK_FAILED` from both finding lists, so a new
   `CONSISTENCY_CHECK_UNAVAILABLE` would still show as a difference.
7. **Dependency identity.** The summary records, for html5lib, six and webencodings, whether
   zipimport loaded the module from the pinned wheel path in the predecessor directory, and that
   archive's sha256 at run time. If any is not the pinned wheel, the replay exits 1. Paths in the
   summary and reports are repository-relative, so `--against` can compare a macOS replay with
   the Linux results.
8. **Tests.** There are 11 focused tests of the changed surface:
   * the oracle equals the rule on C2, and the mutants differ;
   * report-level M1-M4 on C2;
   * M3 on W1;
   * the oracle runs with `text_of`/`unit_text` disabled;
   * an oracle refusal leads to REVIEW;
   * the W1 axes and the gate;
   * corrected versus historical R9 on W1;
   * diagnostics, ambiguity and structural differences stay REVIEW (N1, C17, C1);
   * itertext is an observation only (C2);
   * the stated scope matches the compared attributes;
   * the dependencies are the pinned wheels.

   The tests and the replay each run once.

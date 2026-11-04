# Erratum, 2026-11-04 (request `public-pdf-order-erratum-20261104-01`)

**Attribution.** This erratum was written on 2026-11-04 by the Claude Code session
that wrote `REPORT.md`, at the request named above. It corrects `REPORT.md` as
published in commit `d77a5bd18f18b5720f8b704ac220c4aa446a21a6` (`REPORT.md` sha256
`0733f9aa391f2cfad6eff572cc7c97e1210ac927b688b03ff47b62dcaf63232b`); the line numbers
below refer to that published version. The original wording stays in `REPORT.md`:
the only change there is added lines (a notice and markers) that point here. No fixture, manifest,
raw output, run record or measurement was changed. The corrections rely only on
bytes already committed.

## E1: D also splits the final `Tj`; it does not add "only" a `Tm`

**Affected text.** `REPORT.md` line 29 ("D keeps B's drawing order and adds only
C's `Tm`"), line 64 ("Explicit `Tm` only (D vs B)"), line 28 ("C changes two
things"), and line 56. The same wording appears in the D `justification` string in
`fixtures/manifest.json` and in the message of commit `62d91ddb`. Both are left
unchanged so that the fixture bytes stay identical.

**Evidence.** `fixtures/content_streams/B.txt`, op 11, is
`( move the crate more than 12 cm.) Tj`. In `fixtures/content_streams/D.txt` that
single op becomes ops 11–13:
`( move the crate more than ) Tj`, `1 0 0 1 438 720 Tm`, `(12 cm.) Tj`.

**Correction.** D differs from B by *two* operator changes on line 1:
1. The final `Tj` is split into two `Tj` operators.
2. One `Tm` to the suffix's declared origin (438, 720) is inserted between them.

Glyph origins and drawing order are unchanged. C differs from B by the same split
and `Tm` plus the late drawing of `12 cm.`, so C changes three things, not two.
"C/D differ only in drawing order" still holds: they contain the same operation
lines.

**Impact.** No observation changes: D plain is still byte-identical to B, and D
layout still has 36 spaces. What changes is the attribution. B/D varies the split
and the `Tm` together, so the 36 spaces are not observed to follow from the `Tm`
alone. A split-only control was not run. The Mechanism section's account (the
`Tm` measured from the stale `displaced_tx` 228 of the new run r4) needs both
changes, because the split creates the r4/r5 boundary. Reading the pinned source
suggests a split without the `Tm` would keep 1 space; that is derived, not
observed. The equivalent pair is therefore one `Tj` continuing by implicit advance
versus two `Tj` with an explicit `Tm` to the same origin.

## E2: the S1 limit is the *first* `12 cm` in C plain output, not the second

**Affected text.** `REPORT.md` lines 107–110 ("the second `12 cm` in C plain
output … belongs to S1 and not to `Span:`").

**Evidence.** `runs/run3_final_ABCD/raw/C.pypdf_plain.txt` (118 bytes, sha256
`6f573fae2fc3e3cbafd00e907db6a4b77e352d20d08dfd6193ea47e046c47f38`, byte-identical
in run1) contains `12 cm` at character offsets 89 (line 2, `12 cm.`) and 102
(line 3, `Span: 12 cm`). The manifest declares two separate identities with the
same surface string:
* `S1.m1`: tokens `S1.t27` `12` and `S1.t29` `cm`, chars S1:61–65. The `.` is
  `S1.t30`, the sentence terminal, and is not part of the measurement.
* `R1.m1`: `R1.t03` and `R1.t05`, chars R1:06–10.

The comparator's drawing-order alignment puts `S1.t27`/`S1.t29`/`S1.t30` in
period-segment 2 and `R1.t03`/`R1.t05` in segment 3
(`runs/run3_final_ABCD/comparison.json`, `C.pypdf_plain`).

**Correction.** It is the *first* `12 cm` (line 2, `12 cm.`) that has no identity
from text alone, and only the manifest, or geometry under a rule, says it is
`S1.m1` and not `R1.m1`. The second occurrence is `Span: 12 cm`. The rest of the
paragraph stands. Tokens are mapped only by sequence alignment, and that alignment
itself relies on the manifest's drawing order. The PDFs carry no structure tree.

## E3: D has a run boundary without a font change (it carries a `Tm`)

Found while checking E1. **Affected text.** `REPORT.md` line 115 ("In B and D,
font and run boundaries coincide").

**Correction.** In every fixture, each `Tj` that is not preceded by a `Tm` is
preceded by a `Tf` (checked over all four operation indexes in the manifest). The
only same-font run boundaries inside a block are D ops 11→13 and C ops 11→15, and
each carries a `Tm`. The stated uncertainty stands: no fixture has a run boundary
with neither a font change nor a `Tm`.

## Bounded run: label swap in a held layout debug trace

**Question.** If two text labels are exchanged in an otherwise complete layout
debug trace while all numeric fields stay in place, what do `counts_match`,
`runs_with_tx_mismatch` and the per-row `text_matches_run` report?

**Setup.** The input was the held trace
`runs/run3_final_ABCD/raw/D.pypdf_layout_debug.dir/tjs.json`. Records 4
(` move the crate more than `, stale `tx` 72) and 5 (`12 cm.`, correct `tx` 438)
exchanged their `value`, `text` and `_raw_chars` fields; every other field stayed
in place. The comparator `order_compare.compare_layout_tjs` was evaluated
unchanged. Receipts, preserved inputs and the run note are in
`runs/erratum_20261104_label_swap/` (`RUN.md`).

**Result.**
* `counts_match` stays `true`.
* `runs_with_tx_mismatch` stays `D.r1–D.r4`.
* `text_matches_run` turns `false` for exactly D.r4 and D.r5; these are the only
  changed result fields.
* D.r5 keeps `tx_matches: true` and matching `displaced_tx` (474) while its label
  now reads ` move the crate more than `.

**Which checks distinguish what:**
* *Identity* (which declared run a record represents): only the per-row
  `text_matches_run`. No summary field aggregates it, so a reader of
  `counts_match` and `runs_with_tx_mismatch` alone sees no change. The existing
  per-row field is sufficient, so no new status flag was added.
* *Pairing* (record k paired with run k by stream position): `counts_match` checks
  only cardinality, a necessary but not sufficient condition. `text_matches_run`
  is the only check that the positional pairing agrees with the labels. It does
  not say whether the label or the numbers are wrong.
* *Positional agreement*: `tx_matches` and `runs_with_tx_mismatch` compare
  observed `tx` with the expected `tx` of the positionally paired run, and they are
  blind to labels. `ty` and `displaced_tx` are recorded but not evaluated by any
  boolean. Nothing checks a label's length against its displacement (D.r5's
  26-character label against a 36 pt advance).

This establishes the comparator's behaviour for this one controlled execution on
these exact bytes. `RUN.md` lists what remains unobserved: interpreter startup,
imported module bytes, the self-attested ordering, and older runs, which have no
receipts and received none.

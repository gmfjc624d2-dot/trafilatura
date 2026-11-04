# Report: styled runs and a late-painted measurement (public_pdf_order_20261103)

Request `public-styled-prose-fixture-20261103-01`. Fictional text, four tiny
generated PDFs, pinned extractors, **Linux x86_64 only**. Evidence:
`runs/run3_final_ABCD/` (final), `runs/run1_ABC/` (initial three controls),
`runs/run2_ABCD/` (after adding D; raw outputs byte-identical to run3).

> **Erratum (2026-11-04).** Three statements below are corrected in
> [ERRATUM.md](ERRATUM.md); their original wording is kept unchanged and marked:
> E1, D also splits the final `Tj` (it does not add only a `Tm`); E2, the S1 limit
> is the *first* `12 cm` in C plain output; E3, D has a same-font run boundary
> (with a `Tm`). The erratum also reports a bounded label-swap run of the comparator.

## Question

Can controlled style changes or a late-painted measurement change the extracted
order or the apparent sentence membership while the declared glyph positions stay
the same? The answer keeps three orders apart:

| order | defined by | A | B | C | D |
|---|---|---|---|---|---|
| declared (author's structure: S1, S2, R1, R2) | `manifest.json` | – | – | – | – |
| drawing (paint sequence) | content stream | = declared | = declared | **suffix `12 cm.` after S2** | = declared |
| geometric (origin y desc, x asc; a rule, not semantics) | glyph origins | = declared | = declared | = declared | = declared |

All four PDFs place the same 114 glyphs at the same origins: Courier family,
`/Widths` 600 for codes 32..126, 10 pt, so every glyph advances 6.0 pt. They differ
only in the content stream (every other PDF object is byte-identical):

* **A**: one Courier `Tj` per line.
* **B**: as A, but `not` is drawn in Courier-Bold, and `closed` is split into `clo`
  (Courier) + `sed` (Courier-Oblique). Runs continue by implicit advance.
* **C**: as B, but `12 cm.` is painted after S2, placed by `1 0 0 1 438 720 Tm`.
* **D**: added after run1, because C changes two things at once relative to B.
  D keeps B's drawing order and adds only C's `Tm` before `12 cm.`. So B/D is one
  equivalent operator pair (implicit advance vs. an explicit `Tm` to the same
  origin; the same pattern as pypdf #3951's TJ-vs-Td test), and C/D differ only
  in drawing order. C and D contain the same operation lines in a different order.
  *[Corrected in ERRATUM.md E1: D also splits the final `Tj`; C changes three things.]*

## Observations (pypdf 6.21.4, pdfplumber 0.11.9 / pdfminer.six 20251230)

Exact raw outputs (Python `repr`, `…` elides the unchanged S2/R1/R2 lines):

| | pypdf `extract_text()` (plain) | pypdf `extract_text(extraction_mode="layout")` |
|---|---|---|
| A | `'If the blue latch is closed, do not move the crate more than 12 cm.\nThe green lamp remains on.\nSpan: 12 cm\nDelay: 7 s'` | same lines, joined by `\n\n` |
| B | byte-identical to A | byte-identical to A |
| C | `'If … more than \nThe green lamp remains on.\n12 cm.\nSpan: 12 cm\nDelay: 7 s'` | `'If … more than` + **24 spaces** + `12 cm.\n\nThe green lamp …'` |
| D | byte-identical to B | `'If … more than` + **36 spaces** + `12 cm.\n\nThe green lamp …'` |

No run produced an exception, warning, log record, stdout or stderr output. All
characters are present in every output. `closed` is never split and `do not` always
has one space. The numbers keep their text order (12, 12, 7) everywhere: the late
suffix moves after S2 but stays ahead of R1.

What changed, per controlled representation:

* **Style boundaries (B vs A).** Neither pypdf output changed. pdfplumber reports
  the same 114 origins, advances and `x1-x0` values (max deviation 0.0). Font names
  change at exactly S1:24–26 (`Courier-Oblique`) and S1:32–34 (`Courier-Bold`).
  One internal effect does exist (see Mechanism), but it is not visible in B's text.
* **Late paint plus explicit `Tm` (C vs B).**
  *[See ERRATUM.md E1: plus a split `Tj`.]*
  * Plain mode follows drawing order. Under the comparator's mechanical rules, S1
    is split across lines 0 and 2. The limit `12 cm` lands on a different line and
    a different period-segment than its negation `not`. The first period-segment
    holds S1's head together with all of S2, and `12 cm.` sits directly above
    `Span: 12 cm`.
  * Layout mode restores declared order and keeps `12 cm.` on S1's line, but
    widens `than`→`12` from 1 to 24 spaces.
* **Explicit `Tm` only (D vs B).** Plain output is unchanged. Layout output widens
  `than`→`12` to 36 spaces. Order and line membership stay as declared.
  *[Corrected in ERRATUM.md E1: not `Tm` only; D also splits the final `Tj`, and the
  two changes are not separated by any fixture.]*
* **Drawing order only (C vs D).** Plain mode differs: C follows stream order, D
  follows declared order. Layout mode puts both in declared order; only the space
  counts differ (24 vs 36).
* **pdfplumber character records (all four).** All 114 glyphs match by
  `(char, matrix e,f)`, with `adv` = 6.0 and the declared fonts. The char-list order
  equals drawing order (so C's list has the suffix after S2). Sorting by the
  geometric rule reproduces declared order in all four. pdfplumber's own text
  output was deliberately not compared.

## Mechanism (pinned source plus pypdf's own layout debug files)

* **Plain mode** emits text in content-stream order and inserts `\n` when the
  baseline moves by more than `0.8 × min(string height, font size)` (scaled;
  `crlf_space_check`; here 8 pt against a 24 pt move). In C, the
  `Tm` back up to y=720 is therefore a line break, not a reordering.
* **Layout mode does not advance `tx` across consecutive `Tj` operators.** The
  `Tj` branch of `recurse_to_target_op` stores `text_state_params(...)` (the
  current matrix) and never adds that `Tj`'s displacement. The TJ branch does,
  through `add_trm`, and `Tf` (`set_font`) does not touch the matrix. pypdf's
  `tjs.json` shows runs r1–r4 of line 1 recorded at `tx=72.0`, where the declared
  origins are 216, 234, 264 and 282. Upstream `main` at `08065a0c` has the same
  `Tj` branch.
* **Consequences:**
  * B: the text is still correct, because the fragments concatenate in stream order.
  * D: the `Tm` to x=438 is measured from the stale 228, so `round(210/6)` = 35
    spaces (the #3992 rounding; the #4128 scale factor is 1 here) plus the
    trailing space gives 36.
  * C: the suffix forms its own group. The distorted group widths give
    `char_width` = 618/142.5 = 4.337, so the suffix maps to column 84 against a
    61-character prefix: 23 spaces plus the trailing space gives 24.
* **Derived, not observed:** with advancing `tx`, D would give 1 space. C would
  still give 16, because of layout mode's default `layout_mode_scale_weight=1.25`
  column mapping.

Neither #3951 (Tc is 0 here), #4128 (no `Tm` scaling), #3992 (behaves as written)
nor #3790 (limits not reached) is re-proposed. No upstream issue or PR describing
the `Tj` behaviour was found (keyword search only). Nothing was filed, and no
repair is proposed.

## What remains undecidable

* From text alone, the second `12 cm` in C plain output has no identity. Tokens
  are mapped to declared IDs only by sequence alignment (to drawing order there).
  Only the manifest, or geometry under a rule, says it belongs to S1 and not to
  `Span:`. These PDFs carry no structure tree or marked content.
  *[Corrected in ERRATUM.md E2: the S1 limit is the first `12 cm` (line 2); the
  second is `Span: 12 cm`.]*
* Geometric order equals declared order **by construction** in this family. This
  is no evidence that geometry gives semantic order in general: columns, captions,
  floats and rotated text are untested. No general PDF reading-order guarantee is
  claimed.
* In B and D, font and run boundaries coincide, so whether a run boundary without
  any font change shows the same layout-mode `tx` effect is shown only by source
  reading, not by a fixture. Testing it would need an all-Courier multi-run
  control, which was not added because of the one-pair limit.
  *[Corrected in ERRATUM.md E3: D ops 11→13 are a same-font boundary, but with a `Tm`.]*
* Whether pypdf maintainers regard the layout-mode `Tj` behaviour as a defect or
  as an accepted approximation is unknown.
* Fonts are non-embedded standard-14 fonts. Extraction depends only on the
  declared `/Widths`, and rendering was not tested.
* pypdf's debug `value` field shows even-length strings as CJK code points (debug
  serialisation only; the extracted `text` is correct). Not analysed.
* The fixtures are not derived from, and are not attributable to, any real
  document. They support no production adoption.
* Results are for Linux x86_64 with CPython 3.13.18 and glibc 2.39. macOS arm64
  has not been run; see README.md for the offline qualification commands.

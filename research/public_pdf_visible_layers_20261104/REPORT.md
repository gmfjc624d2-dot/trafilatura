# Report: visible table value vs. an incorrect invisible text layer

Request `public-pdf-visible-table-and-text-layer-20261104-01`.

* **Platform:** Linux x86_64, CPython 3.13.18, glibc 2.39.
* **Tools:**
  * PDFium 156.0.8076.0 via pypdfium2 5.14.0;
  * Poppler 24.02.0 (Ubuntu package 24.02.0-1ubuntu9.11);
  * pypdf 6.21.4;
  * pdfplumber 0.11.9 / pdfminer.six 20251230.
* **Inputs:** five generated, fictional one-page PDFs (`fixtures/`). Nothing was
  scanned and nothing comes from a real document.
* **Evidence:** cited results are from the actual tool run `runs/run2_linux_x86_64/`.
  Predictions were pre-registered in `PREDICTIONS.md` (commit `77410ab1`) before
  any fixture existed. `runs/run1_linux_x86_64/` is an earlier run with a runner
  bug; it is kept as is (see its `RUN.txt`).

## Answer

**No.** In this controlled family, the presence and geometry of extractable text
do not distinguish the visibly printed value from an incorrect invisible text
layer. Only the image evidence shows the printed value.

* **Presence.** All six text extractions return C's hidden `17 mm` as ordinary
  text, and none filters `3 Tr` by default. They are pypdf plain and layout,
  pdfplumber, the PDFium text page, and `pdftotext` plain and `-layout`. They
  return nothing for the image-only page B. Fixture C (wrong hidden value) and D
  (correct hidden value) look the same to all of them, apart from the string itself.
* **Geometry** puts the wrong `7` over the visible `2`. pdfplumber's character
  records and PDFium's loose boxes and origins are identical between C and D.
* **The one geometric difference is PDFium's *tight* glyph box.** Its top edge is
  698.07 pt for the hidden `7` and 698.22 pt for the hidden `2`. This reflects
  the shape of the hidden glyph, not anything visible on the page.
* **Render mode flags invisibility, not correctness.** PDFium reports mode 3
  (invisible) for the text objects of C and D, and pypdf shows `3 Tr` in both
  streams. That flags C and D *equally*. pdfplumber's character records carry no
  render-mode field at all (`supplement_pdfplumber_char_keys.txt`).
* **The image evidence shows the visible value.**
  * B, C and D render pixel-identically in both renderers.
  * In PDFium, the image rectangle equals the authored raster exactly.
  * Exact template matching of the *authored* glyph grid recovers `12 mm` from
    the actual render of C.
  * Checked against that visible truth by cell, the text layer of C mismatches
    exactly one cell (`r1c1`: `17 mm` vs `12 mm`) and D mismatches none. This
    held in pdfplumber, PDFium and Poppler.

Text presence or absence is not evidence of scanning. B has no text and was never
scanned. C has the structure of an OCR'd scan (image plus invisible text) and is
entirely synthetic.

## Predictions vs. the actual tool run

| ID | prediction | observed in run2 | status |
|---|---|---|---|
| P1 | PDFium render(B) == render(C) | identical | pass |
| P2 | PDFium render(B) == render(D) | identical | pass |
| P3 | render(E) != render(B), diffs only in text cells | PDFium 1326 px; Poppler 2026 px; 0 outside cells (+1 pt) | pass |
| P4 | PDFium image rectangle == authored raster, rest white | B, C, D: 0 mismatches inside, 0 non-white outside | pass |
| P5 | Poppler satisfies P1–P4 | P1–P3 hold; **P4 fails**: 3423 smoothed pixels inside, 369 non-white just outside (e.g. column x=384) | fail (partial) |
| P6 | PDFium vs Poppler render(B), no prediction | differ in 3792 px, all within bbox [144,144,385,273] px | observed |
| P7 | render(A) != render(B) | PDFium 2976 px, Poppler 5105 px differ | pass |
| P8 | no text for B; authored strings for A | all six extractions | pass |
| P9 | hidden text returned for C/D, incl. `17 mm` | all six extractions | pass |
| P10 | mode INVISIBLE for C, D; FILL for A, E; `3 Tr` only in C, D | as predicted | pass |
| P11 | boxes for the wrong `7` cover ≥ 95 % of the visible `2` ink | pdfplumber 1.000, PDFium loose 1.000, **PDFium tight 0.659**, **Poppler word box 0.848** | fail |
| P12 | C and D geometry identical except one character | pdfplumber: yes; **PDFium: tight `box` differs** (loose box, origin, mode, size equal) | fail (PDFium) |
| P13 | template decode of the actual render of C == visible truth | PDFium: all 8 cells; **Poppler: every glyph `?`** (830 ambiguous blocks) | pass / fail |
| P14 | C mismatches only the Gap value; D none | pdfplumber, PDFium, Poppler: exactly `r1c1` for C, none for D or A | pass |
| P15 | presence/geometry/mode do not separate C from D; only pixels do | mechanical status **fail**, because it depends on P12-PDFium; see below | fail (derived) |

**Wrong predictions.** Four predictions were wrong as written:
* P5: Poppler does not reproduce a 1-bit image 1:1 at this scale.
* P11: tight and word boxes clip the visible glyph.
* P12: PDFium's tight box depends on the hidden glyph.
* P13 under Poppler: a consequence of P5, because exact matching needs exact
  pixels.

None was relaxed after the fact. The P15 conclusion still holds for visibility:
the only geometric difference between C and D encodes the hidden string's own
glyph, and gives no access to what is printed.

## What this does not show

* **Recovering visible truth here needs the author's font and grid.** It is
  exact template matching, not OCR, and it fails on Poppler's smoothed render.
  A real document needs OCR or a human reader, with their own errors. No OCR or
  external dataset was used.
* **Only one hiding method was tested** (`3 Tr`). Others were not: white fill,
  clipping, text covered by an image, off-page or tiny text.
* **Renderer and font coverage is narrow.** There is one version of each
  renderer, on Linux only. Courier is not embedded, so the pixels of A and E
  depend on each renderer's substitute font. Results on other platforms or
  versions are not implied.
* **pdfplumber's text output was used only for presence.** Its character records
  were used for geometry.

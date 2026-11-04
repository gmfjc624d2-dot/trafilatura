# Plan and pre-registered predictions

Request `public-pdf-visible-table-and-text-layer-20261104-01`. Written on 2026-11-04,
**before** any fixture was generated or any tool was run on it. The predictions are
expectations, not results. Results live in `runs/` and are compared against these
IDs in `REPORT.md`. A prediction that turns out wrong stays here unchanged.

## Question

Can the presence and geometry of extractable PDF text distinguish a visibly printed
table value from an incorrect invisible text layer?

## Fixtures (all fictional, generated, one page of 612 x 792 pt)

The same two-column table appears on every page, with units:

| Item | Value |
|---|---|
| Gap | 12 mm |
| Delay | 7 s |
| Load | 18 kg |

* **A, born-digital:** vector rules and visible Courier 10 pt text (`0 Tr`).
* **B, image-only:** one 1-bit raster of the table, drawn with a bitmap font
  authored for this experiment, placed at 2 px/pt. There is no text object.
* **C, raster plus hidden text:** B's raster, plus a Courier 10 pt text layer with
  `3 Tr` (invisible) over each cell. The Gap value is deliberately **WRONG**: the
  text layer says `17 mm` over the visible `12 mm`.
* **D, control:** like C, but every hidden string is correct (`12 mm`).
* **E, render-sensitivity control:** like C, but the same text layer uses `0 Tr`
  (visible). This shows that the pixel comparison can see text.

Visible truth is the authored raster: its cell strings, glyph grid and pixels are
recorded at generation time. The PDFs are written byte by byte, with the image
uncompressed, so their bytes do not depend on zlib.

## Planned tool runs (Linux x86_64, pinned)

* **Render:** PDFium 156.0.8076.0 via pypdfium2 5.14.0 at scale 2 (144 dpi), and
  Poppler 24.02.0 `pdftoppm -r 144`. Renders are compared as raw pixel buffers and
  saved losslessly.
* **Text:** pypdf 6.21.4 plain and layout; pdfplumber 0.11.9 / pdfminer.six
  20251230 characters with boxes; the PDFium text page (characters, boxes,
  origins) and per-object text render mode; Poppler `pdftotext` (plain, `-layout`,
  `-bbox-layout`).

## Predictions

| ID | prediction |
|---|---|
| P1 | PDFium: render(B) == render(C) pixel-for-pixel |
| P2 | PDFium: render(B) == render(D) |
| P3 | PDFium: render(E) != render(B); every differing pixel lies within the text cells' boxes (padded by 1 pt) |
| P4 | PDFium: render(B) inside the image rectangle equals the authored raster exactly (1:1 mapping); the page outside it is white |
| P5 | Poppler: P1–P4 hold as well |
| P6 | PDFium vs Poppler render(B): no directional prediction (unknown) |
| P7 | render(A) != render(B), because the vector Courier glyphs differ from the bitmap font |
| P8 | Every text extractor returns no text for B, and the authored strings for A |
| P9 | Every text extractor returns the invisible text of C and D, including `17 mm` for C; none filters `3 Tr` by default |
| P10 | PDFium per-object render mode: INVISIBLE for C and D, FILL for A and E; `3 Tr` appears in the content streams of C and D only |
| P11 | Geometry: in C, the boxes reported for the wrong `7` cover at least 95 % of the visible `2` glyph's ink |
| P12 | C and D have identical extracted character geometry (same count, boxes and render mode); only one character differs (`7` vs `2`) |
| P13 | Exact template matching against the authored bitmap font, applied to the actual render of C (not to the authored raster), recovers the visible truth `12 mm` and every other cell |
| P14 | Text layer vs visible truth: C has exactly one mismatching cell (Gap value), D has none |
| P15 | Therefore presence and geometry of extractable text do **not** distinguish C from D. Render mode flags invisibility in both. Only the image evidence (pixels) shows the visible value. |

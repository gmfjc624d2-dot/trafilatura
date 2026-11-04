# public_pdf_visible_layers_20261104

A controlled document-extraction experiment for request
`public-pdf-visible-table-and-text-layer-20261104-01`. It asks whether the presence
and geometry of extractable PDF text can distinguish a visibly printed table value
from an incorrect invisible text layer. Findings are in **[REPORT.md](REPORT.md)**;
the pre-registered predictions are in [PREDICTIONS.md](PREDICTIONS.md).

This is a standalone research directory in a fork of Trafilatura. It does not
change Trafilatura's product, is not imported by the package, and is not collected
by the repository's test suite: `pytest.ini` and `ruff.toml` here are local. The
data is newly authored and fictional, and nothing was scanned.

## Layout

| path | content |
|---|---|
| `generate_fixtures.py` | stdlib-only, byte-level generator: authored 5x9 bitmap font, 1-bit raster, fixtures A–E, manifest |
| `fixtures/` | five one-page PDFs (1.4–5.3 KB), `raster/table.pbm` (the authored raster, uncompressed), `content_streams/`, `manifest.json` (visible truth: cells, glyph boxes, font, rules; per-fixture operations and hashes) |
| `layer_compare.py` | pure comparisons: lossless pixel diff, raster-region check, exact template decoding, ink coverage, cell assignment |
| `run_tools.py` | the actual tool run: PDFium and Poppler renders, plus pypdf, pdfplumber, PDFium and pdftotext text and characters; records checks against P1–P15 |
| `tests/test_visible_layers.py` | fixture invariants from an independent re-parse of the PDF bytes, helper behaviour on synthetic inputs, integrity of preserved renders; no extractor-output approval |
| `runs/run1_linux_x86_64/` | first actual run, kept unchanged; it has a runner bug that leaves 3 checks `not_run` |
| `runs/run2_linux_x86_64/` | the cited actual run: `checks.json`, `tool_runs.json` (status, warnings, logs, stderr, CLI argv), `render_index.json`, `renders/*.png` (lossless), `raw/` (exact outputs), `environment.json`, process stdout/stderr, `RUN.txt`, one supplementary command |
| `requirements-lock.txt` | hash-locked Python pins, copied unchanged from `../public_pdf_order_20261103/` |
| `SHA256SUMS` | sha256 of every tracked file in this directory except itself |

Fixtures:
* **A**: born-digital; vector rules and visible Courier text.
* **B**: image-only; the raster, with no text object.
* **C**: the raster plus a `3 Tr` text layer whose Gap value is WRONG (`17 mm`
  over the visible `12 mm`).
* **D**: control; the raster plus a correct `3 Tr` layer.
* **E**: render-sensitivity control; C's layer drawn visibly (`0 Tr`).

## Environment and licenses

The actual runs used Linux x86_64 and CPython 3.13.18 in a venv installed from
`requirements-lock.txt` with `--require-hashes`. The tools were:
* pypdf 6.21.4 (BSD-3-Clause);
* pdfplumber 0.11.9 (MIT) with pdfminer.six 20251230 (MIT);
* pypdfium2 5.14.0 (BSD-3-Clause / Apache-2.0), bundling PDFium 156.0.8076.0
  (BSD-3-Clause and dependency licenses);
* Pillow 13.0.0 (MIT-CMU), used only to write and verify PNGs;
* Poppler `pdftoppm`/`pdftotext` 24.02.0, from the system package
  `poppler-utils` 24.02.0-1ubuntu9.11 (GPL-2/GPL-3). It is invoked as an external
  program and is neither distributed nor vendored here; it is not hash-locked.

Versions are checked by the runner, and a tool that is missing or off-pin is
recorded as `not_run`, never silently replaced. This directory's own files,
including the bitmap font, fall under the repository's Apache-2.0 `LICENSE`.

## Local replay

From this directory, regenerate and verify the fixtures (stdlib only):

```bash
python3 -I generate_fixtures.py --check
```

Create a pinned venv (CPython 3.13), and install Poppler 24.02.0 for the Poppler
checks:

```bash
python3.13 -m venv /tmp/visible-layers-venv && /tmp/visible-layers-venv/bin/python -m pip install --require-hashes --no-deps -r requirements-lock.txt
```

```bash
/tmp/visible-layers-venv/bin/python -I -m pytest -q
```

```bash
/tmp/visible-layers-venv/bin/python -I run_tools.py --out runs/replay_local
```

```bash
diff <(python3 -c "import json;print(json.dumps([[c['check_id'],c['status']] for c in json.load(open('runs/run2_linux_x86_64/checks.json'))['checks']],indent=0))") <(python3 -c "import json;print(json.dumps([[c['check_id'],c['status']] for c in json.load(open('runs/replay_local/checks.json'))['checks']],indent=0))")
```

On Linux with the same versions, run2's pixel hashes are expected to recur; run1
and run2 matched each other. On another platform or another Poppler or PDFium
version, record the replay as its own run and do not overwrite run2. A missing
tool shows up as `not_run`, with the missing condition in `checks.json` and
`tool_runs.json`.

Verify the artifacts:

```bash
sha256sum -c SHA256SUMS
```

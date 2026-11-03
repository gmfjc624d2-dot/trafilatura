# public_pdf_order_20261103

Public document-extraction research fixture family for request
`public-styled-prose-fixture-20261103-01`. This is a standalone research directory
in a fork of Trafilatura. It does **not** change Trafilatura's extractor, is not
imported by the `trafilatura` package, and is not collected by the repository's
test suite (`pytest.ini` and `ruff.toml` here are local to this directory).

Findings are in **[REPORT.md](REPORT.md)**.

All text is fictional and was written for these fixtures. The PDFs are not derived
from, and are not attributable to, any real document.

## Layout

| path | content |
|---|---|
| `generate_fixtures.py` | deterministic byte-level PDF writer (no PDF library) and manifest builder |
| `fixtures/*.pdf` | A, B, C (initial controls) and D (added after run1), one page each, about 2.4 KB |
| `fixtures/manifest.json` | declared structure (blocks, tokens, clauses, measurements, characters, expected origins/advances), fonts, and per fixture: content stream, operation index with byte offsets, runs, glyphs (draw_seq, char_id, run, op_index, font, origin, advance), drawing/geometric/declared order, perturbations |
| `fixtures/content_streams/*.txt` | the exact uncompressed content streams |
| `order_compare.py` | comparison of extractor records with the manifest; pure functions, no normalisation |
| `run_extractors.py` | runs pinned pypdf plain/layout (plus auxiliary visitor and layout-debug records) and pdfplumber chars; refuses other versions |
| `tests/test_fixture_family.py` | generator/manifest consistency, independent re-derivation of glyph origins from the PDF bytes, comparator behaviour on synthetic strings, hash integrity of preserved runs; no extractor-output approval |
| `runs/run1_ABC/` | first pinned run, A/B/C only, unchanged |
| `runs/run2_ABCD/` | run after adding D |
| `runs/run3_final_ABCD/` | final run (final code, offline hash-locked install); the report cites this one |
| `requirements-lock.txt` | exact pins with sha256 for the Linux x86_64 wheels used and the macOS arm64 wheels on PyPI (CPython 3.13) |
| `provenance.json` | upstream source revisions, reused pypdf PRs, installed-vs-tag checks, wheel files and hashes, licenses |
| `SHA256SUMS` | sha256 of every tracked file in this directory except itself |

Each `runs/<name>/` holds `raw/` with the exact extractor outputs (text files are
the returned `str` as UTF-8, with no trailing newline added),
`extraction_runs.json` (status, exceptions, Python warnings, WARNING+ log records,
captured stdout/stderr, raw-file sha256), `comparison.json`, `environment.json`,
the process `run_stdout.txt`/`run_stderr.txt`, and `RUN.txt`.

## Licensing

Files in this directory are part of this repository and fall under its Apache-2.0
`LICENSE`, which is unchanged. No third-party code is vendored. pypdf
(BSD-3-Clause), pdfplumber (MIT), pdfminer.six (MIT) and the other dependencies
are installed separately; their versions, source revisions and license-file hashes
are recorded in `provenance.json` and `runs/*/environment.json`. The fixtures use
the non-embedded standard-14 Courier fonts by name only, and no font program is
included.

## Reproduce (Linux, as run)

The generator needs only the Python standard library:

```bash
cd research/public_pdf_order_20261103
```

```bash
python3 generate_fixtures.py --check
```

Pinned environment (CPython 3.13). The online install:

```bash
python3.13 -m venv /tmp/pdf-order-venv
```

```bash
/tmp/pdf-order-venv/bin/python -m pip install --require-hashes --no-deps -r requirements-lock.txt
```

```bash
/tmp/pdf-order-venv/bin/python -I -m pytest -q
```

```bash
/tmp/pdf-order-venv/bin/python -I run_extractors.py --out runs/local_check
```

```bash
diff -r runs/run3_final_ABCD/raw runs/local_check/raw && cmp runs/run3_final_ABCD/comparison.json runs/local_check/comparison.json
```

Results on the recording machine (Linux x86_64, CPython 3.13.18, glibc 2.39):
`--check` reported 9 files and 0 mismatches, and pytest reported 22 passed (one
hash-integrity case per run directory). The runner exited 0 with empty stderr, and
its raw outputs, `comparison.json` and `extraction_runs.json` were byte-identical
to `runs/run3_final_ABCD`. This held for both the online install and an offline
`--no-index` install from the same hashed wheels.

The Linux hash for `cryptography` is that of its `manylinux_2_34` wheel, so the
lock needs glibc 2.34 or later. On an older glibc, pip picks a different wheel and
`--require-hashes` rejects it; that is the intended behaviour, not a reason to drop
the hashes.

## Native macOS arm64 qualification (offline, not yet performed)

A Linux pass says nothing about macOS. Run these steps natively on Apple silicon,
not under Rosetta, and keep the results as a separate run directory. Never
overwrite the Linux runs; any difference is a finding to record, not to normalise.

1. On any machine with network access, fetch the hash-checked macOS arm64 CPython
   3.13 wheels (this exact command was tested; it downloads 14 wheels):

```bash
python3 -m pip download --no-deps --only-binary=:all: --platform macosx_14_0_arm64 --platform macosx_11_0_arm64 --python-version 3.13 --implementation cp --require-hashes -r research/public_pdf_order_20261103/requirements-lock.txt -d wheels-macos-arm64
```

2. Copy `wheels-macos-arm64/` and a checkout of branch
   `claude/tender-einstein-ma1hhg` to the Mac. Then, offline, from the repository root:

```bash
python3.13 -c "import platform, sys; print(platform.machine(), platform.mac_ver()[0], sys.version)"
```

The first field must be `arm64`. `pypdfium2` 5.14.0's arm64 wheel requires macOS 13 or later.

```bash
python3.13 -m venv /tmp/pdf-order-venv
```

```bash
/tmp/pdf-order-venv/bin/python -m pip install --no-index --find-links wheels-macos-arm64 --require-hashes --no-deps -r research/public_pdf_order_20261103/requirements-lock.txt
```

```bash
cd research/public_pdf_order_20261103 && shasum -a 256 -c SHA256SUMS
```

```bash
/tmp/pdf-order-venv/bin/python -I generate_fixtures.py --check
```

```bash
/tmp/pdf-order-venv/bin/python -I -m pytest -q
```

```bash
/tmp/pdf-order-venv/bin/python -I run_extractors.py --out runs/macos_arm64_native > runs/macos_arm64_native.stdout 2> runs/macos_arm64_native.stderr
```

```bash
diff -r runs/run3_final_ABCD/raw runs/macos_arm64_native/raw; cmp runs/run3_final_ABCD/comparison.json runs/macos_arm64_native/comparison.json; cmp runs/run3_final_ABCD/extraction_runs.json runs/macos_arm64_native/extraction_runs.json
```

`environment.json` is expected to differ (platform, wheel tags). Commit the macOS
run directory, together with its stdout/stderr, as its own record.

## Verify artifacts

```bash
cd research/public_pdf_order_20261103 && sha256sum -c SHA256SUMS
```

On macOS, use `shasum -a 256 -c SHA256SUMS`.

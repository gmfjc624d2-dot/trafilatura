# Controlled run: label swap in a held layout debug trace

Request `public-pdf-order-erratum-20261104-01`, executed 2026-11-04 (UTC) by the
Claude Code session that wrote this research directory. This run is new. No
receipt exists for run1, run2 or run3, and none has been created or backdated
for them.

## Command (from `research/public_pdf_order_20261103`)

```bash
python3 -I -c 'import sys;p=sys.argv[1];b=open(p,"rb").read();sys.argv=sys.argv[1:];exec(compile(b,p,"exec"),{"__name__":"__main__","__file__":p,"__builtins__":__builtins__,"RUNNER_BUFFER":b})' erratum_label_swap.py --out runs/erratum_20261104_label_swap
```

The interpreter was `/usr/local/bin/python3`, CPython 3.13.18, on Linux x86_64.
Only the standard library is used, and pypdf/pdfplumber were not run. The exit
status was 0, stdout is in `run_stdout.txt`, and stderr (`run_stderr.txt`) was
empty. `prerun_external.txt` holds the git head (`d77a5bd1…`), the working-tree
status and separate `sha256sum` reads, all recorded by the shell before the run.

## Files

| file | content |
|---|---|
| `receipt_STARTED.json` | written and fsynced before evaluation. It records the interpreter, `sys.orig_argv`, the runner buffer, the comparator buffer with the selected function `compare_layout_tjs` (lines 225–260, segment sha256), the transform `swap_text_labels` (lines 75–80), the inputs with sizes, sha256 and git blob ids, the planned calls, and the modules loaded so far |
| `receipt_RESULT.json` | links to STARTED by `receipt_id` and the exact `sha256` of the STARTED bytes. It holds the outcome, the summary, the full raw comparator results for original and variant, and diagnostics (exception slot, warnings, modules imported during evaluation, re-hash of the retained buffers) |
| `inputs/D.tjs.original.json` | byte-identical to `runs/run3_final_ABCD/raw/D.pypdf_layout_debug.dir/tjs.json` (sha256 `466edb43…`, 4245 bytes) |
| `inputs/D.tjs.variant_labels_r4_r5_swapped.json` | records 4 and 5 exchange `value`, `text` and `_raw_chars`; all other fields stay in place (sha256 `adbe8f98…`, 4245 bytes) |

Key hashes: runner `c4fe692100533e8e7d1a99a627e863c83bfa2cf2ee6f1801b4688801a8c560ca`;
`order_compare.py` `c3ff4e5a343f84fc252308f5daa6745f51841b8672e48a7b4297d7bc3b462be1`,
which is unchanged since `d77a5bd`; STARTED
`8eb325d7a5c2baa8d396621c9c5538dece3a25c710532971beded68f00fed821`; RESULT
`02d68ffd8d7de57f0f5942642a6d380dce8fd50c9b9dc67677321df9e2fbdaf2`.

## Result

| field | original | variant |
|---|---|---|
| `counts_match` | `true` | `true` |
| `runs_with_tx_mismatch` | `D.r1–D.r4` | `D.r1–D.r4` |
| `rows[D.r4].text_matches_run` / `tx_matches` | `true` / `false` | **`false`** / `false` |
| `rows[D.r5].text_matches_run` / `tx_matches` | `true` / `true` | **`false`** / `true` |
| all other rows | unchanged | unchanged |

The only result fields that differ are `rows[4].text_matches_run` and
`rows[5].text_matches_run`. Evaluating the original reproduces the `tj_positions`
recorded in `runs/run3_final_ABCD/comparison.json` exactly. For the interpretation,
see `ERRATUM.md`, section "Bounded run".

## What this establishes about this controlled execution

* The process that wrote both receipts (same `process_nonce`) executed the runner
  bytes it hashed: the bootstrap passes in the buffer it read and executes that
  same object. Its recorded `sys.orig_argv` contains the documented bootstrap
  string.
* Each controlled input was opened once. The comparator was compiled from the
  retained source buffer (not imported from the file), and both evaluations used
  the retained trace and manifest buffers. The variant was evaluated from its
  retained serialised bytes, the same bytes that were preserved. All buffers
  re-hashed identically after evaluation.
* In program order, STARTED was written and fsynced before the evaluation call,
  and RESULT names STARTED's id and exact sha256.
* The variant differs from the original only in the six label fields. The
  serialiser `json.dumps(records, indent=2)` reproduces the original bytes exactly.
* The recorded hashes match the shell's separate pre-run `sha256sum` reads and the
  published `SHA256SUMS`.

## What remains unobserved

* **Self-attestation:** the timestamps, the ordering and the nonce are written by
  the same process and have no external witness. The git commit is later than the
  run and proves only what was committed.
* **Interpreter startup:** the bytes of the `python3` binary, its standard library
  and the `site` initialisation (`-I` does not disable `site`) were not hashed. The
  `-c` bootstrap was parsed by the interpreter before any receipt code ran, and is
  only recorded, after the fact, through `sys.orig_argv`.
* **Imports:** only module *names* are recorded, and their files were not hashed
  or otherwise observed. 101 names were loaded when `main()` began; despite its
  name, STARTED's `modules_loaded_before_evaluation` is that start-of-`main()`
  snapshot. `difflib`, `heapq` and `_heapq` were imported during evaluation,
  measured against a set taken immediately before it.
* **Older runs:** run1–run3 have no receipts. Their provenance rests on the
  committed files, the recorded hashes and the commit history. This run did not
  re-execute pypdf or pdfplumber and says nothing new about extractor behaviour.
* **Durability:** fsync semantics of the container filesystem and the clock source
  were not examined.

## Verify

```bash
cd research/public_pdf_order_20261103/runs/erratum_20261104_label_swap && sha256sum receipt_STARTED.json receipt_RESULT.json inputs/* ../../erratum_label_swap.py ../../order_compare.py
```

Compare the printed values with `links.started_receipt_sha256` in the RESULT
receipt and with the `sha256` fields in the STARTED receipt.

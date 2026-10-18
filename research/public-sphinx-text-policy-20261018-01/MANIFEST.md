# Manifest: public-sphinx-text-policy-20261018-01

| | |
|---|---|
| request | `public-sphinx-text-policy-20261018-01` |
| fork / branch | `https://github.com/gmfjc624d2-dot/trafilatura`, `claude/adoring-turing-3ekxhe` (no PR, no upstream issue, no force push) |
| predecessor | `9ab18de157ce4ee33ecadea2b663b211a2560f63` (local = remote at start; earlier research read-only and unchanged) |
| pre-registration | `db51165b856fca0de277d218aac0cc5e8e6b7d14`; witness on the unchanged predecessor `a5b6a4dfc46bb06aafb3fb65ce84864590649359`; design addendum `0a38ec13e2f5691ec860e163b949ec4c080e726d`; code before its run `c38a2a22310eac751d398e3abd02dc507dc39fe3` |
| results commit | the commit adding this file: `git log -1 --format=%H -- research/public-sphinx-text-policy-20261018-01/MANIFEST.md` |
| platform | Linux only: Python 3.12.3, lxml 6.1.3, libxml2 2.14.6, html5lib 1.1, six 1.17.0, webencodings 0.5.1 (zipimport) |

## Files

| path | role |
|---|---|
| `REPORT.md` | the changes, the witness, scope, results, every failure, limits, identities, licenses, Linux and macOS commands |
| `scripts/text_policy.py` | the successor module: the pinned predecessor run from verified bytes, `oracle_text()`, mutants, itertext observation, text ledger, three axes; CLI for one source/anchor |
| `scripts/replay.py` | the single replay entrypoint: pin checks, the 8 regression cases + W1, grading, mutation controls, unchanged-field projection, `--against` |
| `scripts/test_text_policy.py` | 11 focused tests of the changed surface (1 kept failure) |
| `scripts/build_witness.py` | builds and checks the one new fixture; prints its expected text identity |
| `scripts/witness_predecessor.py` | runs the unchanged predecessor `report()` on W1 and its historical R9 |
| `fixtures/w1_long_clean.html` | the one new fixture (clean long unit); the other eight are referenced by path and sha256 |
| `fixtures/expectations.json` | pre-registered changes, scope, text rule, mutation controls, corrected R9, witness and regression predictions, changed/unchanged fields, pins |
| `results/witness-predecessor-linux-py3.12/W1.json` | the predecessor report on W1 and `historical_R9` |
| `results/run1-linux-py3.12/` | `reports/<case>.json` (N1-N5, C17, C1, C2, W1), `summary.json`, `summary.md` |
| `logs/` | exact commands with `exit=` lines; post-hoc logs marked as such |
| `.gitignore`, `.gitattributes`, `ruff.toml` | the only ignore/attribute/lint rules of this experiment (inside this prefix) |
| `PREREGISTERED.sha256`, `SHA256SUMS` | hashes of the 7 pre-registration files (`db51165`) and of every tracked file here except SHA256SUMS |

## Referenced, read-only (pinned in `fixtures/expectations.json`)

| what | path |
|---|---|
| predecessor module, replay, expectations, wheel verifier | `research/public-sphinx-parser-corroboration-20261018-01/scripts/`, `fixtures/expectations.json` |
| retained wheels, lock, manifest, licenses | `research/public-sphinx-parser-corroboration-20261018-01/wheels/` |
| helper | `research/public-sphinx-evidence-integrity-20261018-01/scripts/anchor_unit.py` |
| comparator | `research/public-json-numeric-integrity-20261018-01/scripts/compare_results.py` |
| fixtures N1-N5, C17, C1, C2 | `research/public-sphinx-evidence-integrity-20261018-01/fixtures/n1..n5_*.html`, `research/public-sphinx-anchor-units-20261018-01/fixtures/f4_duplicates.html`, `research/public-sphinx-parser-corroboration-20261018-01/fixtures/c1_reparent_dd.html`, `c2_text_tail.html` |
| committed predecessor results | `research/public-sphinx-parser-corroboration-20261018-01/results/run1-linux-py3.12/` |

## Logs

| log | exit | meaning |
|---|---|---|
| `logs/01_build_witness.log` | 0 | W1 built and checked; expected text 2276 bytes |
| `logs/10_witness_predecessor.log` | 0 | unchanged predecessor on W1: STRUCTURE_CORROBORATED with helper REVIEW_OVER_BUDGET; historical R9 False |
| `logs/15_design_addendum.md` | - | implementation choices, before the code existed |
| `logs/20_replay_run1.log` | 0 | 186 pass, 0 fail, 87 recorded; 33 pins, 0 differ; dependencies from the pinned wheels |
| `logs/21_unittest_run1.log` | 1 | 11 tests: 10 ok, 1 FAIL (kept: wrong test assumption about C2's final tail) |
| `logs/22_posthoc_c2_final_tail.log` | 0 | post-hoc, read-only: where `MARK-TAIL-TAIL` sits in C2 |
| `logs/23_posthoc_c1_errors.log` | 0 | post-hoc, read-only: C1 html5lib errors equal the corrected expectation |

Verify: `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS), from this directory.

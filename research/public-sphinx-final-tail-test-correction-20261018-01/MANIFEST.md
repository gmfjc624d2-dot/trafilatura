# Manifest: public-sphinx-final-tail-test-correction-20261018-01

| | |
|---|---|
| request | `public-sphinx-final-tail-test-correction-20261018-01` |
| fork / branch | `https://github.com/gmfjc624d2-dot/trafilatura`, `claude/adoring-turing-3ekxhe` (no PR, no upstream issue, no force push) |
| source commit | `d8126f57ceb34a3d455a04881b606d2d86220fd7` (local = remote, clean, no divergence: `logs/00_recovery.log`) |
| pre-execution commit | `bee65a09d9abda644c0caee69c8fb5ba38767b6f` (baseline, correction, patch, rationale, prediction, pins, entry point; before any run) |
| results commit | the commit adding this file: `git log -1 --format=%H -- research/public-sphinx-final-tail-test-correction-20261018-01/MANIFEST.md` |
| evidence | Linux x86_64 only (Python 3.12.3, lxml 6.1.3, libxml2 2.14.6); not macOS qualification |

## Files

| path | role |
|---|---|
| `CORRECTION.md` | written before execution: why the old expectation was wrong, the exact diff, what is unchanged, the prediction |
| `RESULT.md` | the outcome, the evidence scope, the macOS recovery/replay/comparison commands and criteria |
| `baseline/test_text_policy.py` | byte-identical copy of `research/public-sphinx-text-policy-20261018-01/scripts/test_text_policy.py` at `d8126f5` (blob `3b11bc20…`, sha256 `deaf6ffa…7100`, introduced in `c38a2a2`) |
| `corrected/test_text_policy.py` | the same file with only the one assertion corrected (sha256 `fc722920…1fca`) |
| `patch/test_text_policy.diff` | the minimal unified diff, baseline → corrected (sha256 `597f314b…0ee0`; `patch -o` reproduces the corrected copy) |
| `sources.json` | source commit, baseline and corrected identities, sha256 of the 17 earlier public files the suite depends on, and their roles |
| `scripts/run_corrected_suite.py` | the entry point: verifies every pin, loads the earlier `text_policy.py`/`replay.py` and the corrected test from verified bytes, runs unittest, optional JSON record |
| `results/run1-linux-py3.12.json` | execution record: environment, dependency identity, each test's outcome, return code |
| `logs/` | exact commands with `exit=` lines |
| `.gitignore`, `.gitattributes`, `ruff.toml` | this directory's only ignore, attribute and lint rules |
| `SHA256SUMS` | sha256 of every tracked file here except itself |

## Logs

| log | exit | meaning |
|---|---|---|
| `logs/00_recovery.log` | 0 | local/remote both `d8126f5`, 0 commits either way, clean tree; earlier test identity; earlier SHA256SUMS ok |
| `logs/01_corrected_suite_run1.log` | 0 | the single run: 17 pins + copies + patch, 0 differ; 11 tests, 11 ok |
| `logs/02_record_comparator_check.log` | 0 | the pinned json-numeric comparator accepts the record (self-comparison, no suite run) |

Verify: `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS), from this directory.

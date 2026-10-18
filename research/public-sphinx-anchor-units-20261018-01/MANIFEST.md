# Manifest: public-sphinx-anchor-units-20261018-01

| | |
|---|---|
| request | `public-sphinx-anchor-units-20261018-01` |
| fork / branch | `https://github.com/gmfjc624d2-dot/trafilatura`, `claude/adoring-turing-3ekxhe` (no PR, no upstream issue, no force push) |
| continued from | `e7d2f5c4e435b09fa800f8fa14685e4f04dc06c5` (earlier increments unchanged) |
| pre-registration commit | `089f3ccec47675c4bc21414aa47ec63d94b87fda` |
| results commit | the commit adding this file: `git log -1 --format=%H -- research/public-sphinx-anchor-units-20261018-01/MANIFEST.md` |
| fresh-clone check | `logs/20_fresh_clone_check.log`, added by the commit after the results commit, which it checks |
| platform | Linux only: Python 3.12.3, lxml 6.1.3, libxml2 2.14.6, x86_64 |

## Files

| path | role |
|---|---|
| `REPORT.md` | answer, results, representations, parser recovery, limits, provenance, commands, macOS replay |
| `source/numpy-2.5/numpy.where.html`, `LICENSE.txt`, `source/PROVENANCE.md` | published public page (byte for byte), its BSD-3-Clause license, provenance |
| `fixtures/f1..f6_*.html`, `regions.json` | synthetic pages and the raw byte regions of their intended units |
| `fixtures/expectations.json`, `expectations_resolved.json`, `README.md` | pre-registered cases, rules, reasons, hypotheses; byte-level resolution |
| `scripts/build_fixtures.py`, `check_expectations.py` | fixture builder and byte-level checker (pre-registered) |
| `scripts/anchor_unit.py` | the minimal research helper `select_unit()` |
| `scripts/probe_existing_apis.py` | hypotheses H1-H3 about lxml.html and Trafilatura |
| `scripts/run_experiment.py`, `compare_results.py` | grading of the 27 cases; replay comparison |
| `scripts/test_anchor_unit.py` | 15 focused tests and negative controls |
| `results/run1-linux-py3.12/` | `results.json` (all outputs, contexts, diagnostics, checks), `summary.md`, `probe_existing_apis.json` |
| `logs/` | exact commands with `exit=` lines |
| `PREREGISTERED.sha256` | hashes of the pre-registration files as committed in `089f3cc` (still verify) |
| `SHA256SUMS` | sha256 of every git-tracked file of this directory except itself |

## Logs

| log | exit | meaning |
|---|---|---|
| `logs/00_environment.log` | 1, 0 | system Python 3.12 has no lxml (exit 1); versions of the local venv |
| `logs/00_public_hosts_refused.log` | 56 ×5 | numpy.org, docs.python.org, readthedocs, sphinx-doc.org, lxml.de refused (CONNECT 403) |
| `logs/01_public_source_fetch.log` | 0 | pinned refs, blobs, hashes of the public page and license |
| `logs/02_build_check_expectations.log` | 0, 0 | fixtures rebuild identically; 27 cases, 0 problems |
| `logs/10_probe_existing_apis_run1.log` | 0 | H1, H2, H3 confirmed; parser diagnostics per page |
| `logs/11_run_experiment_run1.log` | 1 | 96 checks: 90 pass, 2 failed budget predictions (kept), 4 recorded |
| `logs/12_unittest_run1.log` | 0 | 15 tests OK |

Verify: `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS), from this directory.

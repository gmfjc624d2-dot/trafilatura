# Manifest: public-sphinx-parser-corroboration-20261018-01

| | |
|---|---|
| request | `public-sphinx-parser-corroboration-20261018-01` |
| fork / branch | `https://github.com/gmfjc624d2-dot/trafilatura`, `claude/adoring-turing-3ekxhe` (no PR, no upstream issue, no force push) |
| predecessor | `5c41ba875753666d0b3fb780e14f046f77a7ad01` (local = remote at start; earlier research read-only) |
| pre-registration commit | `6df1d6f6ce07ef1622d9574dfca3a4c76948392c` (before the module existed and before html5lib parsed a fixture) |
| results commit | the commit adding this file: `git log -1 --format=%H -- research/public-sphinx-parser-corroboration-20261018-01/MANIFEST.md` |
| recovery check | `logs/20_fresh_clone_recovery.log`, added by the commit after the results commit, which it checks |
| platform | Linux only: Python 3.12.3, lxml 6.1.3, libxml2 2.14.6, html5lib 1.1, six 1.17.0, webencodings 0.5.1 |

## Files

| path | role |
|---|---|
| `REPORT.md` | provenance, parsing contract, results, every failure, limits, commands, macOS replay |
| `scripts/corroborate.py` | the one module: pinned helper on lxml, html5lib parse, mirrored rule, text rule, comparison, disposition; CLI for one source/anchor |
| `scripts/replay.py` | replay entrypoint: the 8 pre-registered cases, grading, `--against` comparison with the pinned recursive comparator |
| `scripts/test_corroborate.py` | 13 focused tests (2 kept failures) |
| `scripts/verify_wheels.py` | stdlib verification of the retained wheels from their bytes |
| `wheels/*.whl`, `wheels/requirements.lock`, `wheels/WHEELS.json` | the three retained pure-Python wheels, hash lock, manifest (sources, hashes, metadata, choices) |
| `wheels/licenses/` | MIT (html5lib, with AUTHORS.rst), MIT (six), BSD (webencodings, from its v0.5.1 tag) |
| `wheels/registry/pypi_records.json` | trimmed PyPI records of the chosen releases and of webencodings 0.6.0/0.6.1 |
| `fixtures/c1_reparent_dd.html`, `fixtures/c2_text_tail.html` | the two new fixtures; the other six are referenced in earlier research by path and sha256 |
| `fixtures/expectations.json` | pre-registered pins, options, policies, required properties, predictions |
| `results/run1-linux-py3.12/` | `reports/<case>.json` (one per source/anchor), `summary.json`, `summary.md` |
| `logs/` | chronology and exact commands with `exit=` lines |
| `.gitignore` | the only ignore rules of this experiment: re-includes logs and results, ignores caches and environments |
| `PREREGISTERED.sha256`, `SHA256SUMS` | hashes of the pre-registration files (`6df1d6f`) and of every tracked file here except SHA256SUMS |

## Referenced fixtures (read-only, in earlier research)

| case | path | sha256 |
|---|---|---|
| N1-N5 | `research/public-sphinx-evidence-integrity-20261018-01/fixtures/n1..n5_*.html` | in `fixtures/expectations.json` pins |
| C17 | `research/public-sphinx-anchor-units-20261018-01/fixtures/f4_duplicates.html` | `6d1da7f6…3ec3` |

## Logs

| log | exit | meaning |
|---|---|---|
| `logs/00_acquisition_chronology.md` | - | what happened in order, including the unlogged first fetch and the unneeded second download |
| `logs/01_acquisition.log` | 0 | the second (logged) fetch: registry, wheels, digests, license; byte-identical to the first |
| `logs/02_verify_wheels.log` | 0 | 3 wheels, 0 problems |
| `logs/03_environment.log` | 0 | isolated venv (lxml only) + retained wheels via hash-locked pip `--target`, offline |
| `logs/10_replay_run1.log` | 1 | 289 checks: 275 pass, 2 fail (kept), 12 recorded |
| `logs/11_unittest_run1.log` | 1 | 13 tests: 11 OK, 2 FAIL (kept: itertext assumption) |
| `logs/12_posthoc_itertext.log` | 0 | post-hoc: C-accelerated ElementTree itertext yields comment data, pure Python does not |

Verify: `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS), from this directory.

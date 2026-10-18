# Manifest: public-evidence-spans-20261018-01

| | |
|---|---|
| request | `public-evidence-spans-benchmark-20261018-01` |
| fork / branch | `https://github.com/gmfjc624d2-dot/trafilatura`, `claude/adoring-turing-3ekxhe` (no PR, no upstream issue, no force push) |
| branch state recovered | `80c0550254b44554d8734e3ba7d175dd9472ee22` (end of the earlier link-fix increment; its files are unchanged) |
| pre-registration commit | `2c6f0917db0ea7c53c852ff6b772466f031f3a4e`: source excerpts, fixtures, oracle, builders, checker, `PREREGISTERED.sha256` |
| results commit | the commit adding this file: `git log -1 --format=%H -- research/public-evidence-spans-20261018-01/MANIFEST.md` |
| fresh-clone check | `logs/20_fresh_clone_check.log`, added by the commit after the results commit, which it checks |
| platform | Linux only: CPython 3.12.3, SQLite 3.45.1 with FTS5, x86_64 |

## Files

| path | role |
|---|---|
| `REPORT.md` | findings, outcome levels, every disagreement, provenance, commands, macOS replay, limits |
| `source/urllib.request.rst.excerpts.json` | exact source lines of the 23 excerpts (python/cpython `58ed60b7`), with hashes |
| `source/LICENSE-PSF-cpython-3.12`, `source/NOTICE.md` | PSF License v2 verbatim; attribution, copyright, summary of changes, refused HTML fetch |
| `fixtures/*.txt` | the retained UTF-8 plain-text fixtures the offsets refer to |
| `fixtures/passages.json` | byte offsets, sizes, sha256 of all 39 passages |
| `fixtures/oracle.json`, `fixtures/oracle_resolved.json` | hand-authored oracle; its resolution to spans and set costs |
| `scripts/build_fixtures.py`, `check_oracle.py`, `spans.py` | fixture builder, oracle checker, block format (pre-registered) |
| `scripts/evidence_bench.py`, `scripts/test_evidence_bench.py` | the comparison; 16 focused tests and negative controls |
| `results/run1-linux-py3.12/` | `environment.json`, `results.json` (102 results with contexts and spans), `summary.md` |
| `logs/` | exact commands with `exit=` lines |
| `PREREGISTERED.sha256` | hashes of the pre-registration files as committed in `2c6f091` (still verify) |
| `SHA256SUMS` | sha256 of every git-tracked file of this directory except itself |

## Logs

| log | exit | meaning |
|---|---|---|
| `logs/00_environment.log` | 0 | Python, SQLite, compile options, FTS5 tokenizers |
| `logs/00_source_fetch_docs_python_org.log` | 56 | the HTML page refused by the network policy (CONNECT 403) |
| `logs/01_source_extract.log` | 0 | pinned commit, blob and file hashes; excerpt extraction |
| `logs/02_build_check_oracle.log` | 0, 0 | fixtures rebuild identically; oracle consistent (17 cases, 0 problems) |
| `logs/10_evidence_bench_run1.log` | 1 | 102 results, 22 disagree with the oracle (all kept, REPORT.md section 3) |
| `logs/11_unittest_run1.log` | 0 | 16 tests OK |
| `logs/11_unittest_run2.log` | 0 | 16 tests OK after adding a `# ruff: noqa` comment line to the test file |

Verify: `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS), from this directory.

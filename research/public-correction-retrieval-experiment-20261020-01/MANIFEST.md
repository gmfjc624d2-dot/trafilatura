# Manifest: public-correction-retrieval-experiment-20261020-01

| | |
|---|---|
| request | `public-correction-retrieval-experiment-20261020-01` |
| fork / branch | `https://github.com/gmfjc624d2-dot/trafilatura`, `claude/adoring-turing-3ekxhe` (no PR, no upstream issue, no force push) |
| hypothesis | `5778f7a62a870c2cce556fcf6980a48914eb9bc5` (local = remote at start, clean, no divergence) |
| pre-registration | `fda5941ed5210d7fa09e63840508106d3cb77174`; script before its run `ce9a1ff6defed71de4cd1a134ee14d8f2a4f42ef` |
| results commit | the commit adding this file: `git log -1 --format=%H -- research/public-correction-retrieval-experiment-20261020-01/MANIFEST.md` |
| evidence | Linux x86_64 only: CPython 3.12.3 + SQLite 3.45.1 (primary), CPython 3.10.20 + SQLite 3.53.1 (compatibility); not macOS qualification; Python 3.9 syntax-checked, not executed |

## Files

| path | role |
|---|---|
| `REPORT.md` | design, observed results, negative outcomes, reader output, correction to the critique, limits, replay |
| `corpus/records/R01.txt` … `R12.txt` | the synthetic source texts (byte-exact) |
| `corpus/corpus.json` | the exact declared corpus: record id, issuer, declared date, issued identifiers, passages (byte ranges, sha256) |
| `fixtures/queries.json` | the three consumer queries |
| `fixtures/expectations.json` | pre-registered methods, expected candidate sets, reader facts, predicted findings, properties, limits, evaluation-only annotations |
| `scripts/build_corpus.py` | writes or checks the corpus and its manifest |
| `scripts/correction_retrieval.py` | the experiment: pinned earlier helpers, six strategies, reader output, result with environment separated, grading, `--against` |
| `results/run1-linux-py3.12/result.json`, `reader.md` | the primary run |
| `results/compat-linux-py3.10/result.json`, `reader.md` | the compatibility replay (0 differences in `result`, reader identical) |
| `logs/` | exact commands with `exit=` lines |
| `.gitignore`, `.gitattributes`, `ruff.toml` | this directory's only ignore, attribute and lint rules (ruff target py39) |
| `PREREGISTERED.sha256`, `SHA256SUMS` | the 20 pre-registration files (`fda5941`) plus a self-entry that cannot verify (generation defect, kept; verify with `grep -v ' PREREGISTERED.sha256$' PREREGISTERED.sha256 \| sha256sum -c`); every tracked file here except SHA256SUMS |

## Referenced, read-only (pinned by sha256 in the script and in `fixtures/expectations.json`)

| file | sha256 |
|---|---|
| `research/public-evidence-spans-20261018-01/scripts/evidence_bench.py` | `b74774f13bc2d6d534ade87e7ab537c80c5c9668df31a33706006f7d9bf3b9d4` |
| `research/public-evidence-spans-20261018-01/scripts/spans.py` | `6bc15cee4920d91cd5c3afe2b4a3f4fa1a0591fbfdd75915c18bf710b8bb19d8` |

## Logs

| log | exit | meaning |
|---|---|---|
| `logs/01_build_corpus.log` | 0 | corpus built and checked |
| `logs/10_run1_linux_py3.12.log` | 0 | primary run: 41 pass, 0 fail, 0 not run |
| `logs/11_compat_linux_py3.10.log` | 0 | Python 3.10 replay `--against` run1: 0 differences; reader identical (display filter disclosed in the log) |

Verify: `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS), from this directory.

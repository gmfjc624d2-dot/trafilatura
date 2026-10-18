# Manifest: public-json-numeric-integrity-20261018-01

| | |
|---|---|
| request | `public-json-numeric-integrity-20261018-01` |
| fork / branch | `https://github.com/gmfjc624d2-dot/trafilatura`, `claude/adoring-turing-3ekxhe` (no PR, no upstream issue, no force push) |
| continued from | `b4fa1424ead6fe23e93ed1ca6a698e401f2b403b`; branch unmoved, ancestry checked (`logs/00_identity_environment.log`) |
| pre-registration commit | `5c3e94f30cd954a57b1a0fbb31102b36d61f6c47` (before any comparator ran on the cases) |
| baseline run commit | `f667484067666298c6f1e510cc80dab49397cbfc` (before the repaired comparator existed) |
| results commit | the commit adding this file: `git log -1 --format=%H -- research/public-json-numeric-integrity-20261018-01/MANIFEST.md` |
| fresh-clone check | `logs/30_fresh_clone_check.log`, added by the commit after the results commit, which it checks |
| platform | Linux only: Python 3.12.3, libmpdec 2.5.1, x86_64, standard library only |

## Files

| path | role |
|---|---|
| `REPORT.md` | defect, contract, limits, documented/policy/executed, every failure, commands, macOS replay |
| `references/REFERENCES.md` | CPython v3.12.14 / v3.12.3 sources: tags, blobs, quoted lines |
| `scripts/compare_results_baseline_9a7933f.py` | verbatim baseline (sha256 `9a7933f8…`, git blob `89a24718…`) |
| `scripts/compare_results.py` | the repaired successor (sha256 `29267d53…`) |
| `scripts/measure_retained.py`, `results/measurement/retained_json.json` | measurement of the 33 retained JSON files that sized the limits |
| `scripts/build_fixtures.py`, `fixtures/cases/*.json`, `fixtures/files.json`, `fixtures/expectations.json` | byte-exact fixtures (100), their sha256 and those of 4 generated inputs, pre-registered policy, limits and outcomes |
| `scripts/run_cases.py` | grades one comparator on every case (committed with the baseline run) |
| `scripts/test_compare_results.py` | 27 focused offline tests with negative controls |
| `results/baseline-linux-py3.12/`, `results/run1-linux-py3.12/` | `cases.json` (compared on replay), `interpreter_observations.json` (version-specific) |
| `logs/` | exact commands with `exit=` lines |
| `PREREGISTERED.sha256` | hashes of the 114 pre-registration files as committed in `5c3e94f` (still verify) |
| `SHA256SUMS` | sha256 of every git-tracked file of this directory except itself |

## Logs

| log | exit | meaning |
|---|---|---|
| `logs/00_identity_environment.log` | 0 | head = remote = `b4fa142`, ancestry, baseline source identity, interpreter |
| `logs/01_references.log` | 56 ×3, 0 | docs.python.org refused; CPython sources fetched; local json = v3.12.3; scanner diff to v3.12.14 |
| `logs/02_measure_retained.log` | 0 | retained JSON sizes, depths and number tokens |
| `logs/03_build_check_fixtures.log` | 0 | fixtures rebuild identically; their text |
| `logs/10_run_cases_baseline.log` | 1 | 275 checks, 30 predicted failures kept, 0 findings; O1 misprediction kept |
| `logs/11_posthoc_unicode_digits.log` | 0 | post-hoc: v3.12.3 pure-Python scanner passes non-leading Unicode digits |
| `logs/20_run_cases_repaired_run1.log` | 1 | 188 checks, 186 pass; 2 mispredicted display strings (I07, I10) and O1 kept |
| `logs/21_unittest_run1.log` | 0 | 27 tests OK |
| `logs/22_scope_check.log` | 0 | nothing outside this directory changed; earlier hash lists verify; lint; comparator identities |

Verify: `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS), from this directory.

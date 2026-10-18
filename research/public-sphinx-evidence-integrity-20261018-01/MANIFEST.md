# Manifest: public-sphinx-evidence-integrity-20261018-01

| | |
|---|---|
| request | `public-sphinx-evidence-integrity-20261018-01` |
| fork / branch | `https://github.com/gmfjc624d2-dot/trafilatura`, `claude/adoring-turing-3ekxhe` (no PR, no upstream issue, no force push) |
| continued from | `7345bfea30ce378dfd91d5121a10dd2db2fb8f1d` (earlier increments unchanged, `logs/23_scope_check.log`) |
| pre-registration commit | `d386b49a65d128eca6523b858c58b17a307652b8` (before any lxml run on the new fixtures) |
| baseline reproduction commit | `9004016759a60530d6dded55f548d65efee6a962` (before any repaired code existed) |
| results commit | the commit adding this file: `git log -1 --format=%H -- research/public-sphinx-evidence-integrity-20261018-01/MANIFEST.md` |
| fresh-clone check | `logs/30_fresh_clone_check.log`, added by the commit after the results commit, which it checks |
| platform | Linux only: Python 3.12.3, lxml 6.1.3, libxml2 2.14.6, x86_64 |

## Files

| path | role |
|---|---|
| `REPORT.md` | defects, repair, identities, comparison, budget scope, every failure, limits, commands, macOS replay |
| `fixtures/n1_late_diagnostic.html`, `n2_comment_match.html` | the two supplied public synthetic inputs, byte-exact (no final newline) |
| `fixtures/n3_windows1252.html`, `n4_outside_diagnostic.html`, `n5_clean_control.html` | original synthetic pages (windows-1252; diagnostic outside the unit; its clean control) |
| `fixtures/files.json`, `byte_facts.json` | fixture identities; literal byte facts the predictions refer to (not alignments) |
| `fixtures/expectations.json` | pre-registered defects, rules, requirements, baseline predictions, old-case transform, 32 mutation controls |
| `scripts/build_fixtures.py`, `check_fixtures.py` | byte-exact builder and parser-free checker (pre-registered) |
| `scripts/anchor_unit_baseline_7345bfe.py`, `compare_results_baseline_7345bfe.py` | verbatim copies of the 7345bfe helper and comparator (sha256 `03b0f28f…`, `22af5ffa…`) |
| `scripts/grading.py`, `reproduce_baseline.py` | grading and the baseline-only run (committed before the repair) |
| `scripts/anchor_unit.py` | repaired helper: R1 diagnostics, R2 no spans, R3 identities, R4 budget scope |
| `scripts/compare_results.py` | repaired recursive comparator, three exempt environment values |
| `scripts/run_experiment.py` | grades both helpers and both comparators against the pre-registration |
| `scripts/test_evidence_integrity.py` | 20 focused offline tests with negative controls |
| `results/baseline-linux-py3.12/baseline_reproduction.json` | baseline outputs, checks, comparator outcomes |
| `results/run1-linux-py3.12/results.json`, `summary.md` | all outputs (5 new × 2 helpers, 27 old repaired), checks, mutation outcomes |
| `logs/` | exact commands with `exit=` lines |
| `PREREGISTERED.sha256` | hashes of the 17 pre-registration files as committed in `d386b49` (still verify) |
| `SHA256SUMS` | sha256 of every git-tracked file of this directory except itself |

## Logs

| log | exit | meaning |
|---|---|---|
| `logs/00_environment.log` | 1, 0, 0, 0 | system Python 3.12 has no lxml; venv versions; head; previous increment's hashes intact |
| `logs/01_build_check_fixtures.log` | 0, 0 | fixtures rebuild identically; byte checks, 0 problems; supplied inputs shown with `cat -A` |
| `logs/10_reproduce_baseline.log` | 0 | 145 checks, 14 predicted baseline failures kept, 0 findings; baseline comparator misses 23 of 32 |
| `logs/20_run_experiment_attempt1_crash.log` | 1 | first repair run: strict comparator refused lxml str subclasses in memory (kept) |
| `logs/21_run_experiment_run1.log` | 0 | 386 checks, 17 predicted failures kept, 0 findings |
| `logs/22_unittest_run1.log` | 0 | 20 tests OK |
| `logs/23_scope_check.log` | 0 | nothing outside this directory changed since `7345bfe`; earlier hash lists verify; lint of this directory |

Verify: `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS), from this directory.

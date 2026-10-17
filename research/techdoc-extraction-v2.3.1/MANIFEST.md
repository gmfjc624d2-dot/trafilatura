# Manifest: techdoc-extraction-v2.3.1

## Identities

| | |
|---|---|
| upstream | `https://github.com/adbar/trafilatura`, tag `v2.3.1` = `e2f85c965662c7df26b73290ef175b2c2a5fdca6` (**parent**) |
| fork / branch | `https://github.com/gmfjc624d2-dot/trafilatura`, `claude/adoring-turing-3ekxhe` (no PR, no upstream issue) |
| `63d32dc123437604cd44a5afb59a60f7c1e4ca55` | research: pre-registration (fixtures, expectations, SHA256SUMS) + baseline link reproduction |
| `d5690f1` | research: mode-matrix harness + v2.3.1 matrix results |
| **`bb0e4fac70ff12b635213960c71e912bfe68e630`** | **source fix (result commit for the code)**: `trafilatura/htmlprocessing.py`, `trafilatura/core.py`, `trafilatura/external.py`, `tests/unit_tests.py`, `docs/usage-python.rst` |
| artifact commit | the commit adding this file: `git log -1 --format=%H -- research/techdoc-extraction-v2.3.1/MANIFEST.md` |

Separation check: `git diff --stat e2f85c9 HEAD -- . ':!research'` lists exactly the 5 source
files of `bb0e4fa`; every other change is under `research/techdoc-extraction-v2.3.1/`.

## Deliverables

| path | content |
|---|---|
| `REPORT.md` | question, verdict, reproduction, `<base>` semantics, every loss, tests, limits |
| `PORTABLE_TEST_RECIPE.md` | Linux / macOS Apple Silicon / Windows recipe (only Linux was run) |
| `patch/0001-fix-resolve-relative-links-against-the-full-document.patch` | `git format-patch -1 bb0e4fa`, sha256 `a7db64927a2e2ca594f12f44d59e4069bc6e22f6a513bfe9e84199391e2551d5` |
| `patch/source-fix_v2.3.1..bb0e4fa.diff` | `git diff e2f85c9 bb0e4fa -- trafilatura tests docs`, sha256 `0f77a6db1304ae5e118beeb00b5908569f64a26dafcc65b7cbf66dae92d9f5cb` |
| `fixtures/` | 8 synthetic pages, pre-registered `expectations.json`, `SHA256SUMS`, provenance README |
| `results/baseline-v2.3.1/` | raw results on unmodified v2.3.1, committed before the fix |
| `results/baseline-v2.3.1-rerun/` | final scripts on a clean v2.3.1 worktree (identical to the above) + post-hoc |
| `results/patched-bb0e4fa/` | final scripts on `bb0e4fa` + post-hoc |
| `results/public_fixture_provenance.json` | 95 reused upstream pages: URL, sha256, blob, first-add commit, license note |
| `scripts/` | `run_all.py` drives `check_expectations`, `repro_links`, `public_corpus_links`, `mode_matrix`; plus `compare_runs`, `posthoc_analysis`, `probe_base_survival`, `public_provenance`, `coverage_check` |
| `ARTIFACTS.sha256` | sha256 of every file in this directory except itself |

Environment: Ubuntu 24.04.5 LTS, Linux 6.18.44 x86_64; CPython 3.13.16 (also 3.10.20 and
3.11.17 for the full suite), lxml 6.1.3 / libxml2 2.14.6, courlan 1.4.0; complete freezes in
`logs/patched-bb0e4fa_pip_freeze_py*.txt`. Session clone was shallow until
`git fetch --unshallow` (affects only the superseded `added_in_commit` field, REPORT.md section 7).

## Logs (final `exit=` line of each)

Exit 1 is expected where marked: the research scripts exit 1 when they find failures or losses.

| log | exit | meaning of a non-zero exit |
|---|---|---|
| `logs/check_expectations.log` | 0 | |
| `logs/baseline-v2.3.1_repro_links.log` | 1 | 16/24 cases fail: the defect |
| `logs/baseline-v2.3.1_public_corpus_links_as-is.log` | 1 | 53 strict mismatches |
| `logs/baseline-v2.3.1_public_corpus_links_naive-ablation.log` | 1 | 3 mismatches (simplyscience.ch) |
| `logs/baseline-v2.3.1_mode_matrix.log` | 1 | 960 pre-registered losses |
| `logs/baseline-v2.3.1_pytest_full.log` | 1 | 3 environmental failures, 4313 passed |
| `logs/baseline-v2.3.1_new_regression_tests.log` | 1 | 26 of the 33 new cases fail on v2.3.1 (13 behavioural, 13 helper absent) |
| `logs/baseline-v2.3.1_eval_gate.log` | 0 | |
| `logs/patched_pytest_full.log` | 1 | uncommitted tree = `bb0e4fa` diff; 3 environmental failures, 4346 passed |
| `logs/patched_eval_gate.log` | 0 | |
| `logs/patched-bb0e4fa_check_expectations.log` | 0 | |
| `logs/patched-bb0e4fa_repro_links.log` | 1 | 8 direct-`convert_tags` `<base>` cases (documented boundary) |
| `logs/patched-bb0e4fa_public_corpus_links_as-is.log` | 0 | |
| `logs/patched-bb0e4fa_mode_matrix.log` | 1 | 384 losses, none link-target related |
| `logs/patched-bb0e4fa_posthoc_matrix.log` | 0 | |
| `logs/patched-bb0e4fa_posthoc_corpus.log` | 0 | |
| `logs/patched-bb0e4fa_probe_base_survival.log` | 0 | |
| `logs/patched-bb0e4fa_coverage_check.log` | 0 | |
| `logs/patched-bb0e4fa_pytest_full.log` | 1 | 3 environmental failures, 4346 passed |
| `logs/patched-bb0e4fa_pytest_full_py3.10.log` | 1 | same 3, 4346 passed |
| `logs/patched-bb0e4fa_pytest_full_py3.11.log` | 1 | same 3, 4346 passed |
| `logs/patched-bb0e4fa_pytest_new_regression_tests.log` | 0 | 35 passed (33 new + 2 existing) |
| `logs/patched-bb0e4fa_ruff_check.log` | 0 | |
| `logs/patched-bb0e4fa_ruff_format.log` | 0 | |
| `logs/patched-bb0e4fa_mypy.log` | 0 | |
| `logs/patched-bb0e4fa_docs_tests.log` | 1 | Sphinx `-W` build: 3 intersphinx fetches refused by the sandbox proxy; doctest passed |
| `logs/docs_build_warnings_baseline_vs_patched.log` | 0 | identical warning lists |
| `logs/baseline-v2.3.1-rerun_check_expectations.log` | 0 | |
| `logs/baseline-v2.3.1-rerun_repro_links.log` | 1 | as baseline |
| `logs/baseline-v2.3.1-rerun_public_corpus_links_as-is.log` | 1 | as baseline |
| `logs/baseline-v2.3.1-rerun_public_corpus_links_naive-ablation.log` | 1 | as baseline |
| `logs/baseline-v2.3.1-rerun_mode_matrix.log` | 1 | as baseline |
| `logs/baseline-v2.3.1-rerun_posthoc_matrix.log` | 0 | |
| `logs/baseline-v2.3.1-rerun_posthoc_corpus.log` | 0 | |
| `logs/compare_baseline-v2.3.1__vs__baseline-v2.3.1-rerun.log` | 0 | `differences: 0` |
| `logs/compare_baseline-v2.3.1-rerun__vs__patched-bb0e4fa.log` | 1 | `worse: 1` = the direct-`convert_tags` `base-host-root` case |
| `logs/patch_apply_check.log` | 0 | both patch forms apply to pristine v2.3.1 and reproduce `bb0e4fa` |
| `logs/public_fixture_provenance.log` | 0 | |

Verify: `sha256sum -c ARTIFACTS.sha256` (Linux), `shasum -a 256 -c ARTIFACTS.sha256` (macOS).

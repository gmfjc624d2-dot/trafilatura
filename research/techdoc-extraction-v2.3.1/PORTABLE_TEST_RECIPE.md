# Portable test recipe (Linux, macOS Apple Silicon, Windows)

**Tested platform: Linux only** (Ubuntu 24.04.5, x86_64, Python 3.13.16; full suite also on
3.10.20 and 3.11.17). The macOS and Windows steps below are written for those platforms but
were **not run** in this research; treat any result there as new evidence, not as a
confirmation of the Linux logs.

Everything is offline except `pip install` and `git clone`. No step downloads a web page.

## 1. Get the branch and the baseline

```sh
git clone https://github.com/gmfjc624d2-dot/trafilatura.git
cd trafilatura
git checkout claude/adoring-turing-3ekxhe
git rev-parse e2f85c965662c7df26b73290ef175b2c2a5fdca6^{commit}   # parent = upstream tag v2.3.1
git log --oneline e2f85c9..HEAD                                   # research + fix commits
git worktree add --detach ../trafilatura-v2.3.1 e2f85c965662c7df26b73290ef175b2c2a5fdca6
```

Optional upstream identity check: `git ls-remote https://github.com/adbar/trafilatura refs/tags/v2.3.1`
must print `e2f85c965662c7df26b73290ef175b2c2a5fdca6`.

## 2. Environment

| | Linux / macOS (zsh, bash) | Windows (PowerShell) |
|---|---|---|
| create | `python3 -m venv .venv` | `py -3.13 -m venv .venv` |
| activate | `source .venv/bin/activate` | `.venv\Scripts\Activate.ps1` |
| install | `python -m pip install -e ".[dev]"` | `python -m pip install -e ".[dev]"` |

Apple Silicon: use a native arm64 Python (`python -c "import platform; print(platform.machine())"`
prints `arm64`); lxml ships arm64 wheels, no compiler needed. Windows: same for `AMD64`/`ARM64`.
Record `python --version` and `python -m pip freeze`; the Linux freezes are in
`logs/patched-bb0e4fa_pip_freeze_py*.txt`.

## 3. Verify the fixture bytes (any OS)

```sh
python -c "import hashlib,pathlib;d=pathlib.Path('research/techdoc-extraction-v2.3.1/fixtures');[print('OK' if hashlib.sha256((d/n).read_bytes()).hexdigest()==h else 'MISMATCH',n) for h,n in (l.split() for l in (d/'SHA256SUMS').read_text().splitlines())]"
```

All lines must print `OK`. On Windows a `MISMATCH` usually means line endings were converted
(e.g. files copied rather than checked out); restore them from git, which applies the research
`.gitattributes` (`-text`): `Remove-Item -Recurse research\techdoc-extraction-v2.3.1\fixtures; git checkout -- research`.

## 4. Source regression tests (patched tree)

```sh
python -m pytest -p no:cacheprovider tests/unit_tests.py -v -k "resolves_links_against_document_url or test_document_base_url or honors_base_href or readability_links_honor_base_href"
```

Linux result: 33 passed (`logs/patched-bb0e4fa_pytest_new_regression_tests.log` shows 35 with
the two pre-existing link tests added to the selection). Full suite: `python -m pytest -p no:cacheprovider -rfEs`
(Linux: 4346 passed, 3 failed for environmental reasons, see REPORT.md section 8).
Expected platform differences in the full suite: `tests/cli_tests.py::test_sysoutput` behaves
differently on Windows by design, and the live-network download tests need internet access.

Lint and types as in CI: `ruff check .`, `ruff format --check .`, `mypy -p trafilatura`.

## 5. Research harness, patched tree

```sh
python research/techdoc-extraction-v2.3.1/scripts/run_all.py local-patched
```

Writes `results/local-patched/` and `logs/local-patched_*.log`. Step exit codes 1 are expected
(they mean "losses found"): `repro_links` 1 (8 direct-`convert_tags` `<base>` cases),
`public_corpus_links_as-is` 0, `mode_matrix` 1 (384 pre-registered losses, none link-related).

## 6. Research harness, v2.3.1 baseline

Point Python at the baseline worktree; the scripts record which source they imported
(`trafilatura_file`, `git_head`) in every result file.

| Linux / macOS | Windows (PowerShell) |
|---|---|
| `PYTHONPATH=../trafilatura-v2.3.1 python research/techdoc-extraction-v2.3.1/scripts/run_all.py local-baseline --ablation` | `$env:PYTHONPATH="..\trafilatura-v2.3.1"; python research\techdoc-extraction-v2.3.1\scripts\run_all.py local-baseline --ablation; Remove-Item Env:PYTHONPATH` |

## 7. Compare with the committed Linux evidence

```sh
python research/techdoc-extraction-v2.3.1/scripts/compare_runs.py research/techdoc-extraction-v2.3.1/results/patched-bb0e4fa research/techdoc-extraction-v2.3.1/results/local-patched --expect-identical
python research/techdoc-extraction-v2.3.1/scripts/compare_runs.py research/techdoc-extraction-v2.3.1/results/baseline-v2.3.1 research/techdoc-extraction-v2.3.1/results/local-baseline --expect-identical
python research/techdoc-extraction-v2.3.1/scripts/compare_runs.py research/techdoc-extraction-v2.3.1/results/local-baseline research/techdoc-extraction-v2.3.1/results/local-patched
```

`compare_runs.py` compares parsed JSON and raw extraction outputs, not file bytes, so CRLF
line endings written on Windows do not matter. On Linux both `--expect-identical` runs gave
`differences: 0`. Elsewhere, a difference is a finding to report (a different lxml/libxml2
build can parse malformed HTML differently, `f6_malformed.html` is the most likely place),
not a reason to edit the expectations: `fixtures/expectations.json` is pre-registered.

## 8. Clean up

```sh
git worktree remove ../trafilatura-v2.3.1
```

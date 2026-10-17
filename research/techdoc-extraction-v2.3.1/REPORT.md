# Offline extraction of technical reference documentation with trafilatura 2.3.1

Research question: can the offline extraction API preserve decisive statements, code
indentation, tables and link targets in technical reference documentation, without treating a
shortened output as proof of correctness?

Every number below is taken from a file in `logs/` or `results/`; output length is recorded
but never used as evidence. Linux evidence only (section 9).

## 1. Verdict (qualified)

* **Link targets: defective in 2.3.1, fixed by `bb0e4fa`.** Relative links lost the document
  path and query, and protocol-relative links were downgraded to `http`. After the fix every
  link requirement passes in every mode where links are on, on the synthetic fixtures and on
  all 565 link targets of the 95 public corpus pages.
* **Decisive statements, negations, inline-code characters, code indentation, nested lists and
  typed tables** were preserved on every *well-formed* fixture, in every mode, option set and
  format. Tables require `include_tables=True` (the default).
* **Not preserved, unchanged by this increment and kept as failures**: text outside the main
  container that the extractor selects (malformed page `f6`: one code block, one statement and
  one link lost in all 96 configurations, `favor_recall` included); code/emphasis marking with
  `output_format="markdown"` plus an explicit `include_formatting=False`; and in txt/markdown
  with links on, sentences interleaved with `[text](url)` markup. Section 6 shows how a caller
  detects each one.
* Acquisition use: acceptable for well-formed reference pages **with the fix**, provided the
  caller passes the page URL, reads links from `output_format="xml"` (or tolerates inline
  markdown links), and runs the coverage check of section 6 against `html2txt()` to catch
  content-selection losses. Without that check, malformed pages can silently lose decisive
  text in every mode.

## 2. Identity

| item | value |
|---|---|
| upstream baseline | `adbar/trafilatura` tag `v2.3.1` = `e2f85c965662c7df26b73290ef175b2c2a5fdca6` (verified with `git ls-remote https://github.com/adbar/trafilatura refs/tags/v2.3.1`; local HEAD identical at start) |
| research branch | `claude/adoring-turing-3ekxhe` on `https://github.com/gmfjc624d2-dot/trafilatura` (fork only; no upstream issue or PR) |
| `63d32dc` | research: pre-registered fixtures and expectations + baseline link reproduction |
| `d5690f1` | research: mode-matrix harness + its v2.3.1 baseline results |
| **`bb0e4fa`** | **source fix** (only `trafilatura/`, `tests/`, `docs/`; parent `d5690f1`, whose source tree equals v2.3.1) |
| artifact commit | the commit that adds this report and `MANIFEST.md` (`git log -1 --format=%H -- research/techdoc-extraction-v2.3.1/MANIFEST.md`) |
| git identity | session identity `Claude <noreply@anthropic.com>` |
| platform | Ubuntu 24.04.5 LTS, Linux 6.18.44, x86_64, glibc 2.39 |
| Python / libs | CPython 3.13.16; lxml 6.1.3 (libxml2 2.14.6); courlan 1.4.0; htmldate 1.11.0; jusText 3.0.2; charset-normalizer 3.5.2; urllib3 2.8.0; pytest 9.1.1; ruff 0.16.10; mypy 2.4.0 (`[dev]` extras, not `[all]`) |

## 3. Reproduction of the reported defect (2.3.1)

`scripts/repro_links.py`: document URL `https://example.org/docs/v1/api.html?view=full`;
expected `urllib.parse.urljoin(document_url, href)`. Paths: `convert_tags(tree, Extractor(links=True), url)`
and `extract(doc, url=url, include_links=True, output_format="xml")` with default,
`fast=True`, `favor_recall=True` and `favor_precision=True`.

| href | expected | 2.3.1 (all 5 paths) | `bb0e4fa` |
|---|---|---|---|
| `#method` | `https://example.org/docs/v1/api.html?view=full#method` | `https://example.org#method` | PASS |
| `peer.html` | `https://example.org/docs/v1/peer.html` | `https://example.org/peer.html` | PASS |
| `../overview.html` | `https://example.org/docs/overview.html` | `https://example.org/overview.html` | PASS |
| `?view=short` | `https://example.org/docs/v1/api.html?view=short` | `https://example.org?view=short` | PASS |
| `//other.example/guide` | `https://other.example/guide` | `http://other.example/guide` | PASS |
| `./sub/page.html`, `peer.html#frag` | path kept | host only | PASS |
| `/reference/index.html`, `//example.org/same`, absolute http(s), `mailto:` | unchanged | PASS | PASS |

Cause: `htmlprocessing.convert_tags` passed `safe_base_url(url)` (scheme + host) to
`convert_link`, which joined with `courlan.fix_relative_urls`; that helper also forces `http`
on a scheme-less foreign host. Logs: `logs/baseline-v2.3.1_repro_links.log` (exit 1, 16/24
cases failing) and `logs/patched-bb0e4fa_repro_links.log` (exit 1, 8/24, all of them in the
direct-`convert_tags` column with `<base>`, section 4).

## 4. `<base href>`: supported semantics

* **2.3.1**: ignored. `<head>` is in `MANUALLY_CLEANED`, so `tree_cleaning()` deletes `<base>`
  before `convert_tags` runs. Pages whose base is the site root were right only by coincidence
  (host-only joining happens to equal it).
* **`bb0e4fa`** follows the HTML Standard "document base URL": the first `<base>` with an
  `href` attribute in tree order (`<base target>` alone is skipped), its value stripped and
  parsed against the document URL; if parsing fails, or the result has no scheme, or the
  scheme is `data:`/`javascript:`, the document URL is used. Without a document URL only an
  absolute base applies. Links are then `urljoin(document_base_url, href)`; a fragment link
  resolves against the base (`#top` → `https://docs.example.org/sdk/v2/#top`), as in browsers.
* The base is read once on the **raw** tree (`document_base_url()` in `trafilatura_sequence()`
  and, for the readability output, in `compare_extraction()`), because `tree_cleaning` removes
  `<head>` but keeps a `<base>` placed in `<body>` (`logs/patched-bb0e4fa_probe_base_survival.log`):
  re-reading it after cleaning would apply a path-relative base twice (`.../sub/sub/`).
* **Boundary, kept as recorded failures**: `convert_tags(tree, options, url)` itself resolves
  against the `url` it is given and does not read `<base>`. Calling it directly on a raw tree
  that declares a base gives document-URL resolution: 8 cases in `repro_links` (one of them,
  `base-host-root`, passed by coincidence on 2.3.1 and fails in this column now, the only
  verdict that got worse in `logs/compare_baseline-v2.3.1-rerun__vs__patched-bb0e4fa.log`).
  Through `extract()`/`bare_extraction()` all 11 base cases pass in all four modes. Direct
  callers pass `document_base_url(raw_tree, url)`; `document_base_url(tree, url) != url` tells a
  caller that a page declares an effective base (module `trafilatura.htmlprocessing`, not part
  of the package's `__all__`).
* Not changed: image `src` resolution (`handle_image` uses `options.url`, ignores `<base>`),
  downloads, crawling, feeds, sitemaps, metadata URLs.

## 5. The fix (`bb0e4fa`, 5 files, +163/−14)

* `convert_link`: `urljoin(base_url, href)` instead of the courlan host-only join. Kept as
  before: `{...}` template placeholders and malformed URLs (`ValueError`) stay verbatim.
* `document_base_url(tree, url)` (new) and its two raw-tree call sites; `sanitize_tree(tree,
  options, url=None)` takes the base URL (defaults to `options.url` as before).
* Behaviour change beyond the defect, intended by the `urljoin` rule: absolute same-scheme
  URLs are normalised by `urljoin` (an empty trailing `?`/`#` is dropped, the scheme is
  lower-cased). This is what removed the three "equivalent form" corpus mismatches below.
* Why not just join against the full URL: the ablation `scripts/public_corpus_links.py
  --variant naive-ablation` (full URL, `<base>` ignored) on 2.3.1 produced 3 wrong targets on
  `tests/cache/simplyscience.ch.erdoel.html` (`<base href="http://www.simplyscience.ch/">`),
  e.g. `.../teens-liesnach-archiv/articles/teens-liesnach-archiv/articles/warum-wird-das-erdoel-knapp.html`,
  links that 2.3.1 got right (`logs/baseline-v2.3.1_public_corpus_links_naive-ablation.log`).
* Docs: one comment in `docs/usage-python.rst` states the resolution rule.

## 6. Mode and option comparison on the synthetic fixtures

Pre-registered in `fixtures/expectations.json` (committed in `63d32dc` before any extraction ran
on the fixtures; two corrections made before that commit by the source-only checker are in
`logs/check_expectations.log`). Call, for each of 8 fixtures:

```python
trafilatura.extract(fixture_bytes, url=<fixture url>, output_format=fmt,
                    include_links=L, include_tables=T, include_formatting=F, **mode)
# mode in {}, {"fast": True}, {"favor_precision": True}, {"favor_recall": True}
# L, T, F in {False, True}; fmt in {"txt", "markdown", "xml"}; everything else default
```

768 configurations, 64 requirements. Verdicts per requirement type (FAIL = loss, R11):

| type | reqs | FAIL 2.3.1 | FAIL `bb0e4fa` | PASS `bb0e4fa` | excluded by option |
|---|---|---|---|---|---|
| statement (incl. prerequisite, negations) | 23 | 160 | 160 | 2000 | 48 |
| inline code characters | 3 | 0 | 0 | 288 | 0 |
| inline code marked as code | 3 | 48 | 48 | 144 | 96 |
| code block with indentation | 3 | 96 | 96 | 192 | 0 |
| nested list structure | 3 | 0 | 0 | 192 | 0 (+96 INFO, txt) |
| emphasis on the negation | 2 | 32 | 32 | 96 | 64 |
| typed table rows (incl. `str \| None`) | 12 | 0 | 0 | 576 | 576 |
| link targets | 18 | 624 | 48 | 816 | 864 |
| **total** | 64 | **960** | **384** | 4304 | 1648 |

Raw outputs changed only for the three link fixtures (`f5`, `f7`, `f8`: 48 each, the
`include_links=True` configurations); the other 624 outputs are byte-identical.

**Every remaining loss** (`bb0e4fa`; classification is POST-HOC, `logs/patched-bb0e4fa_posthoc_matrix.log`,
verdicts unchanged):

| fixture :: requirement | FAILs | configurations | post-hoc cause | how a caller detects or avoids it |
|---|---|---|---|---|
| `f6` :: code-block-indentation | 96 | all | dropped by main-content selection: text after the stray `</div></div></span>` is outside the selected `#content` div | present in `trafilatura.html2txt()` and `baseline()` but absent from `extract()`: compare, see below |
| `f6` :: security-only (statement) | 96 | all | same | same |
| `f6` :: link-changes | 48 | all with `include_links=True` | same paragraph | same |
| `f5` :: read-first, sdk-team (statements) | 32 + 32 | txt and markdown with `include_links=True` | sentence words interleaved with `[text](url)` markup; the statement is intact once link markup is reduced to its text | use `output_format="xml"` (text and `<ref target>` separate) |
| `f2` :: inline-connect-marked, inline-operator-marked; `f8` :: inline-publish-marked | 16 × 3 | `output_format="markdown"`, `include_formatting=False` | explicit `False` overrides markdown's implied formatting, by design (`trafilatura/settings.py:148-149`) | leave `include_formatting` unset or `True` with markdown |
| `f3`, `f8` :: not-emphasis | 16 × 2 | same | same | same |

Coverage check for content-selection losses (offline, any page; `scripts/coverage_check.py`):

```python
import re

from trafilatura import extract, load_html

BLOCKS = ("p", "li", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "dd", "dt", "blockquote")


def words(s):
    return re.findall(r"\w+", s)


def missing_blocks(page, url, min_words=6):
    "Text blocks of the page whose words do not all occur in the extraction."
    out = set(words(extract(page, url=url) or ""))
    tree = load_html(page)
    blocks = (" ".join(" ".join(el.itertext()).split()) for el in tree.iter(BLOCKS))
    return [b for b in blocks if len(words(b)) >= min_words and not set(words(b)) <= out]
```

On the eight fixtures (`logs/patched-bb0e4fa_coverage_check.log`) it flags exactly the three
`f6` blocks lost by content selection (the change-log paragraph, the code block, the
security-fixes statement), plus footer/cookie boilerplate on every page, which is correctly
absent from the output: the caller reviews the list. It detects; it does not fix. A first
version based on `html2txt()` lines was useless (`html2txt()` returns one line per page) and
was replaced before this report was committed.

Further observations, not pre-registered requirements: markdown/txt output of `f3` carries a
whitespace-only line after "Supported platforms:"; identifiers outside code (`x86_64`,
`sync_mode`) are escaped as `x86\_64` in markdown; none of the listed boilerplate strings
occurs in any of the 768 outputs (field `boilerplate_found_info` per record in
`results/*/matrix_outputs.jsonl`).

## 7. Public fixtures (upstream test corpus, read-only)

`scripts/public_corpus_links.py` over the 95 pages of `tests/cache` that have an http(s) URL in
`tests/evaldata.json` and at least one relative link (7 of them declare `<base>`). Reference:
`urljoin(document base URL, href)` computed independently from each raw page.

| run | strict mismatches (default / fast) | pages |
|---|---|---|
| 2.3.1 | 53/565 / 47/563 | 7 / 6 |
| 2.3.1, naive ablation | 3/565 / 3/563 | 1 (`simplyscience.ch`, wrong resource) |
| `bb0e4fa` | **0/565 / 0/563** | 0 |

POST-HOC classification of the 2.3.1 mismatches (`logs/baseline-v2.3.1-rerun_posthoc_corpus.log`):
50 (default) / 44 (fast) point to a different resource, e.g. Wikipedia `#cite_note-2` →
`https://en.wikipedia.org#cite_note-2` (host root, not the article) and protocol-relative
`//www.ncbi.nlm.nih.gov/...` → `http://...` on an https page; 3 are equivalent forms (empty
trailing `#`, empty path). Provenance of all 95 pages (URL, sha256, git blob, unchanged since
v2.3.1, first-add commit as the retrieval-date upper bound, license note):
`results/public_fixture_provenance.json`. The `added_in_commit` field inside
`results/*/public_corpus_links_*.json` came from the session's shallow clone and is superseded
by that file. No live page was fetched; no page was copied.

## 8. Tests and checks (Linux)

All commands ran from the repository root with the venv activated (`PATH` includes its `bin/`).

| command | tree | exit | result | log |
|---|---|---|---|---|
| `python -m pytest -p no:cacheprovider -rfEs` | v2.3.1 worktree | 1 | 4313 passed, 3 failed, 8 skipped, 37 xfailed | `logs/baseline-v2.3.1_pytest_full.log` |
| same | `bb0e4fa`, py3.13 | 1 | 4346 passed, 3 failed, 8 skipped, 37 xfailed | `logs/patched-bb0e4fa_pytest_full.log` |
| same | `bb0e4fa`, py3.10.20 / 3.11.17 | 1 / 1 | 4346 passed, 3 failed (same three) | `logs/patched-bb0e4fa_pytest_full_py3.10.log`, `..._py3.11.log` |
| 33 new cases + 2 existing link tests, `-v` | `bb0e4fa` | 0 | 35 passed | `logs/patched-bb0e4fa_pytest_new_regression_tests.log` |
| the 33 new cases on v2.3.1 (one-line import shim, scratch copy, in the log) | v2.3.1 worktree | 1 | 26 failed, 7 passed | `logs/baseline-v2.3.1_new_regression_tests.log` |
| `python tests/eval_gate.py` | both | 0 / 0 | fast F1 0.9204, fallback F1 0.9261 on both (floors met) | `logs/*_eval_gate.log` |
| `ruff check .`, `ruff format --check .`, `mypy -p trafilatura` | `bb0e4fa` | 0, 0, 0 | clean | `logs/patched-bb0e4fa_ruff_*.log`, `..._mypy.log` |
| `python -m pytest docs/docs_tests.py` (`[dev,docs]`) | `bb0e4fa` | 1 | doctest passed; build failed on 3 intersphinx warnings | `logs/patched-bb0e4fa_docs_tests.log` |
| `sphinx-build --keep-going -b html docs` | both | 0 / 0 | identical 3-warning lists (intersphinx only) | `logs/docs_build_warnings_baseline_vs_patched.log` |

**The 33 new cases on v2.3.1**: 7 pass (controls that already worked: root-relative, same-host
`//`, absolute http/https, `mailto:`, template placeholder, malformed IPv6). Of the 26 failures,
**13 are behavioural link-output failures** (AssertionError: 6 `convert_tags` defect cases, 2
end-to-end `extract`, 4 end-to-end `<base>`, 1 readability path) and **13 only show that the new
helper is absent** (`test_document_base_url`, TypeError on the shim's `None`); they are not
link-output results.

**Failures not caused by the change** (identical set on v2.3.1 and `bb0e4fa`):
`tests/cli_tests.py::test_sysoutput` (expects `/root/forbidden/` to be unwritable; the session
runs as root), `tests/downloads_tests.py::test_is_live_page` and `::test_fetch` (live network:
`httpbun.com` does not resolve in this sandbox). One more observation whose raw output was
overwritten: the first patched full run, before the venv's `bin/` was on `PATH`, also failed
`tests/cli_tests.py::test_climain` (`FileNotFoundError: 'trafilatura'`, the CLI was not on
`PATH`); the activated re-run replaced that log and passes it. The docs build failure comes
from the sandbox proxy refusing `docs.python.org`, `htmldate.readthedocs.io` and
`courlan.readthedocs.io` (403). Skipped: 5 pycurl tests, 1 yaml, 2 py3langid (`[all]` extras
not installed).

Reproducibility: `logs/compare_baseline-v2.3.1__vs__baseline-v2.3.1-rerun.log` (the committed
baseline results against a fresh run of the final scripts on a clean v2.3.1 worktree):
`differences: 0`, 768/768 raw outputs identical.

## 9. Not established here

* macOS Apple Silicon and Windows were **not run**. `PORTABLE_TEST_RECIPE.md` describes how to
  run the same evidence there and compare it with these Linux results.
* CI's `[all]` extras (pycurl, brotli, cchardet, py3langid…) and Python 3.12/3.14/3.15 were not
  used; the eval gate README notes `[all]` can score slightly differently on non-UTF-8 pages.
* Image `src` resolution and `<base>` (unchanged, section 4), `output_format` json/html/csv/xmltei,
  `include_images`, `include_comments=False` and `prune_xpath` were outside the matrix.
* The fixes for the remaining losses (content selection on malformed pages, markdown link
  interleaving, the formatting override) are deliberately out of scope for this increment.

## 10. Layout

`fixtures/` synthetic pages + pre-registered expectations (+ `SHA256SUMS`, README with
provenance); `scripts/` harness (`run_all.py` drives the rest); `results/<label>/` raw JSON and
JSONL outputs for `baseline-v2.3.1` (committed before the fix), `baseline-v2.3.1-rerun` (final
scripts, clean v2.3.1 worktree), `patched-bb0e4fa`; `logs/` exact command logs ending in
`exit=<code>`; `patch/` the source fix as `git format-patch` and plain diff (both verified to
apply to a pristine v2.3.1 and reproduce `bb0e4fa`'s files, `logs/patch_apply_check.log`);
`MANIFEST.md` identities and hashes.

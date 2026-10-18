# Complete documentation units for explicit Sphinx API anchors

Request `public-sphinx-anchor-units-20261018-01`. Input: retained HTML bytes plus one explicit
anchor id (never an XPath). Output: the Sphinx object's whole `dt`/`dd` unit, or an explicit review
reason. **Linux evidence only** (Python 3.12.3, lxml 6.1.3, libxml2 2.14.6). A structurally
complete unit is **not** evidence that the passage is factually sufficient for any question, and
nothing here was semantically reviewed.

## 1. Can existing APIs do it?

* **Trafilatura structured output: no.** `trafilatura.extract(..., output_format="xml")` keeps no
  `id` attribute at all (H1 confirmed on all 7 pages); anchor strings survive only as text or link
  targets. `trafilatura.load_html()` keeps ids but parses with `remove_comments=True,
  remove_pis=True, collect_ids=False` through a module-level parser, so it alters the DOM and
  exposes no parser diagnostics. Neither is used for selection.
* **lxml.html: yes, with care.** Pitfalls confirmed: `get_element_by_id()` silently returns one of
  two elements sharing an id (H2: line 13 of lines 13 and 19); `tostring()` defaults to
  `with_tail=True` and so carries stray text after a `dd` (H3). What works: a dedicated
  `lxml.html.HTMLParser()` instance whose `error_log` is kept, `xpath("//*[@id=$anchor]")` with a
  bound variable (the anchor is data, injection attempts return `MISSING_ID`), whole-element
  `tostring(..., with_tail=False)` for the last element, and `text_content()`.
* **A minimal helper is necessary** for the association itself: `scripts/anchor_unit.py`
  (`select_unit()`, about 240 lines, lxml only). It takes only a `dt` whose class has `sig` and
  `sig-object`, returns the maximal run of `dt` siblings around it plus the following `dd` run, each
  element whole, and otherwise reports one of the pre-registered reasons. It never chooses among
  candidates, never normalises the id, never truncates.

## 2. Results (27 pre-registered cases; `results/run1-linux-py3.12/summary.md`)

96 checks: **90 pass, 2 fail, 4 recorded** (no prediction). All 27 structural expectations hold.

| outcome | text_content | dom_serialization | cases |
|---|---|---|---|
| OK_STRUCTURAL_UNIT | 6 | 4 | text: C01 function with note/warning/field list/code, C07 and C08 shared descriptions, C12 class with nested members, C13 nested method, C18 Unicode id; DOM: C07, C08, C13, C18 |
| REVIEW_OVER_BUDGET (unit structurally complete, kept whole) | 2 | 4 | text: C14, P01; DOM: C01, C12, C14, P01 |
| REVIEW (structural reason) | 19 | 19 | the expected review cases below |

Expected review cases, each reported with its reason and never resolved silently: `MISSING_ID`
(C06, P02 `numpy.nonzero` documented elsewhere), `ID_NORMALIZATION_MISMATCH` (C19 NFD, C20
percent-encoded; the NFC id is listed as a near match, not selected), `DUPLICATE_ID` (C17),
`NOT_A_SIGNATURE` (C04 label span, C05 and P04 section ids, P03 a div id inside the numpy `dd`: no
generic ancestor rule), `NOT_SPHINX_OBJECT` (C03 glossary term), `NO_DESCRIPTION` (C10),
`EMPTY_DESCRIPTION` (C09), `MULTIPLE_GROUPS_IN_OBJECT_DL` (C11), `STRAY_CONTENT_IN_OBJECT_DL` (C02),
`UNEXPECTED_NESTED_OBJECT` (C15, C16, and the malformed C21/C22), `PARSER_RECOVERY_IN_UNIT` (C23,
and additionally C21).

**Original failures (kept):** my budget predictions for C01 and C12 said the DOM context would fit;
it does not. C01 is 2054 bytes, 6 over the 2048-byte budget once query, source identity and labels
are counted; C12 is 2187 bytes. Both become `REVIEW_OVER_BUDGET` (their text contexts fit: 989 and
758 bytes). **Recorded:** P01's DOM serialization is byte-identical to the pre-registered raw region
24394-34656; P01's text context is 2469 bytes (payload 1828 bytes, about 641 bytes of query, source
identity, long public origin and labels); C18 has no raw span; C21 also reports
`PARSER_RECOVERY_IN_UNIT`.

## 3. Representations are kept apart

* **Retained HTML byte identity:** sha256 and size of the whole retained file in every context and
  result.
* **Parsed DOM serialization:** `lxml.html.tostring()` of the unit's elements. A **raw byte span**
  is claimed only when this serialization occurs byte for byte exactly once in the file: 13 of the
  17 candidates, including the five predicted spans (C01, C07, C08, C12, C13) and P01. No span for
  C18 (`&nbsp;` in the source serializes as U+00A0) or the malformed C21-C23 (recovery changed the
  markup).
* **text_content():** no whitespace normalisation and nothing removed. The numpy unit therefore
  includes the `Go Back`/`Open In Tab` button labels and the JavaScript of a `<script>` element that
  sit inside its `dd`, and doctest output such as `array([ 0,  1,  2,  3,  4, 50, 60, 70, 80, 90])`
  with its double spaces.
* **Line numbers** are libxml2's element start lines, labelled as such; they are never presented as
  byte offsets. Text offsets are not produced at all.

## 4. Parser recovery (`lxml.html.HTMLParser()` error log)

| fixture | diagnostics |
|---|---|
| f4 duplicates | line 19 `DTD_ID_REDEFINED`: ID pkg.dup already defined |
| f6 malformed | line 15 `ERR_TAG_NAME_MISMATCH` (b/i misnested) ×2, line 19 `ERR_TAG_NAME_MISMATCH` (stray `</span>`), line 23 `ERR_INVALID_ENCODING` |
| all others, numpy page | none |

Not reported, because HTML allows or recovers them silently: the omitted `</dt>`, `</dd>`, `</p>`
in f6 and the raw `&` and `<`. The omitted `</dd>` makes the next `dl` parse **inside**
`pkg.broken`'s `dd` (C21 candidate includes `MARK-AFTER-DESC`), which only the nesting rule catches.
A parser diagnostic is therefore not a reliable sign of every structural problem.

## 5. Limits

* Structural association only. Content an author relates to an object outside its `dd` (later
  paragraphs, another page) is not included; `numpy.nonzero` is linked but documented elsewhere.
* Recognises Sphinx ≥ 4 signatures (`dt.sig.sig-object`); older markup is `NOT_SPHINX_OBJECT`
  (review). Containers for nested objects: `class`, `exception` only; other domains untested.
* One public page, one Sphinx version (7.2.6), one libxml2 version. Other parsers or versions can
  parse malformed input differently.
* macOS was **not** run; section 7 gives the replay command.

## 6. Provenance and license

* `source/numpy-2.5/numpy.where.html`: published NumPy 2.5 page, byte for byte, from
  `numpy/doc` commit `be1a2c96dd1e28fd5492efb9e9f7e3bce33bd7ab`, path
  `2.5/reference/generated/numpy.where.html`, blob `62a13db7`, sha256 `ee9fb008…`, Sphinx 7.2.6. Its
  URL `https://numpy.org/doc/2.5/reference/generated/numpy.where.html` and the other docs hosts were
  refused by the session network policy (`logs/00_public_hosts_refused.log`); no page was
  reconstructed. License: BSD-3-Clause, NumPy's `LICENSE.txt` retained verbatim from `numpy/numpy`
  tag `v2.5.0` (commit `6910b28f`); `numpy/doc` itself has no license file
  (`source/PROVENANCE.md`).
* Synthetic fixtures: original, Apache-2.0; byte-exact builder `scripts/build_fixtures.py`.
* Pre-registered in commit `089f3ccec47675c4bc21414aa47ec63d94b87fda` (fixtures, regions,
  expectations, public page, builder, byte-level checker, `PREREGISTERED.sha256`) before the
  helper, probe, runner and tests existed.

## 7. Commands (Linux, from this directory) and replay

| command | exit | log |
|---|---|---|
| `python3.12 scripts/build_fixtures.py check`; `python3.12 scripts/check_expectations.py` | 0; 0 | `logs/02_build_check_expectations.log` |
| `<venv3.12>/bin/python scripts/probe_existing_apis.py results/run1-linux-py3.12/probe_existing_apis.json` | 0 | `logs/10_probe_existing_apis_run1.log` |
| `<venv3.12>/bin/python scripts/run_experiment.py results/run1-linux-py3.12` | 1 (2 failed predictions, kept) | `logs/11_run_experiment_run1.log` |
| `<venv3.12>/bin/python -m unittest discover -s scripts -v` | 0 (15 tests) | `logs/12_unittest_run1.log` |

`<venv3.12>` is a local venv (Python 3.12.3, project dependencies, `lxml==6.1.3`; nothing global;
`logs/00_environment.log`). The first attempt to start the tests stopped at a lint error before any
test ran; the logged run is the first one that executed.

**macOS Python 3.12 with an existing lxml (not run here):**

```sh
git clone --branch claude/adoring-turing-3ekxhe https://github.com/gmfjc624d2-dot/trafilatura.git trafilatura-anchor-replay
cd trafilatura-anchor-replay/research/public-sphinx-anchor-units-20261018-01
shasum -a 256 -c SHA256SUMS
python3.12 -c "import lxml, lxml.etree as e; print(lxml.__version__, e.LIBXML_VERSION)"
python3.12 scripts/run_experiment.py "$HOME/anchor-units-replay"; echo "exit=$? (1 expected: 2 failed predictions)"
python3.12 scripts/compare_results.py results/run1-linux-py3.12/results.json "$HOME/anchor-units-replay/results.json"
python3.12 -m unittest discover -s scripts -v
```

Only lxml is needed; the one Trafilatura test skips if Trafilatura's dependencies are absent.
`compare_results.py` ignores only the platform fields; any other difference (another libxml2 can
recover malformed input differently) is a finding to report, not a reason to edit expectations.

**Disclosure about earlier evidence, unchanged:** the previous increment's last check, a fresh
clone of `e7d2f5c` whose hashes all verified, ended with `pwd: error retrieving current
directory: getcwd ...` because its own cleanup deleted the working directory; that result was
reported in chat only and stays as it was. This increment keeps its verification clones.

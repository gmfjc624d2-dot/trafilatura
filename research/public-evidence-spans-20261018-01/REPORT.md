# Literal vs SQLite FTS5/BM25 evidence selection for a 2048-byte context

Request `public-evidence-spans-benchmark-20261018-01`. A small, offline, Python 3.12 stdlib
benchmark: when do literal whole-passage search and SQLite FTS5 (`unicode61`, and `unicode61
tokenchars '_'`) give an offline technical-document worker enough evidence, and when does it
still need human/source review? **Linux evidence only.** No model, network or new library is
needed to replay it.

## 1. Findings

* **The simple mechanisms suffice only when every required statement, subject, condition and
  negation sits in a passage that contains the query terms.** That held in 9 of 17 cases for every
  method (D1, D4, D6, S1, S2, S3, S6, S10, plus S5 for literal only or S7 for FTS5 only).
* **A retrieved, budget-fitting context is often not sufficient.** In plain assembly, a worker that
  takes any non-empty context as sufficient would be wrong in 4/17 cases with literal and 5/17 with
  either FTS5 variant: the subject of a sentence in a signature passage (D2, D3), a negated
  condition in the next passage (S4, "It does not apply to reading…"), a 2,000-byte context that
  lacks the read-only exception (S8, FTS5), and a word hit whose meaning is defined in another
  document (D5). The BM25 top rank is not a required passage in D1 (a bare `OpenerDirector.open`
  signature first, an unrelated `CacheFTPHandler` timeout third) or D4 (the macOS warning first);
  it is in D2, D3 and D6, and D2/D3 are still incomplete.
* **Explicit required spans close most of that gap.** With the hand-authored dependency map
  (`oracle_dependencies` assembly), 15/17 (literal) and 16/17 (both FTS5) decisions match the
  oracle, and both budget traps end in abstention instead of a partial set (S8: S13+S14 = 2107 B;
  S9: one passage of 2159 B with its label, only 713 characters). This map is written by hand for
  these passages; nothing here discovers such dependencies automatically.
* **Method differences** (all from `results/run1-linux-py3.12/summary.md`):

  | behaviour | literal | FTS5 `unicode61` | FTS5 `tokenchars '_'` |
  |---|---|---|---|
  | case | case-sensitive: `quota` misses `Quota` (S8) | folded | folded |
  | NFD `résumé` vs NFC query (S7) | miss | hit | hit |
  | Japanese without spaces (S5) | hit | **miss** (no segmentation) | **miss** |
  | `no_proxy`, `check_hostname` | exact | phrase `no proxy`/`check hostname`: collisions D10 (+505 B in D4) and S03 | exact token, no collision |
  | `timeout` vs `retry_on_timeout` (S4) | substring hit | token hit | no hit |
  | ranking | document order | BM25 | BM25 |

* Unanswerable controls behave as intended: D5 (meaning deferred to `http.client`) gets hits from
  every method and is `HITS_NOT_SUFFICIENT_REVIEW`; S11 (`SOCKS5`, absent) gets no hits anywhere.

**Practical rule for the worker:** quote every FTS5 term (`fts_query()`; raw `NOT` is an operator,
`read-only` is a syntax error); prefer `tokenchars '_'` for identifiers and keep literal search for
CJK and exact strings; never read a hit or a score as sufficiency; send to review when a passage
defers to another document, when a selected body passage lacks its signature/subject, when a
condition may sit in a neighbouring passage, or when required passages do not fit whole.

## 2. Outcome levels (102 results = 17 cases × 3 methods × 2 assemblies)

| method | assembly | retrieved any | whole required set retrieved | budget-fitting | oracle-complete | semantically reviewed |
|---|---|---|---|---|---|---|
| literal | plain | 14 | 10 | 17 | 9 | 0 |
| literal | oracle_dependencies | 14 | 10 | 17 | 12 | 0 |
| fts5_unicode61 | plain | 15 | 10 | 17 | 9 | 0 |
| fts5_unicode61 | oracle_dependencies | 15 | 10 | 17 | 12 | 0 |
| fts5_unicode61_underscore | plain | 15 | 10 | 17 | 9 | 0 |
| fts5_unicode61_underscore | oracle_dependencies | 15 | 10 | 17 | 12 | 0 |

"Budget-fitting" is true by construction (asserted for all 102): labels and separators are counted
and no passage is truncated. "Oracle-complete" is a mechanical check against the hand-authored
required sets. **No result was semantically reviewed by a human**; "SUFFICIENT_PER_ORACLE" is not
a reviewed verdict.

## 3. Every disagreement with the oracle (run 1, all kept)

22 of 102 results disagree (`logs/10_evidence_bench_run1.log`, exit 1):

| case | method(s) | assembly | decision | expected | cause |
|---|---|---|---|---|---|
| D2-proxyhandler-empty-dict | all 3 | plain | ORACLE_INCOMPLETE_REVIEW | SUFFICIENT_PER_ORACLE | subject D09 lacks "empty dictionary"; the context also holds the deprecated URLopener's D23 |
| D3-http-proxy-cgi | all 3 | plain | ORACLE_INCOMPLETE_REVIEW | SUFFICIENT_PER_ORACLE | default behaviour D10 and subject D09 lack "HTTP_PROXY" |
| S4-timeout-not-reads | all 3 | plain | ORACLE_INCOMPLETE_REVIEW | SUFFICIENT_PER_ORACLE | the negation S09 lacks "timeout" |
| S5-cjk-timeout | both FTS5 | both | ABSTAIN_NO_HITS | SUFFICIENT_PER_ORACLE | unicode61 makes the whole Japanese clause one token |
| S7-nfd-resume | literal | both | ABSTAIN_NO_HITS | SUFFICIENT_PER_ORACLE | NFC needle, NFD passage |
| S8-quota-readonly-budget | literal | both | ABSTAIN_NO_HITS | ABSTAIN_BUDGET | case-sensitive `quota` vs `Quota` |
| S8-quota-readonly-budget | both FTS5 | plain | ORACLE_INCOMPLETE_REVIEW | ABSTAIN_BUDGET | S13 fits alone (2000 B), its exception S14 is never retrieved |
| S9-pool-sizing-oversize | all 3 | plain | ORACLE_INCOMPLETE_REVIEW | ABSTAIN_BUDGET | S15 retrieved, omitted whole for budget; plain assembly has no budget-abstention label |

The method-level decision labels and their mapping to the oracle's expected decisions
(`CORRECT` in `scripts/evidence_bench.py`) were written after the pre-registration commit and
before run 1, and were not changed afterwards.

## 4. Data, provenance and license

* `fixtures/urllib_request_3.12_excerpts.txt`: 23 short excerpts (4,028 bytes) of the Python 3.12
  `urllib.request` docs, rendered from `Doc/library/urllib.request.rst` at python/cpython `3.12`
  commit `58ed60b7415e218ce3d608302e39b5e55bfb0e88`; the exact source lines are retained with
  hashes in `source/urllib.request.rst.excerpts.json`. **Disclosure:** the HTML page itself
  (`https://docs.python.org/3.12/library/urllib.request.html`) was refused by the session network
  policy (`logs/00_source_fetch_docs_python_org.log`), so the plain text is this benchmark's
  rendering of the page source and may differ slightly from the HTML text. Copyright PSF;
  PSF License Version 2, retained verbatim in `source/LICENSE-PSF-cpython-3.12`; attribution and
  the summary of changes in `source/NOTICE.md`.
* `fixtures/synthetic_cache_client.txt`: 16 synthetic passages (5,227 bytes), original, Apache-2.0.
* Offsets are UTF-8 byte offsets `[start, end)` into these plain-text files (never reST or HTML);
  `fixtures/passages.json` lists each passage's offsets, bytes, characters and sha256, and every
  result lists the selected passages the same way.
* Pre-registered in commit `2c6f091` (fixtures, oracle, block format, rules, builders, checker;
  `PREREGISTERED.sha256`) before the benchmark code existed. One disclosure: an environment probe
  run before that commit inserted two toy strings into FTS5 to confirm availability
  (`logs/00_environment.log`); it read no fixture.

## 5. Commands (Linux, from `research/public-evidence-spans-20261018-01/`)

| command | exit | log |
|---|---|---|
| `python3.12 scripts/build_fixtures.py extract <cpython checkout>` | 0 | `logs/01_source_extract.log` |
| `python3.12 scripts/build_fixtures.py check` and `python3.12 scripts/check_oracle.py` | 0, 0 | `logs/02_build_check_oracle.log` |
| `python3.12 scripts/evidence_bench.py results/run1-linux-py3.12` | 1 (22 disagreements, by design) | `logs/10_evidence_bench_run1.log` |
| `python3.12 -m unittest discover -s scripts -v` | 0 (16 tests) | `logs/11_unittest_run1.log`; run 2 after adding a `# ruff: noqa` comment line: `logs/11_unittest_run2.log` |

Environment: CPython 3.12.3 on Linux 6.18.44 x86_64 (glibc 2.39); SQLite 3.45.1 with
`ENABLE_FTS5`; both tokenizers available (`results/run1-linux-py3.12/environment.json`). If a
build lacks FTS5, the FTS5 methods are reported as `NOT_RUN` (tested), never replaced.

**Offline replay on macOS** (not run here; needs a Python 3.12 whose `sqlite3` has FTS5, e.g.
python.org or Homebrew; the benchmark reports what it finds):

```sh
git clone --branch claude/adoring-turing-3ekxhe https://github.com/gmfjc624d2-dot/trafilatura.git
cd trafilatura/research/public-evidence-spans-20261018-01
shasum -a 256 -c SHA256SUMS
python3.12 scripts/evidence_bench.py /tmp/evidence-replay; echo "exit=$? (1 expected)"
shasum -a 256 /tmp/evidence-replay/results.json results/run1-linux-py3.12/results.json
python3.12 -m unittest discover -s scripts
```

Identical `results.json` hashes mean an identical replay; a different SQLite version can change
BM25 scores or tokenization, which is then a finding, not a failure to hide.

## 6. Limits

* 17 hand-made cases over 39 short passages: a probe of failure modes, not an estimate of rates
  in real documentation. The oracle is the author's reading of these passages only.
* One query per case, written by the author; other phrasings would retrieve differently.
* No human semantic review was performed.
* Earlier evidence, left unmodified: the committed `research/techdoc-extraction-v2.3.1/ARTIFACTS.sha256`
  (commit `80c0550`) lists five files of a local, git-ignored `.ruff_cache/`; in a fresh clone
  those five lines report missing files while its other 89 entries verify. This increment's
  manifests are built from `git ls-files` to avoid that.

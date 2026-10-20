# Correction retrieval: content words, literal identifier and SQLite FTS5 on synthetic public records

Request: `public-correction-retrieval-experiment-20261020-01`.

This experiment turns the hypothesis of `5778f7a` into one small runnable test. That hypothesis
(`research/public-library-context-critique-20261020-01/REPORT.md`) says that a later change written
by identifier alone is missed by relating sources by content. Here the question is narrower: which
retrieval strategy finds which candidate passages, for an offline consumer of public documents.

**Evidence status:**
* The retrieval behaviour below was *observed* on Linux, on 12 invented records.
* The broader claim about real assistants or archives remains a *hypothesis*.
* This is not macOS qualification.

Candidate discovery is the whole task. Nothing classifies a relation, and no output states that a
target is corrected, accepted, authoritative or currently valid.

## 1. Chronology

| commit | content |
|---|---|
| `5778f7a62a870c2cce556fcf6980a48914eb9bc5` | the hypothesis (start: local = remote, no divergence, clean tree) |
| `fda5941ed5210d7fa09e63840508106d3cb77174` | pre-registration, before the experiment script existed: corpus, manifest, queries, methods, expected candidate sets, predicted findings, properties, limits |
| `ce9a1ff6defed71de4cd1a134ee14d8f2a4f42ef` | `scripts/correction_retrieval.py`, committed before its first run |
| the commit adding this file | `logs/10`, `logs/11`, `results/`, this report, `MANIFEST.md`, `SHA256SUMS` |

There was one primary run, on Python 3.12 (`logs/10`), and one compatibility replay, on Python 3.10
(`logs/11`). Both were offline (`unshare -rn`, `-I`). No earlier suite was re-run, and no earlier
research or production code was changed.

## 2. Corpus, queries and strategies

**The corpus.** `corpus/records/R01.txt` … `R12.txt` hold the source text. The exact corpus is
declared in `corpus/corpus.json`, which lists for each record:
* its id;
* its issuer;
* its declared date;
* the identifiers the record itself issues;
* its passages, one per paragraph, with byte ranges and sha256.

Nothing else is in the corpus. The roles below come from `fixtures/expectations.json` →
`evaluation_annotations`. They were used for grading only and are never read by discovery.

| record | issuer, declared date | role (evaluation only) |
|---|---|---|
| R01 | Library Board 2019-03-12 | proposal to move the reading room |
| R02 | Library Board 2019-05-14 | approval: agreement 14/2019, clauses 1-2 (the Q1 target) |
| R03 | Library Board 2019-08-26 | mere implementation citation of 14/2019 |
| R04 | Library Board 2019-11-19 | partial amendment of clause 2 only |
| R05 | Library Board 2020-01-10 | "This notice does NOT revoke agreement 14/2019." |
| R06 | City Council 2019-06-20 | the same number 14/2019, issued by a different body |
| R07 | Library Board 2020-02-11 | later full revocation by identifier alone: "Agreement 14/2019 is left without effect." |
| R08 | Library Board 2020-02-25 | invoice "14-2019" (different identifier form) |
| R09 | Library Board 2020-03-10 | reference to 22/2019, which no record issues (unresolved) |
| R10 | Library Board 2019-12-03 | agreement 114/2019 (contains "14/2019" as a substring) |
| R11 | Library Board 2021-06-15 | agreement 3/2021, the latest record (Q2: nothing later) |
| R12 | Library Board 2020-01-28 | suspension described without any identifier (added, to show the opposite miss) |

**The queries** (`fixtures/queries.json`). Each gives a target identifier, the issuer it is
attributed to, and a later question. The content words come from the question by a fixed stopword
rule.
* Q1: 14/2019, Library Board.
* Q2: 3/2021, Library Board.
* Q3: 22/2019, Library Board (no record issues it).

**The six strategies** run over every passage. The target record's own passages are shown as the
original and are not candidates.
1. `content_words_python`: shares at least one content word.
2. `literal_substring_reused`: the earlier `literal_search`, unchanged, which does plain substring
   matching.
3. `literal_bounded`: the identifier with no adjacent letter or digit.
4. `fts5_content_unicode61`: the content words joined by OR.
5. `fts5_identifier_unicode61`: the quoted identifier, which this tokenizer turns into the phrase
   `14 2019`.
6. `fts5_identifier_slash`: the same, with `tokenchars '/'`.

**Reuse.** Strategy 2 and the FTS5 quoting and availability probe (`fts_query`, `sql_string`,
`probe`) are taken from `research/public-evidence-spans-20261018-01/scripts/evidence_bench.py`. That
file (sha256 `b74774f1…`) and its `spans.py` (`6bc15cee…`) are executed from pinned, verified bytes.

The earlier script cannot express this experiment on its own:
* its fixtures have no issuer or declared date;
* its outcome is a sufficiency decision under a byte budget;
* it has no content-word strategy and no candidate-only reader output.

So `scripts/correction_retrieval.py` is a small new reference implementation. It uses the standard
library only, runs on Python 3.9+ and has no index service.

## 3. Results (`results/run1-linux-py3.12/`, observed)

Environment: Linux x86_64, CPython 3.12.3, SQLite 3.45.1 with FTS5. Both tokenizers were available.

**Graded checks: 41 pass, 0 fail, 0 not run; exit 0.** Every candidate set, reader fact and finding
matched what was pre-registered. These results describe how the strategies behave, not how good
they are. The negative outcomes are in the table and the findings below.

Q1 (Library Board 14/2019, target R02). Each strategy's candidate set:

| strategy | candidates | misses | off-target candidates |
|---|---|---|---|
| content_words_python | R01, R03, R04, R05, R09, R12 | **R07** (identifier-only revocation) | R09 (other agreement, shares "reading room") |
| fts5_content_unicode61 | R01, R03, R04, R05, R09, R12 | **R07** | R09 |
| literal_substring_reused | R03, R04, R05, R06, R07, R10 | **R12** (change without identifier) | **R10** (114/2019 substring), **R06** (same number, other body) |
| literal_bounded | R03, R04, R05, R06, R07 | **R12** | **R06** |
| fts5_identifier_unicode61 | R03, R04, R05, R06, R07, R08 | **R12** | **R08** ("14-2019" tokenized like "14/2019"), **R06** |
| fts5_identifier_slash | R03, R04, R05, R06, R07 | **R12** | **R06** |

(All candidates are paragraph `#p1`.)

**Q1 findings:**
* **The identifier-only revocation R07 is missed by both content-word strategies,** in Python and in
  FTS5. It shares no topic word with the question.
* **The change described without an identifier, R12, is missed by every identifier strategy.**
* **No single strategy returns all three later changes** (R04, R07, R12). The union of the six
  does. That is still not completeness.
* **Identifier search cannot tell the passages that mention 14/2019 apart.** All four identifier
  strategies return the implementation citation R03, the explicit "does NOT revoke" notice R05, the
  partial amendment R04 and the revocation R07. Retrieval does not separate them; reading does.
* **The issuer is ambiguous in every identifier strategy.** All four return R06, from another body
  with the same number. R07's own text ("Agreement 14/2019") does not name the body. The reader
  lists both issuers of 14/2019 and draws no conclusion.
* **The naive literal helper and the default tokenizer add irrelevant hits.** The reused substring
  helper returns 114/2019. The default FTS5 tokenizer returns invoice 14-2019. The bounded literal
  match and `tokenchars '/'` return neither.

**Q2 (3/2021, the latest record).** Every strategy returns zero candidates, and no record is
declared later. The reader says so, and adds: "This is not evidence that the target is current,
unchanged or valid".

**Q3 (22/2019).** No record issues 22/2019, so the target is reported unresolved. The identifier
strategies return only R09. The content strategies return 9 passages, 8 of which share only
"reading room".

**Properties:**
* **P1:** every shown passage equals the bytes at its locator.
* **P2:** no assertion-like key appears in result.json.
* **P3:** the determination is `NOT_MADE`, and the scope limitation appears in every query,
  including the empty one.
* **P4:** discovery is deterministic.
* **P5:** no strategy was substituted.

All five pass.

**Compatibility.** The Python 3.10.20 replay used a different SQLite (3.53.1). It had 0 differences
in the `result` section, and its reader output is byte-identical (`logs/11`).

## 4. The reader output (`results/run1-linux-py3.12/reader.md`)

The reader output has one section per query, with these parts:
* the question and its content words;
* an explicit uncertainty list;
* the declared scope;
* the original passages of the target;
* every candidate, quoted verbatim. Each carries its stable locator (`R07#p1`, file, byte range,
  sha256), issuer, declared date and date relation, the strategies that found and did not find it,
  and its identifier mentions, resolved against the manifest only;
* the records with no returned passage;
* the per-strategy table.

The determination is always NOT MADE.

`result.json` keeps two parts apart:
* `environment`: interpreter, platform, SQLite build and FTS5 probe;
* `result`: inputs with sha256, queries, candidates, reader sha256 and grading, which is
  platform-independent.

## 5. Correction to the earlier critique, and limits

**Correction.** The critique of `5778f7a` proposed answering "vigente en el ámbito X". That
overstates. A declared search scope does not prove:
* completeness;
* the absence of changes outside the scope;
* current normative validity.

No match inside the scope is not evidence that a target is current. So the reader here never says
"current within scope". It lists candidates, says nothing was determined, and states the limitation
for every query.

**What a match means.** A matching identifier, hash, issuer or later declared date is never treated
as an assertion of correction, acceptance, authority or validity. Dates and issuers are the records'
own declarations and are not verified.

**Other limits:**
* **Not a benchmark.** There are twelve invented English records and three queries, so this says
  nothing about real archives, other languages, OCR, scale or cost.
* **Tuned to this corpus.** The stopwords and the identifier form `n/yyyy` fit this corpus. There is
  no stemming, which is why "moving" does not match "move"; that is kept as part of the result.
* **What was graded.** bm25 order is recorded but not graded.
* **Unavailable FTS5.** If FTS5 or a tokenizer is unavailable, its strategies are `NOT_RUN` and the
  findings that involve them are reported as FAIL against the pre-registration, not hidden.
* **Python 3.9 was not executed.** No 3.9 interpreter exists in this container. The script is
  syntax-checked as 3.9 (`ast.parse(feature_version=(3, 9))`) and linted with ruff's `py39` target;
  3.10 is the lowest version actually run.
* **Platform.** These runs are Linux only and are not macOS qualification.
* **Cosmetic.** On empty results, `reader.md` places a heading directly after the "None returned"
  line. This was left as generated.
* **Pre-registration checksum defect.** `PREREGISTERED.sha256`, committed in `fda5941`, contains
  an entry for itself. It was hashed while the shell redirect was writing it, so that line can
  never verify. Its other 20 entries verify, and none of those files changed after `fda5941`
  (`git diff --name-only fda5941 HEAD` lists only files added later). The file is kept as
  committed; verify it without its self-line, as in section 6.

## 6. Replay (macOS or Linux, Python 3.9+, no dependency, offline after the clone)

```sh
git clone --branch claude/adoring-turing-3ekxhe https://github.com/gmfjc624d2-dot/trafilatura.git trafilatura-correction
cd trafilatura-correction && git checkout --detach <reported commit>
P=research/public-correction-retrieval-experiment-20261020-01; OUT="$HOME/correction-retrieval-$(date -u +%Y%m%dT%H%M%SZ)"
(cd "$P" && shasum -a 256 -c SHA256SUMS && grep -v ' PREREGISTERED.sha256$' PREREGISTERED.sha256 | shasum -a 256 -c)   # Linux: sha256sum -c
# disconnect the network from here on
python3 -I "$P/scripts/correction_retrieval.py" "$OUT" --against "$P/results/run1-linux-py3.12/result.json"; echo "exit=$?"
cmp "$OUT/reader.md" "$P/results/run1-linux-py3.12/reader.md" && echo "reader identical"
git status --short                                     # empty: nothing written into the clone
```

**The replay reproduces this result when:**
* it prints `{"PASS": 41, "FAIL": 0, "NOT_RUN": 0}` and `0 difference(s) in the result section`;
* it exits 0;
* `reader.md` is identical.

The `environment` block (Python, platform, SQLite version) is expected to differ and is not
compared. Anything else, such as FTS5 being unavailable, is a finding to report, not something to
edit.

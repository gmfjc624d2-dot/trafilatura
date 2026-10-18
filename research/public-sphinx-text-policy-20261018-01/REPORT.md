# Sphinx text policy: an independent text oracle and separate axes

This is a minimal successor of `research/public-sphinx-parser-corroboration-20261018-01`. The
predecessor is read-only, and its results are unchanged. There are three targeted changes:

* **T1** An independent text oracle replaces the incorrect itertext requirement.
* **T2** Three separate axes: the structural axis, the unchanged helper disposition, and a
  consumer gate that is never granted.
* **T3** The exact comparison scope is stated.

The parsers, the selection rule, the text rule, the comparison, the fixtures and the wheels are the
predecessor's. Its pinned module runs from verified bytes.

Nothing here is admission, a fit to any prompt or size limit, semantic sufficiency, or permission
to dispatch a model. Every report carries `consumer_gate.value = NOT_GRANTED`.

**These runs are Linux only.** The macOS replay reported for the predecessor was the user's run,
not repeated here, and it does not qualify this successor. These Linux runs do not qualify macOS
either. Section 7 gives the exact native macOS commands and the pass criteria.

## 1. Chronology and ancestry

| commit | content |
|---|---|
| `9ab18de157ce4ee33ecadea2b663b211a2560f63` | predecessor (local = remote at start; ancestry and tree checked, no concurrent change) |
| `db51165b856fca0de277d218aac0cc5e8e6b7d14` | pre-registration: `fixtures/expectations.json` (changes, witness, predictions, changed/unchanged fields, corrected R9, mutation controls, pins), the witness fixture, `scripts/build_witness.py`, `logs/01` |
| `a5b6a4dfc46bb06aafb3fb65ce84864590649359` | the budget witness on the **unchanged** predecessor: `scripts/witness_predecessor.py`, `results/witness-predecessor-linux-py3.12/W1.json`, `logs/10` |
| `0a38ec13e2f5691ec860e163b949ec4c080e726d` | `logs/15_design_addendum.md`: implementation choices left open by the pre-registration, before any successor code existed |
| `c38a2a22310eac751d398e3abd02dc507dc39fe3` | `scripts/text_policy.py`, `scripts/replay.py`, `scripts/test_text_policy.py`, committed **before** their first run |
| the commit adding this file | `logs/20`-`23`, `results/run1-linux-py3.12/`, this report, `MANIFEST.md`, `SHA256SUMS` |

`PREREGISTERED.sha256` holds the hashes of the 7 files committed in `db51165`. All of them are
unchanged.

Each was run once: the replay (`logs/20`) and then the tests (`logs/21`), both offline
(`unshare -rn`) and with `PYTHONDONTWRITEBYTECODE=1`. The two post-hoc logs (`22`, `23`) only read
files that already existed. Nothing was downloaded. No old corpus, live page, benchmark or model
was used.

## 2. T1: the text oracle

**Why the old check was wrong.** The predecessor checked
`html5lib_text_rule_equals_itertext` and turned a false value into `CONSISTENCY_CHECK_FAILED`.
On C2 that check failed. CPython 3.12's C-accelerated ElementTree `Element.itertext()` yields
comment data, while the pure-Python one does not (predecessor `logs/12`). itertext is therefore not
the intended rule, so it is no oracle for it.

**The rule** is unchanged. A unit's text is:
* each element's text, then each child's text and tail, recursively and in order;
* comment and PI payloads excluded, but their tails kept;
* the tails between top-level unit elements included;
* the last unit element's tail excluded.

**The oracle**, `oracle_text()` in `scripts/text_policy.py`, works like this:
1. It copies the unit's *native* nodes (lxml elements, or the ElementTree elements html5lib built),
   not the predecessor's node view.
2. In the copy, a node whose tag is a `str` becomes `<e>` with its text. Any other node (comment,
   PI, entity) becomes an empty comment. Every copy keeps its tail, and all of them sit inside one
   container.
3. The last unit element's tail is cleared.
4. The text is libxml2's XPath `string()` of the container.

It calls none of the rule's functions. A test runs it with the predecessor's `text_of` and
`unit_text` replaced by functions that raise.

If lxml refuses a string (NUL, U+000C, lone surrogates), the check is `null` and the finding
`CONSISTENCY_CHECK_UNAVAILABLE` gives REVIEW. A test shows this refusal and the resulting REVIEW.

**The two new checks.** `lxml_text_rule_equals_oracle` and `html5lib_text_rule_equals_oracle`
take the old check's place. A false value is `CONSISTENCY_CHECK_FAILED`, as before.

**itertext is still recorded.** For every unit, `observations.itertext` records whether itertext
equals the rule, whether it equals the rule with comment payloads, the text identity, and
`elementtree_c_accelerated`. It never produces a check or a finding.

**The oracle catches deliberate errors.** The mutation controls are M1-M4 (M0 is the
no-mutation control):
* M1: comment/PI payload included;
* M2: comment/PI tail dropped;
* M3: final tail included;
* M4: inter-unit tail dropped.

Results:

| units | oracle = rule | mutants the oracle tells apart | mutants equal to the rule (no evidence there) |
|---|---|---|---|
| C2, both trees | true | M1, M2, M3, M4 | - |
| N3, N4, N5, C1, W1, both trees | true | M3, M4 | M1, M2 (no comment or PI in the unit) |
| N1, N2, both trees | true | - | M1, M2, M3, M4 (no comment or PI, and the inter-unit and final tails are empty) |

At report level, two tests patch the predecessor's `unit_text` for one call:
* M1, M2, M3 and M4 on C2 each make both oracle checks false and add `CONSISTENCY_CHECK_FAILED`.
* M3 on the clean witness W1 turns STRUCTURE_CORROBORATED into REVIEW.

## 3. T2: the budget witness and the three axes

**The hypothesis held, on the unchanged predecessor** (`a5b6a4d`, `logs/10`). W1
(`fixtures/w1_long_clean.html`, 2820 bytes) is a clean long unit with these properties:
* no lxml diagnostic and no html5lib error;
* one exact match in each tree, with identical membership;
* a text of 2276 UTF-8 bytes in both trees.

The predecessor's `report()` gave STRUCTURE_CORROBORATED while the pinned helper said
`REVIEW_OVER_BUDGET` for both representations.

The predecessor replay's R9 is in its `scripts/replay.py`, lines 95-98:

    all(s == "OK_STRUCTURAL_UNIT" for s in statuses) or disposition == "REVIEW"

It is **False** there. That property is stronger than the predecessor's contract:
* its `disposition_rule` names no helper status;
* its required property R9 says only that the helper's reasons and status are "reported
  unchanged".

None of its fixtures was clean and over budget, so the stronger property never failed there. The
predecessor's results are kept as they are.

**The successor reports three axes:**
* `structural_corroboration`: the same disposition rule, plus an explicit guard that any helper
  reason gives REVIEW.
* `existing_helper`: the pinned `select_unit()` reasons, status and candidate, unchanged.
* `consumer_gate`: always `NOT_GRANTED`, with an explicit prohibition. No field (the structural
  disposition, `OK_STRUCTURAL_UNIT`, `REVIEW_OVER_BUDGET`) may be read as admission, as fitting a
  prompt, context or size limit, as semantic sufficiency, or as permission to send the unit or its
  source to a model.

**R9 is corrected in the successor** (`corrected_R9` in `fixtures/expectations.json`):
* (a) the reasons and status equal a fresh call of the pinned `select_unit()`;
* (b) any helper reason gives structural REVIEW;
* (c) the gate is NOT_GRANTED.

REVIEW_OVER_BUDGET may coexist with STRUCTURE_CORROBORATED, which then describes the structural
axis only. On W1, the replay finds corrected R9 true and the historical expression false (recorded,
not required).

## 4. T3: exactly what is compared

The text below is the `comparison_scope` of every report, equal to the pre-registered text.

**Compared between the two trees:**
* encoding (codec name);
* exact id matches (count) and the rule's structural reasons;
* for a selected unit:
  * membership: signature ids, signature and description counts, anchor position, nested object
    ids;
  * boundaries: the dl and its parent as kind/name/id/class, the kinds and names of all dl
    children, the unit's element indexes, neighbouring elements, the enclosing object id;
  * ordered topology of the unit: depth, node kind, mapped name, and only the id, class and href
    attributes of each node;
  * links: the href and text of each `a`;
  * the exact concatenated unit text.

**Not compared:**
* any other attribute (title, lang, style, data-*, ...);
* comment and PI payloads;
* where text sits inside the unit (only the concatenation is compared);
* anything outside the unit and its dl;
* the document head;
* the full DOM.

Parser diagnostics and errors are not compared with each other. Any diagnostic or error makes the
result REVIEW.

**Nothing is relaxed.** `compare()` is the predecessor's own function, run from its pinned bytes.
Every parser error, ambiguity (the exact-id rule is unchanged, and duplicates give no unit),
encoding disagreement and structural difference still gives REVIEW. No global diagnostic is
whitelisted. A replay property checks that the attributes compared are exactly id, class and href.

## 5. Results (`results/run1-linux-py3.12/`, `logs/20_replay_run1.log`)

Linux x86_64, Python 3.12.3, lxml 6.1.3, libxml2 2.14.6 (runtime and compiled), html5lib 1.1,
six 1.17.0, webencodings 0.5.1. ElementTree is C-accelerated. Before running, the replay checked
33 pinned files and found 0 differences. The three dependencies were zipimported from the pinned
wheel paths and their sha256 values matched.

**Replay: 186 pass, 0 fail, 87 recorded, exit 0.**

| case | structural axis | helper status (dom / text) | gate | findings (all as pre-registered) |
|---|---|---|---|---|
| N1 | REVIEW | REVIEW / REVIEW | NOT_GRANTED | LXML_DIAGNOSTICS_PRESENT, HTML5LIB_ERRORS_PRESENT |
| N2 | STRUCTURE_CORROBORATED | OK_STRUCTURAL_UNIT / OK_STRUCTURAL_UNIT | NOT_GRANTED | - |
| N3 | STRUCTURE_CORROBORATED | OK_STRUCTURAL_UNIT / OK_STRUCTURAL_UNIT | NOT_GRANTED | - |
| N4 | REVIEW | REVIEW / REVIEW | NOT_GRANTED | LXML_DIAGNOSTICS_PRESENT, HTML5LIB_ERRORS_PRESENT |
| N5 | STRUCTURE_CORROBORATED | OK_STRUCTURAL_UNIT / OK_STRUCTURAL_UNIT | NOT_GRANTED | - |
| C17 | REVIEW | REVIEW / REVIEW | NOT_GRANTED | LXML_DIAGNOSTICS_PRESENT, ID_NOT_UNIQUE, STRUCTURAL_REASONS_PRESENT (twice each) |
| C1 | REVIEW | OK_STRUCTURAL_UNIT / OK_STRUCTURAL_UNIT | NOT_GRANTED | HTML5LIB_ERRORS_PRESENT, MEMBERSHIP_DIFFERS, BOUNDARIES_DIFFERS, TOPOLOGY_DIFFERS |
| C2 | REVIEW | OK_STRUCTURAL_UNIT / OK_STRUCTURAL_UNIT | NOT_GRANTED | HTML5LIB_ERRORS_PRESENT (`CONSISTENCY_CHECK_FAILED` gone, as predicted) |
| W1 | STRUCTURE_CORROBORATED | REVIEW_OVER_BUDGET / REVIEW_OVER_BUDGET | NOT_GRANTED | - |

* **Unchanged fields.** For each of the eight regression cases, the replay compared the
  pre-registered unchanged fields with the committed predecessor report, using the pinned
  json-numeric comparator. Only environment.python, .platform and .machine were exempt. Each case
  had 0 differences. The compared fields:
  * environment, anchor, source, decoding_policy, parsers (all diagnostics and errors), name_mapping;
  * existing_helper, trees (selection, units, texts);
  * comparison agreements;
  * findings without `CONSISTENCY_CHECK_FAILED`;
  * the four predecessor checks;
  * the disposition.
* **Changed fields, as pre-registered:**
  * `request_id`;
  * the checks: itertext removed, two oracle checks added;
  * the new `observations`, `text_ledger`, `comparison_scope`, `structural_corroboration`
    (replacing `triage`) and `consumer_gate`.
* **Both oracle checks** are true for every unit, and `null` for C17, which has no unit.
* **itertext observation.** For html5lib on C2, itertext differs from the rule and equals the rule
  with comment payloads, as predicted. Every other html5lib unit is equal. For lxml (recorded, not
  predicted), itertext equals the rule everywhere, including C2: lxml's itertext skips comments.
* **W1.** Text of 2276 bytes with sha256 `51e00d9f…5b35` in both trees, link `#pkg.long` /
  `¶`, corrected R9 true, historical R9 false.
* **C1 html5lib errors** (`logs/23`, a read-only post-hoc comparison of the written report): they
  equal the corrected expectation `end-tag-too-early` for dd and then for div. The historical
  prediction (`unexpected-end-tag` for div) is still wrong, and it stays as historical evidence
  (FAIL in the predecessor).

**Focused tests: 11 run, 10 ok, 1 FAIL, exit 1** (`logs/21`). The failure is kept unchanged; see
section 6.

## 6. Every failure and negative result (all kept)

1. **Test FAIL:** `test_oracle_equals_the_rule_and_tells_every_mutant_apart_on_c2`.
   * **What failed.** The test asserted that the M3 mutant (final tail included) contains
     `MARK-TAIL-TAIL`. It does not. In C2, `MARK-TAIL-TAIL` is in the `<p>` *after* `</dl>`,
     line 12, while the dd's own tail is the single `"\n"` before `</dl>` (`logs/22`).
   * **The cause.** This is a wrong assumption in the test about the fixture, made when the test
     was written. The module is not at fault: the replay graded M3 as detected on C2 in both trees,
     and the report-level M1-M4 test passed.
   * **Not checked by this test.** Its remaining assertions, the loop showing every mutant differs
     from the oracle, did not run after the failure. The replay's graded mutation checks cover the
     same facts.
   * **Not fixed and not re-run**, to keep the one-run rule. The correction would be to assert that
     the M3 mutant equals the rule plus `"\n"`. It was not applied.
2. **Uninformative controls.**
   * On N1 and N2, all four mutants equal the rule, so those units give no evidence that the oracle
     discriminates.
   * M1 and M2 are discriminated only on C2. It is the only unit with comment or PI nodes.
3. **The oracle's PI branch has not been exercised.** In HTML mode, libxml2 2.14.6 turned C2's
   `<?pi …?>` into a comment: the C2 lxml text ledger has 2 comments and 0 PIs, like html5lib. No
   fixture gives a real PI node to either tree.
4. **The oracle checks composition, not the parsers' strings.** It uses the same text and tail
   strings the parser produced. So it checks:
   * order;
   * payload exclusion;
   * tail inclusion and exclusion;
   * the final-tail rule.

   It cannot detect a parser that produced wrong text. Two-parser disagreement covers that, within
   `comparison_scope`. On the lxml tree, both the oracle and the helper's `text_content()` are
   libxml2 code: the oracle is independent of the Python rule, not of libxml2.
5. **Unpredicted observations, recorded.** lxml itertext equals the rule on C2. html5lib keeps
   comment payloads in the ElementTree comment `.text`.
6. **Predecessor results unchanged.** Its 2 test failures (the itertext assumption) and 2 replay
   failures (the C1 code prediction and the C2 itertext check) are unchanged. This successor
   supersedes the assumption behind them; it does not edit them.

## 7. Limits

* The runs are Linux only (one interpreter and one libxml2 build). macOS is not qualified by
  anything here.
* lxml is the platform binary. It is identified by version (lxml, libxml2 runtime and compiled) and
  path in the log, not by a hash.
* The scope is nine small synthetic fixtures (eight reused, one new). It is not a corpus,
  benchmark, real documentation site or security boundary.
* STRUCTURE_CORROBORATED means two repaired interpretations agree on `comparison_scope`. It does
  not mean source truth or completeness.
* No text normalisation and no source byte positions are used.
* The report keys exclude `span|offset|occurrence|byte_start|byte_end|fits|budget` (a replay
  property). Helper status values such as `REVIEW_OVER_BUDGET` are reported unchanged as values.

## 8. Identities, dependencies and licenses (by reference)

* **Pinned, checked at run time** (sha256 in `fixtures/expectations.json` → `pins`):
  * the predecessor `corroborate.py` (`4b5e7914…4b1d`), `replay.py`, `expectations.json` and
    `verify_wheels.py`;
  * `anchor_unit.py` (`9c013517…04e9`);
  * the json-numeric `compare_results.py` (`29267d53…6e19`);
  * the three wheels, `WHEELS.json`, `requirements.lock` and the four license files;
  * the nine fixtures and the nine committed predecessor result files.

  `summary.json` → `implementation` also records the sha256 of the successor scripts as run.
* **Dependencies:** the predecessor's retained wheels, imported only through zipimport. They are:
  * `html5lib-1.1-py2.py3-none-any.whl` (`0d78f8fd…041d`);
  * `six-1.17.0-py2.py3-none-any.whl` (`4721f391…3274`);
  * `webencodings-0.5.1-py2.py3-none-any.whl` (`a0af1213…2a78`).

  There is no install and no new package.
* **Licenses:**
  * html5lib (MIT, with its AUTHORS), six (MIT) and webencodings (BSD) are in
    `research/public-sphinx-parser-corroboration-20261018-01/wheels/licenses/`, with provenance in
    that directory's `REPORT.md` section 1 and `wheels/WHEELS.json`.
  * lxml (BSD-3-Clause) and libxml2 (MIT) are the user's platform installs, not redistributed here.
  * This repository's code is under its root `LICENSE` (Apache-2.0).

## 9. Commands

### Linux (executed here, from this directory)

| command | exit | log |
|---|---|---|
| `python3 scripts/build_witness.py build` / `check` | 0 | `logs/01_build_witness.log` |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<3 wheels> unshare -rn <lxml venv>/bin/python -W default scripts/witness_predecessor.py results/witness-predecessor-linux-py3.12/W1.json` | 0 | `logs/10_witness_predecessor.log` |
| `… scripts/replay.py results/run1-linux-py3.12` | 0 | `logs/20_replay_run1.log` |
| `… -m unittest discover -s scripts -v` | 1 (1 kept failure) | `logs/21_unittest_run1.log` |

`<3 wheels>` is the three `.whl` paths in
`research/public-sphinx-parser-corroboration-20261018-01/wheels/`, joined by `:`. The lxml venv
holds only lxml 6.1.3. Under `-W default` no warning was printed.

### macOS (native, Python 3.12 with lxml; not run here)

Retrieve the branch and check out the exact commit that was reported. Run offline after the clone.
Outputs go outside the clone:

```sh
git clone --branch claude/adoring-turing-3ekxhe https://github.com/gmfjc624d2-dot/trafilatura.git "$HOME/trafilatura-text-policy"
cd "$HOME/trafilatura-text-policy" && git checkout --detach <reported commit> && git log -1 --format=%H
RES="$PWD/research"; R="$RES/public-sphinx-text-policy-20261018-01"; W="$RES/public-sphinx-parser-corroboration-20261018-01/wheels"
OUT="$HOME/text-policy-replay-$(date -u +%Y%m%dT%H%M%SZ)"; PY=python3.12   # the interpreter where `import lxml` works
cd "$R" && shasum -a 256 -c SHA256SUMS && shasum -a 256 -c PREREGISTERED.sha256
# disconnect the network from here on
ZP="$W/html5lib-1.1-py2.py3-none-any.whl:$W/six-1.17.0-py2.py3-none-any.whl:$W/webencodings-0.5.1-py2.py3-none-any.whl"
"$PY" -c "import sys, lxml, lxml.etree as e; print(sys.version, lxml.__version__, e.LIBXML_VERSION, e.LIBXML_COMPILED_VERSION)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ZP" "$PY" -W default scripts/replay.py "$OUT/run" --against results/run1-linux-py3.12; echo "exit=$?"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ZP" "$PY" -W default -m unittest discover -s scripts -v; echo "exit=$?"
git status --short                                # empty: nothing written into the clone
```

Do not pass `-I`, because it ignores `PYTHONPATH`. The replay itself re-checks every pin and that
each dependency came from its wheel path.

**Pass criteria for a macOS qualification of this successor:**
* The replay prints `pins: 33 files checked, 0 differ`, three `zipimported … =True … matches
  pin=True` lines, totals `{"PASS": 186, "FAIL": 0, "RECORDED": 87}`, and
  `compare …: 0 difference(s)` for each of the 10 committed JSON files (9 reports and
  `summary.json`). It exits 0.
* The tests run 11, with exactly the one kept FAIL above, and exit 1.
* `git status --short` is empty.

Anything else (another lxml or libxml2 version, a pure-Python ElementTree, a different error list)
is a finding to report, not something to edit.

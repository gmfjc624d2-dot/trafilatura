# Evidence integrity of the Sphinx anchor-unit helper

Request `public-sphinx-evidence-integrity-20261018-01`, continuing `7345bfea30ce378dfd91d5121a10dd2db2fb8f1d`.
A narrow repair of three evidence-integrity defects in the research helper of
`../public-sphinx-anchor-units-20261018-01` (read, never written). The selection rule is unchanged.
**Linux evidence only** (Python 3.12.3, lxml 6.1.3, libxml2 2.14.6, x86_64). A structurally complete
unit is not evidence that a passage answers any question; nothing was semantically reviewed.

Order of work, each step pushed before the next: pre-registration `d386b49` (fixtures,
expectations, verbatim baseline copies, byte checker), baseline reproduction `9004016` (only the
unmodified 7345bfe copies ran), then the repair with its results, then a fresh-clone check.

## 1. Parser diagnostics (D1 → R1)

**Baseline, reproduced.** `build_candidate()` kept a diagnostic only when its line lay between the
unit's first and last *element start* lines. For the supplied `pkg.late` page (N1) every unit element
starts on line 1, while the `dd` text runs to line 5; libxml2 reports the stray `</span>` at line 3,
column 5 (`ERR_TAG_NAME_MISMATCH`, "Unexpected end tag : span"). The baseline dropped it and returned
`OK_STRUCTURAL_UNIT` for both representations. A diagnostic outside the unit (N4, line 12) was ignored
the same way.

**Repaired.** Any entry in the document's error log, at any line, adds `PARSER_DIAGNOSTICS_PRESENT`,
so every representation is `REVIEW`. No line range, no end range from start lines, no exempted page.
The candidate is still built and kept whole. Its context sizes are computed, and its context text is
withheld, as for every review case. `parser.diagnostics` keeps every entry with line, column, level,
type and message; it equals the error log of an independent parse of the same bytes.
`PARSER_RECOVERY_IN_UNIT` and `candidate.diagnostics_in_unit_lines` are gone.

| case | baseline | repaired |
|---|---|---|
| N1 `pkg.late` (supplied input 1) | OK / OK, diagnostic dropped | REVIEW / REVIEW, `PARSER_DIAGNOSTICS_PRESENT`, whole `dd` kept incl. "Third line of description." |
| N4 `pkg.inside`, diagnostic outside the unit | OK / OK | REVIEW / REVIEW |
| N5 `pkg.clean`, N4 without the stray tag (control) | OK / OK | OK / OK |
| old C17 (duplicate id), C21, C22, C23 (malformed f6) | reasons as committed | the same reasons plus `PARSER_DIAGNOSTICS_PRESENT`; for C23 it replaces `PARSER_RECOVERY_IN_UNIT` |

The rule is deliberately conservative: a single diagnostic anywhere on the page sends every anchor on
that page to review. It still cannot see recoveries that libxml2 makes silently (omitted `</dt>`,
`</dd>`, raw `&` and `<`). Only the structural rules catch those, as before (C21).

## 2. No byte span: identities kept apart (D2, D2b → R2, R3)

**Baseline, reproduced.** `raw_byte_span` came from `data.count()`/`data.find()` of the serialization:

* N2 `pkg.target` (supplied input 2): the live `dd` holds `&#65;`, which serializes as `A`. The only
  literal match of the serialization is at bytes 66-142, inside the comment (62-145), not at the live
  `dt` (169-249). The baseline reported 66-142 as the unit's raw span.
* N3 `pkg.legacy` (windows-1252, declared with `<meta charset>`): the rule and tests of the previous
  increment say the UTF-8 serialization is searched. The code encoded it with `docinfo.encoding`
  instead. The claimed span 126-244 therefore holds 118 windows-1252 bytes, while the reported
  `dom_bytes` is 125 UTF-8 bytes. The span's bytes are not the serialization whose sha256 is reported.

**Repaired.** No span, offset or literal occurrence count is produced: `raw_byte_span` and
`raw_occurrences_of_serialization` are removed. No output key of the 32 repaired outputs (5 new, 27
old) matches `span|offset|occurrence|byte_start|byte_end|in_unit`. No tokenizer or source map was
built, so the helper now makes no source-location claim except element start lines, which stay
labelled "not byte offsets". Three identities are kept apart (`identity_definitions` in the results):

* **file**: `source.sha256` and `source.bytes`, the retained bytes exactly as received.
* **DOM**: `candidate.dom_sha256` and `dom_bytes`, the UTF-8 encoding of the unicode serialization,
  whatever the document encoding.
* **text**: `candidate.text_sha256` and `text_bytes`, the UTF-8 encoding of `text_content()`.

`parser.encoding` only reports how the file was decoded (`windows-1252` for N3, whose text decodes
correctly as "Café costs 5 €, “quoted”."). For N2 and N3 the three sha256 values are pairwise
different and each can be recomputed from the output.

## 3. Comparison (D3 → R5)

**Baseline, reproduced.** `compare_results.py` said it ignored only the platform fields. In fact it
compared a digest that leaves out:

* case id, anchor, source identity and parser encoding;
* diagnostic column, level and message;
* candidate kind and the payload texts;
* context text and check details.

It never compared the environment (library versions included), treated `true` as `1` and `1` as
`1.0`, and crashed on a different result count. On 32 pre-registered mutations of the committed
results it **missed 23** and crashed on 1 (M18, `ValueError` from `zip(strict=True)`).

**Repaired** `scripts/compare_results.py` compares two JSON documents completely and recursively:

* the JSON type at every path (`true`, `1` and `1.0` are three different values);
* object keys and their order;
* array length and order;
* every scalar.

Duplicate object keys and NaN/Infinity make an input invalid (exit 2). The only exceptions are the
values at `$.environment.python`, `$.environment.platform` and `$.environment.machine`. Their keys
must still exist on both sides, and library versions are not exempt. Mutation outcomes:

| mutation controls | repaired | baseline 7345bfe |
|---|---|---|
| M00 identity, M01-M03 python/platform/machine | allowed | allowed |
| M04-M14, M16, M19-M28: library versions, missing exempt key, case id, anchor, source sha256/path, encoding, diagnostic message/column/level/order, swap of two results with equal digests, added/removed keys, `true`→`1`, `989`→`989.0`, context/payload text, check detail, key order | detected, at the pre-registered paths | missed (22) |
| M15, M17, M29, M30: diagnostic removed, results swapped, reason order (with python changed), status | detected | detected |
| M18 last result removed | detected (`$.results` length) | crash |
| M31 duplicate key in the JSON text | rejected (exit 2) | missed (the 23rd) |

## 4. Research context budget (R4)

`context_bytes` counts only the research context built from the unchanged template: query line,
source identity, origin, unit and representation labels, and payload. Every `contexts` entry now
carries `scope`, which says so. A real caller's question, instructions, system prompt and message
wrappers are not counted, so `fits` is no admission decision for any caller and nothing here claims
universal admission. The template is byte-identical to the previous one, so all 27 old contexts kept
their exact bytes, sha256 and `fits`.

## 5. Results and every failure

* Reproduction (`logs/10_reproduce_baseline.log`): 145 checks, 0 findings. The 14 failures are the
  predicted baseline requirement failures, kept: N1 and N4 fail `reasons`, `status`,
  `no_alignment_claim` and `budget_scope`; N2, N3 and N5 fail `no_alignment_claim` and
  `budget_scope`. The 27 baseline outputs equal the committed entries exactly.
* Repair run (`logs/21_run_experiment_run1.log`, `results/run1-linux-py3.12/`): 386 checks, 369 pass,
  0 findings. The 17 failures were all predicted and are kept:
  * the same 14 baseline requirement failures;
  * **C01 and C12**: the previous increment's predictions that their DOM contexts fit still fail
    (2054 and 2187 bytes > 2048), unchanged and not edited;
  * **C23**: the previous expectation names `PARSER_RECOVERY_IN_UNIT`, which R1 superseded.
  * 7 old raw-region checks are not applicable after R2.
  * All 27 repaired outputs equal the pre-registered transform T of the committed entries. All 27
    statuses are unchanged.
* **Attempt 1 crashed** (`logs/20_run_experiment_attempt1_crash.log`, kept). The strict comparator
  raised `TypeError` on the in-memory helper output: `near_matches` come from `xpath("//@id")` as
  lxml's `_ElementUnicodeResult`, a `str` subclass. Refusing non-JSON types is intended. The runner
  and the tests now compare outputs after a JSON round trip (`compare_results.as_json`), which is
  what the result files record. No helper output and no prediction changed. A test documents the
  case.
* Focused tests (`logs/22_unittest_run1.log`): 20 tests, OK, offline. These include the
  negative controls on the baseline copies and both command-line comparators on all 32 mutations.
* Lint and format of this directory only (ruff 0.16.10, `--no-cache`, `ruff.toml` extending the
  project's): clean before each logged run. No repository-wide suite or lint was rerun.

## 6. Limits

* R1 trades recall for safety: pages with any diagnostic need a review decision, which the helper
  never makes. Diagnostics are specific to the libxml2 version.
* Without spans, a reader who needs a source location has only element start lines. A real
  node-to-source mapping would need a tokenizer or source map, which this repair does not build.
* One non-UTF-8 case: a declared windows-1252 page under libxml2 2.14.6. Undeclared or other
  encodings were not tested.
* The comparator compares JSON documents. In-memory values must be serialized first (`as_json`).
* macOS was not run here. The 27-case macOS replay quoted in the request is the user's result, not
  this session's.

## 7. Scope, provenance, commands

Changed: only `research/public-sphinx-evidence-integrity-20261018-01/`. Every earlier research
directory and all project code are byte-identical to `7345bfe`. N1 and N2 are the public synthetic
inputs supplied with the request, written character for character: UTF-8, LF line ends, no final
newline (`logs/01_build_check_fixtures.log` shows them with `cat -A`). N3-N5 are original synthetic
pages (Apache-2.0). The 27 old cases read the previous directory's fixtures and the NumPy page
(BSD-3-Clause, provenance there), all sha256-pinned. No network, no installs: the local venv of the
previous increment (`logs/00_environment.log`). All runs were inside `unshare -rn`.

| command (Linux, from this directory) | exit | log |
|---|---|---|
| `python3.12 scripts/build_fixtures.py check`; `python3.12 scripts/check_fixtures.py` | 0; 0 | `logs/01_build_check_fixtures.log` |
| `<venv3.12>/bin/python scripts/reproduce_baseline.py results/baseline-linux-py3.12` | 0 | `logs/10_reproduce_baseline.log` |
| `<venv3.12>/bin/python scripts/run_experiment.py results/run1-linux-py3.12` | 1 (crash), then 0 | `logs/20_…attempt1_crash.log`, `logs/21_run_experiment_run1.log` |
| `<venv3.12>/bin/python -m unittest discover -s scripts -v` | 0 (20 tests) | `logs/22_unittest_run1.log` |

The scripts create mutated copies in a temporary directory and remove it themselves. Nothing in
the repository or in any verification clone is deleted.

**macOS Python 3.12 with an existing lxml (not run here):**

```sh
git clone --branch claude/adoring-turing-3ekxhe https://github.com/gmfjc624d2-dot/trafilatura.git trafilatura-integrity-replay
cd trafilatura-integrity-replay/research/public-sphinx-evidence-integrity-20261018-01
shasum -a 256 -c SHA256SUMS && shasum -a 256 -c PREREGISTERED.sha256
python3.12 -c "import lxml, lxml.etree as e; print(lxml.__version__, e.LIBXML_VERSION)"
python3.12 scripts/build_fixtures.py check && python3.12 scripts/check_fixtures.py > /dev/null; echo "exit=$?"
git status --short .   # empty: check_fixtures.py rewrote byte_facts.json identically
python3.12 scripts/reproduce_baseline.py "$HOME/integrity-replay/baseline"; echo "exit=$? (0 expected)"
python3.12 scripts/compare_results.py results/baseline-linux-py3.12/baseline_reproduction.json "$HOME/integrity-replay/baseline/baseline_reproduction.json"
python3.12 scripts/run_experiment.py "$HOME/integrity-replay/run"; echo "exit=$? (0 expected)"
python3.12 scripts/compare_results.py results/run1-linux-py3.12/results.json "$HOME/integrity-replay/run/results.json"
python3.12 -m unittest discover -s scripts -v
```

Only lxml is needed (Trafilatura is not imported). `compare_results.py` exits 0 only if nothing but
the three environment values differs. Any other difference is a finding to report, for example
another libxml2 reporting other diagnostics. It is never a reason to edit expectations.

**Earlier disclosure, unchanged:** the final check of the evidence-span increment, a fresh clone of
`e7d2f5c` whose hashes all verified, ended with `pwd: error retrieving current directory: getcwd ...`
because its own cleanup deleted the working directory. That result was reported in chat only and
stays as it was.

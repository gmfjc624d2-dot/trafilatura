# Exact numbers for the JSON result comparator

Request `public-json-numeric-integrity-20261018-01`, continuing `b4fa1424ead6fe23e93ed1ca6a698e401f2b403b`.
The branch had not moved: local and remote heads were both `b4fa142` and `7345bfe` is its ancestor
(`logs/00_identity_environment.log`). This is a small standard-library repair of
`research/public-sphinx-evidence-integrity-20261018-01/scripts/compare_results.py` (sha256
`9a7933f8…`, git blob `89a24718…`), kept verbatim here as `scripts/compare_results_baseline_9a7933f.py`.
The successor is `scripts/compare_results.py` (sha256 `29267d53…`). **Linux evidence only**
(Python 3.12.3, libmpdec 2.5.1, x86_64). It is not native qualification on macOS and not adoption.
The earlier directories are unchanged.

Order of work, each step pushed before the next:

* `5c3e94f`: pre-registration (references, measurement, limits, policy, 100 fixtures, expectations).
* `f667484`: the baseline run on every case, before any repaired code existed.
* the repair with its tests and results.
* a fresh-clone check.

## 1. The defect, reproduced on the baseline

The baseline parsed fraction and exponent tokens with `float`, so different numbers collided
(`results/baseline-linux-py3.12/cases.json`, exit codes of the CLI):

| family | committed / replay | baseline (float) | repaired (Decimal) |
|---|---|---|---|
| overflow | `{"x":1e400}` / `{"x":2e400}` | 0, equal (both `inf`) | 1, `1E+400` vs `2E+400` |
| overflow | `1e400` / `1e9999` | 0 | 1 |
| underflow | `1e-4000` / `2e-4000` | 0 (both `0.0`) | 1 |
| underflow | `1e-4000` / `0.0`, `-1e-4000` / `-0.0` | 0 | 1 |
| finite rounding | `9007199254740993.0` / `9007199254740992.0` | 0 | 1 |
| finite rounding | `0.1` / `0.10000000000000001`; two 40-digit values differing in the last digit | 0 | 1 |
| retained data | a bm25 score in the evidence-spans results, `-0.48514337270399616` → `…617` | 0 | 1 (one difference) |

Other baseline defects, all kept:

* Inputs just over every limit were accepted (exit 0).
* 100000 nested arrays ended in a `RecursionError` traceback with exit 1, which a caller would read
  as "different".
* A string holding a lone surrogate escape crashed the diagnostic `print` (`UnicodeEncodeError`).
* A nested `1e400` at an exempt path was displayed as `Infinity`, which is not a JSON number.
* In process, the baseline compared native floats, recursed into a `RecursionError` at depth 5000,
  and left NaN to be rejected only by accident and `Decimal` only through an implicit `TypeError`.

The baseline got spellings (`1.0`/`1.00`/`1e0`), signed zeros, categories, duplicates, NaN
literals, malformed text and the interpreter's 4300-digit integer limit right. The repair keeps
all of them.

## 2. The contract as implemented

1. **Parsing.** `json.loads` runs with `parse_int`, `parse_float`, `parse_constant` and
   `object_pairs_hook` hooks (`PARSE_HOOKS`). An integer token becomes `int(text)` and a fraction or
   exponent token becomes `Decimal(text)`, both after the limits in item 6. The JSON types
   `boolean`, `integer` and `decimal` never compare equal. Duplicate keys and the literals `NaN`,
   `Infinity` and `-Infinity` are invalid. `1e400` is an ordinary finite token. The hooks accept only
   ASCII JSON number characters. On v3.12.3 the pure-Python fallback scanner hands non-leading
   Unicode digits to the hooks: `[1١]` gives `[11]` with default hooks (`logs/11_…`). The
   `Decimal` and `int` constructors would also accept underscores.
2. **Decimal equality** is `a == b` (exact) plus `a.is_signed() == b.is_signed()` when both are zero:
   * `1.0`, `1.00`, `1e0` are equal, and so are `1e400` and `10e399`;
   * `0.0` differs from `-0.0`, while `-0.0` equals `-0e0`;
   * integer `-0` is `int` 0 and equals `0` (legacy policy).

   The code uses no `compare_total`, no spelling comparison, no `normalize`, `quantize` or unary
   plus, and no float; a test checks the source for these. It does no context arithmetic. Under a
   caller context with `prec=1`, `Emax=1`, `Emin=-1` and every signal trapped, every verdict equals
   the default-context verdict, `1.1` still differs from `1.2`, and the caller's context object,
   precision, traps and flags are unchanged (A01, tests). The fixture bytes are kept as written; no
   claim is made that equal values have equivalent spellings.
3. **Structure is unchanged.** The comparison covers:
   * the JSON type at every path;
   * object key sets **and** key order;
   * array length and order;
   * every scalar.

   Only the values at `environment.python`, `.platform` and `.machine` may differ. A missing exempt
   key is still a difference, and a field with the same name elsewhere (`other.python`) is not
   exempt. The useful signatures are kept: `compare(a, b, exceptions=ENVIRONMENT_EXCEPTIONS, path=())`,
   `loads(text)` (now also UTF-8 bytes), `load(path)`, `as_json(value)`, `json_type(value)`,
   `render(path)`, `lookup(doc, path)`, `short(value)`, `main(argv=None)`, `InvalidJSONError`.
   `LimitExceededError` and `UnsupportedValueError` (a `TypeError` as well, as before) are new.

   **Changed for in-process callers:**
   * `compare()` now rejects native floats, non-finite `Decimal` and other non-JSON values with
     `UnsupportedValueError`;
   * `json_type()` names `decimal` where the baseline named `float`;
   * containers deeper than 32 raise `LimitExceededError`.
4. **Native objects (`as_json`)** do `json.dumps(value, ensure_ascii=False, allow_nan=False,
   default=<reject>)` and then the exact parser.
   * str subclasses (lxml's `xpath()` strings) still become `str`.
   * A Python float is compared by the text `json.dumps` emits for it, so `0.1` becomes
     `Decimal('0.1')` and not its binary value `0.1000000000000000055511…`.
   * Precision lost when the float was made is not recovered: `9007199254740993.0` is already the
     float `9007199254740992.0`, so the two compare equal after `as_json` (A03, tests).
   * `nan`, `inf` and native `Decimal` are rejected explicitly. Nothing is converted to float or
     stringified.
5. **Diagnostics are display data**, never compared:
   * a decimal is shown with `str()`: finite, every digit, a valid JSON number (`1E+400`, `-0`,
     `0.000`); a test parses each one back to the same coefficient and exponent;
   * numbers and containers are never cut;
   * a string longer than 160 characters is cut and labelled with its length and a sha256 prefix;
   * text that cannot be encoded as UTF-8 is shown with `\u` escapes;
   * value tags name the JSON type (`decimal value`), because `str(Decimal('1e0'))` is `1`;
   * the CLI exits 0 (equal), 1 (different) or 2 (invalid, unreadable or unsupported); every limit
     and the recursion case are exit 2 with a message and never a traceback.
6. **Limits** were recorded before the repair (`fixtures/expectations.json`). They are sized from
   the 33 retained JSON files (`results/measurement/retained_json.json`):

| limit | value | measured max | enforced | just-over control |
|---|---|---|---|---|
| input bytes | 4194304 (4 MiB) | 246236 | on the bytes read (at most limit + 1), before UTF-8 decoding | G02 (+1 byte) |
| nesting depth | 32 | 7 | after parsing (iterative) and in `compare()`; a decoder `RecursionError` is reported as a limit | L12 (33), G04 (100000) |
| number token characters | 48 | 20 | in the hook, first | L10 (49), G03 (5000) |
| integer digits | 40 | 6 | in the hook, before `int()` | L02 (41) |
| coefficient digits | 40 | 18 | in the hook, before `Decimal()` | L04 (41) |
| exponent digits (text) | 4 | 0 | in the hook, on the text, before any conversion | L07 `1e10000`, L08, L09 `1e00001` |

`1e400`, `2e400`, `1e-4000`, `2e-4000`, `1e9999` and `1e-9999` are admitted. A test patches the
module's `int` and `Decimal` and shows that neither runs for a rejected token. The interpreter's
4300-digit protection is not changed. **Stated limit:** the hooks run after the json scanner has
matched the whole token, so that scan is bounded only by the byte ceiling. This is no lexical
parser and no safety claim for arbitrary input.

## 3. Documented, policy, executed

| statement | kind | where |
|---|---|---|
| `parse_float` / `parse_int` get "the string of every JSON float/int"; `parse_constant` gets the three constants | documented | `json.rst` L289-310 (v3.12.14) |
| the C scanner passes the matched substring to custom hooks; nested containers use `_Py_EnterRecursiveCall` | documented (source) | `_json.c` L967-981, L1043-1056 |
| json imposes no limits beyond those of the interpreter, and recommends limiting the input size | documented | `json.rst` L22-24, L705-706 |
| `Decimal(str)` stores every digit regardless of context precision; the context only decides about malformed strings | documented | `decimal.rst` L382-390 |
| signed zeros "are treated as equal and their sign is informational" | documented | `decimal.rst` L1839-1842 |
| `str` to `Decimal` is **not** covered by the 4300-digit limit | documented | `stdtypes.rst` L5589-5606 |
| exact equality plus sign for zeros; the limits; ASCII-only tokens; rejecting native Decimal | policy | `fixtures/expectations.json` |
| `Decimal('1e999999999999999999')` constructs although the default `Emax` is 999999, `Decimal('1e9999999999999999999')` is `InvalidOperation` (or NaN untrapped), and 100000 nested arrays raise `RecursionError` | executed, Linux 3.12.3 | `results/*/interpreter_observations.json` O2-O4 |

All references were read at CPython tags v3.12.14 and v3.12.3 (`references/REFERENCES.md`), because
`docs.python.org` was refused here.

## 4. Results and every failure

* **Baseline** (`logs/10_run_cases_baseline.log`): 275 graded checks, 0 differ from their
  predictions. 30 failures were predicted and are kept:
  * 18 CLI requirement outcomes: K01-K08, L02, L04, L07-L10, L12, G02, G04, D01;
  * 11 in-process requirements: A01, A03-A06, A08-A11, A14, A16;
  * the bm25 mutation S02d.
* **Repair** (`logs/20_run_cases_repaired_run1.log`, `results/run1-linux-py3.12/`): 188 graded
  checks, 186 pass, and all 66 CLI outcomes are right.
  * 2 findings, kept: the expected display text I pre-registered for I07 and I10 was wrong. I wrote
    `(committed): codec can't decode…` and `(committed): No such file…`, but the messages read
    `'utf-8' codec can't decode byte 0xff…` and `[Errno 2] No such file or directory: …`. The
    comparator's outcome is right (exit 2, no traceback), and the comparator was not changed to
    match the wording.
  * All 16 in-process cases, 33/33 retained self-comparisons, the 2 largest files through the CLI,
    and the 5 derived mutations pass.
* **Interpreter observation O1 failed in both runs**, kept: I predicted that v3.12.3's pure-Python
  scanner would accept `[١]`. Its pattern needs an ASCII first digit, so it does not; a
  post-hoc log, labelled as such, shows the non-leading case.
* **Focused tests** (`logs/21_unittest_run1.log`): 27 tests, OK, offline. They include negative
  controls on the baseline.
* **Lint and format** of this directory only (ruff 0.16.10, `--no-cache`): clean before each logged
  run. No earlier experiment, fixture builder or test suite was rerun; the earlier results were
  only read.

## 5. Limits of this work

* One interpreter: Linux 3.12.3 with libmpdec 2.5.1. The recursion depth that fails, the scanner
  fallback and libmpdec can differ elsewhere.
* The comparator compares JSON documents. Floats made before `as_json` keep the precision they
  have.
* Integer `-0` equals `0` by policy, so a replay that turns `-0` into `0` is not reported.

## 6. Scope, provenance, commands

Changed: only `research/public-json-numeric-integrity-20261018-01/` (`logs/22_scope_check.log`).
Fixtures are original synthetic texts; the two the request named are byte-exact
(`{"x":1e400}`, `{"x":2e400}`, no final newline). The 33 retained result files belong to the earlier
increments and are only read, sha256-pinned in the measurement. No network beyond fetching the
public CPython sources. No new dependency: system `/usr/bin/python3.12`, standard library only. All
runs were inside `unshare -rn`. The runner and tests create their generated large inputs in a
temporary directory and remove it themselves.

| command (Linux, from this directory) | exit | log |
|---|---|---|
| `python3.12 scripts/measure_retained.py <repo> results/measurement/retained_json.json` | 0 | `logs/02_measure_retained.log` |
| `python3.12 scripts/build_fixtures.py check` | 0 | `logs/03_build_check_fixtures.log` |
| `unshare -rn python3.12 scripts/run_cases.py baseline results/baseline-linux-py3.12` | 1 (O1, kept) | `logs/10_run_cases_baseline.log` |
| `unshare -rn python3.12 scripts/run_cases.py repaired results/run1-linux-py3.12` | 1 (I07, I10, O1, kept) | `logs/20_run_cases_repaired_run1.log` |
| `unshare -rn python3.12 -m unittest discover -s scripts -v` | 0 (27 tests) | `logs/21_unittest_run1.log` |

**macOS, offline, Python 3.12 and the standard library only (not run here).** Outputs go outside
the recovered source, and bytecode is not written:

```sh
git clone --branch claude/adoring-turing-3ekxhe https://github.com/gmfjc624d2-dot/trafilatura.git trafilatura-json-numeric
cd trafilatura-json-numeric && git rev-parse HEAD   # compare with the head reported for this request
cd research/public-json-numeric-integrity-20261018-01
export PYTHONDONTWRITEBYTECODE=1; OUT="$HOME/json-numeric-replay-$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$OUT"
# the network can be off from here on
shasum -a 256 -c SHA256SUMS && shasum -a 256 -c PREREGISTERED.sha256
python3.12 -c "import sys, decimal; print(sys.version, decimal.__libmpdec_version__, sys.get_int_max_str_digits())"
python3.12 scripts/build_fixtures.py check
python3.12 scripts/run_cases.py repaired "$OUT/run"; echo "exit=$? (1 expected: I07 and I10 kept)"
python3.12 scripts/compare_results.py results/run1-linux-py3.12/cases.json "$OUT/run/cases.json"; echo "exit=$?"
python3.12 scripts/run_cases.py baseline "$OUT/baseline"; echo "exit=$?"
python3.12 scripts/compare_results.py results/baseline-linux-py3.12/cases.json "$OUT/baseline/cases.json"; echo "exit=$?"
python3.12 -m unittest discover -s scripts -v
git status --short   # empty: nothing was written into the source
```

**Expected on 3.12.14:**
* The comparisons exit 0 only if nothing but `environment.python`, `.platform` and `.machine`
  differs. `environment.libmpdec`, `decimal` and `int_max_str_digits` are compared, so another
  libmpdec (for example a build against the system mpdecimal) is reported as a difference. That is
  a finding to report, never a reason to widen the exceptions.
* O1 is predicted to pass on 3.12.14, where both scanners reject `[١]`. The baseline run would
  then exit 0.
* `interpreter_observations.json` is version-specific and is inspected, not compared.

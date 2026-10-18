# Result: corrected text-policy test suite (Linux evidence, not macOS qualification)

The corrected suite was run once, from the repository root and offline, after the pre-execution
commit `bee65a09d9abda644c0caee69c8fb5ba38767b6f` (`logs/01_corrected_suite_run1.log`):

    sources: 17 pinned files, baseline, corrected copy and patch checked; 0 differ []
    ... (3 dependencies zipimported from the pinned wheels, sha256 matching)
    Ran 11 tests in 0.104s
    OK
    returncode=0
    exit=0

**11 tests run, 11 ok, return code 0, as predicted in `CORRECTION.md`.**

* `test_oracle_equals_the_rule_and_tells_every_mutant_apart_on_c2` passes. For both lxml and
  html5lib:
  * the C2 unit's final native tail is `"\n"`;
  * the M3 mutant equals the oracle plus `"\n"`;
  * the M1-M4 loop, which never ran in the earlier execution, finds every mutant different from
    the oracle.
* The other 10 tests are byte-identical to the earlier ones and pass as they did in
  `research/public-sphinx-text-policy-20261018-01/logs/21_unittest_run1.log`.
* The historical record is unchanged. The earlier run (11 run, 10 ok, 1 FAIL, exit 1) and its log,
  report, manifest and test remain exactly as committed. This directory adds only a corrected copy.
* Nothing was written outside this directory: no bytecode, and the tree was clean apart from the
  two new outputs. The earlier replay and unrelated suites were not run. The replay's `main()` was
  never called; `replay.py` was only imported for the helpers the test uses.

## Evidence scope

**This is Linux evidence only.** The platform was x86_64, Python 3.12.3 (GCC 13.3.0), lxml 6.1.3,
libxml2 2.14.6 (runtime and compiled), with html5lib 1.1, six 1.17.0 and webencodings 0.5.1
zipimported from the retained wheels. It is **not** macOS qualification: no macOS run was made
here.

Other limits are inherited from the earlier report (section 6):
* the oracle's PI branch is not exercised by any fixture;
* the mutation controls discriminate M1 and M2 only on C2.

## Recovery, comparison and macOS replay

Retrieve the exact commit that adds this file
(`git log -1 --format=%H -- research/public-sphinx-final-tail-test-correction-20261018-01/RESULT.md`,
reported with the run). Then, offline after the clone, with a Python 3.12 where `import lxml` works:

```sh
git clone --branch claude/adoring-turing-3ekxhe https://github.com/gmfjc624d2-dot/trafilatura.git "$HOME/trafilatura-tail-fix"
cd "$HOME/trafilatura-tail-fix" && git checkout --detach <reported commit> && git log -1 --format=%H
P=research/public-sphinx-final-tail-test-correction-20261018-01; W="$PWD/research/public-sphinx-parser-corroboration-20261018-01/wheels"
OUT="$HOME/tail-fix-run-$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$OUT"; PY=python3.12
(cd "$P" && shasum -a 256 -c SHA256SUMS)
patch -s -o "$OUT/patched.py" "$P/baseline/test_text_policy.py" "$P/patch/test_text_policy.diff" && cmp "$OUT/patched.py" "$P/corrected/test_text_policy.py" && echo "patch reproduces the corrected copy"
cmp "$P/baseline/test_text_policy.py" research/public-sphinx-text-policy-20261018-01/scripts/test_text_policy.py && echo "baseline is byte-identical"
# disconnect the network from here on
ZP="$W/html5lib-1.1-py2.py3-none-any.whl:$W/six-1.17.0-py2.py3-none-any.whl:$W/webencodings-0.5.1-py2.py3-none-any.whl"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ZP" "$PY" -W default "$P/scripts/run_corrected_suite.py" "$OUT/record.json"; echo "exit=$?"
"$PY" -I research/public-json-numeric-integrity-20261018-01/scripts/compare_results.py "$P/results/run1-linux-py3.12.json" "$OUT/record.json"; echo "exit=$?"
git status --short                                 # empty: nothing written into the clone
```

Do not pass `-I` to the runner, because it would ignore `PYTHONPATH`.

**A macOS run counts as replicating this Linux result when:**
* the runner prints `0 differ`, three `zipimported … =True matches pin=True` lines, `Ran 11 tests`,
  `OK` and `returncode=0`, and exits 0;
* the comparator prints `differences outside the 3 exempt paths: 0` and exits 0. Only
  environment.python, .platform and .machine may differ (`logs/02_record_comparator_check.log` shows
  the command accepts this record);
* `git status --short` is empty.

Anything else, such as another lxml or libxml2 version, a pure-Python ElementTree, or a failing
test, is a finding to report as it is, not something to edit.

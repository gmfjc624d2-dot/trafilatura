"""Run the corrected copy of the text-policy focused tests against the pinned earlier public sources.

Usage (any working directory; lxml importable; the three retained wheels on PYTHONPATH through zipimport):
    python research/public-sphinx-final-tail-test-correction-20261018-01/scripts/run_corrected_suite.py [RECORD_JSON]

1. Every file in sources.json is checked by sha256: the pinned earlier sources, the baseline copy
   (also byte for byte against the earlier test), the corrected copy and the patch. Any mismatch
   gives exit 2 before a test runs.
2. The earlier text_policy.py and replay.py are executed from their verified bytes as the modules
   `text_policy` and `replay`. replay's main() is never called, so no replay runs.
3. The corrected test module is loaded the same way and run by unittest at verbosity 2. No bytecode
   is written.

Exit 0 when every test passes, 1 otherwise. The optional RECORD_JSON receives the environment and
each test's outcome, without tracebacks or absolute paths, for comparison with results/ by the
pinned json-numeric comparator.
"""

import hashlib
import json
import sys
import types
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent
SOURCES = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
EARLIER = "research/public-sphinx-text-policy-20261018-01/scripts"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def differing():
    bad = [rel for rel, pin in SOURCES["pinned_sources"].items() if sha256((REPO / rel).read_bytes()) != pin]
    base, fixed = SOURCES["baseline"], SOURCES["corrected"]
    if (HERE / base["copy"]).read_bytes() != (REPO / base["source"]).read_bytes():
        bad.append(f"{base['copy']} is not byte-identical to {base['source']}")
    for rel, pin in (
        (base["copy"], base["sha256"]),
        (fixed["copy"], fixed["sha256"]),
        (fixed["patch"], fixed["patch_sha256"]),
    ):
        if sha256((HERE / rel).read_bytes()) != pin:
            bad.append(rel)
    return bad


def load(name, path, pin):
    "Execute the bytes just verified as module `name`, registered so that later imports find it."
    data = path.read_bytes()
    if sha256(data) != pin:
        raise RuntimeError(f"{path} differs from its pin")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(data, module.__file__, "exec"), module.__dict__)
    return module


def flat(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flat(test)
        else:
            yield test


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    bad = differing()
    print(
        f"sources: {len(SOURCES['pinned_sources'])} pinned files, baseline, corrected copy and patch checked; {len(bad)} differ {bad}"
    )
    if bad:
        return 2
    pins = SOURCES["pinned_sources"]
    tp = load("text_policy", REPO / EARLIER / "text_policy.py", pins[f"{EARLIER}/text_policy.py"])
    load("replay", REPO / EARLIER / "replay.py", pins[f"{EARLIER}/replay.py"])
    test = load("test_text_policy", HERE / SOURCES["corrected"]["copy"], SOURCES["corrected"]["sha256"])
    environment, dependencies = tp.co.environment(), tp.dependencies()
    print("environment:", json.dumps(environment))
    for name, d in dependencies.items():
        print(
            f"dependency {name} {d['version']}: zipimported from {d['wheel']}={d['zipimported_from_wheel']} matches pin={d['matches_pin']}"
        )
    suite = unittest.defaultTestLoader.loadTestsFromModule(test)
    tests = list(flat(suite))
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    marked = {t.id(): "FAIL" for t, _ in result.failures} | {t.id(): "ERROR" for t, _ in result.errors}
    marked |= {t.id(): "skip" for t, _ in result.skipped}
    returncode = 0 if result.wasSuccessful() else 1
    if argv:
        record = {
            "environment": environment,
            "request_id": SOURCES["request_id"],
            "corrected_sha256": SOURCES["corrected"]["sha256"],
            "dependencies": dependencies,
            "tests_run": result.testsRun,
            "outcomes": [{"test": t.id(), "outcome": marked.get(t.id(), "ok")} for t in tests],
            "returncode": returncode,
        }
        Path(argv[0]).parent.mkdir(parents=True, exist_ok=True)
        Path(argv[0]).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"returncode={returncode}")
    return returncode


if __name__ == "__main__":
    sys.exit(main())

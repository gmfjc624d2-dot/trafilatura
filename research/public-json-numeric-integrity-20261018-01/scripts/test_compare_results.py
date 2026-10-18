"""Focused offline tests of the exact-number comparator (stdlib unittest only).

Run from the research directory: python -m unittest discover -s scripts -v
Negative controls run the unmodified 9a7933f copy and assert that it still shows the defect.
CLI tests start the comparator as a subprocess; generated large inputs go to a temporary
directory that the test removes itself.
"""

import decimal
import io
import json
import json.scanner
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest import mock

import build_fixtures
import compare_results as cmp
import compare_results_baseline_9a7933f as baseline

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
EXP = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
JSON_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?")
EVIDENCE = REPO / "research/public-sphinx-evidence-integrity-20261018-01/results/run1-linux-py3.12/results.json"
SPANS = REPO / "research/public-evidence-spans-20261018-01/results/run1-linux-py3.12/results.json"


def differs(a, b, mod=cmp):
    return mod.compare(mod.loads(a), mod.loads(b)) != []


def cli(*args):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "compare_results.py"), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


class Collisions(unittest.TestCase):
    FAMILIES = (
        ('{"x":1e400}', '{"x":2e400}'),  # overflow to inf as float
        ('{"x":1e-4000}', '{"x":2e-4000}'),  # underflow to 0.0 as float
        ('{"x":9007199254740993.0}', '{"x":9007199254740992.0}'),  # finite rounding to the same double
    )

    def test_the_three_families_differ(self):
        for a, b in self.FAMILIES:
            self.assertTrue(differs(a, b), (a, b))

    def test_baseline_still_collides(self):
        "negative control: the 9a7933f parser turns each pair into one float"
        for a, b in self.FAMILIES:
            self.assertFalse(differs(a, b, baseline), (a, b))
        self.assertEqual(baseline.loads('{"x":1e400}')["x"], float("inf"))

    def test_finite_large_exponents_are_not_constants(self):
        self.assertEqual(cmp.loads('{"x":1e400}')["x"], Decimal("1E+400"))
        self.assertEqual(cmp.loads('{"x":-1e-4000}')["x"].as_tuple(), (1, (1,), -4000))


class CategoriesAndEquality(unittest.TestCase):
    def test_boolean_integer_decimal_stay_apart(self):
        self.assertEqual(
            [cmp.json_type(cmp.loads(t)) for t in ("true", "1", "1.0", "1e0")], ["boolean", "integer", "decimal", "decimal"]
        )
        for a, b in (("1", "1.0"), ("true", "1"), ("false", "0"), ("0", "0.0"), ("-0", "-0.0"), ("null", "0")):
            self.assertEqual(cmp.compare(cmp.loads(a), cmp.loads(b))[0][1], "type", (a, b))

    def test_equivalent_spellings_are_equal(self):
        for a, b in (
            ("1.0", "1.00"),
            ("1.0", "1e0"),
            ("1E+2", "100.0"),
            ("1e400", "10e399"),
            ("1e-4000", "0.1e-3999"),
            ("1e0400", "1e400"),
        ):
            self.assertFalse(differs(a, b), (a, b))

    def test_signed_zeros(self):
        self.assertTrue(differs("0.0", "-0.0"))
        self.assertTrue(differs("0e-3", "-0e0"))
        self.assertFalse(differs("-0.0", "-0e0"))
        self.assertFalse(differs("0.0", "0e5"))
        self.assertFalse(differs("-0", "0"))  # integer -0 is int 0 (legacy policy)
        self.assertIs(type(cmp.loads("-0")), int)

    def test_low_precision_caller_context_is_neither_used_nor_changed(self):
        with decimal.localcontext() as ctx:
            ctx.prec, ctx.Emax, ctx.Emin = 1, 1, -1
            ctx.clear_flags()
            for signal in list(ctx.traps):
                ctx.traps[signal] = True  # any rounding, overflow or float use would raise
            before = (ctx.prec, ctx.Emax, ctx.Emin, dict(ctx.traps), dict(ctx.flags))
            self.assertTrue(differs("1.1", "1.2"))  # +x or x - y at prec=1 would make these equal
            self.assertTrue(differs("1e400", "2e400"))
            self.assertFalse(differs("1.0", "1.00"))
            self.assertTrue(differs("0.0", "-0.0"))
            self.assertEqual((ctx.prec, ctx.Emax, ctx.Emin, dict(ctx.traps), dict(ctx.flags)), before)
            self.assertIs(decimal.getcontext(), ctx)

    def test_no_rounding_or_spelling_operations_in_the_source(self):
        source = (ROOT / "scripts" / "compare_results.py").read_text(encoding="utf-8")
        for forbidden in ("compare_total", ".normalize(", ".quantize(", "float(", "default=str", "set_int_max_str_digits"):
            self.assertNotIn(forbidden, source)


class InvalidInput(unittest.TestCase):
    def test_duplicates_constants_and_malformed_text(self):
        for text in (
            '{"x":1,"x":2}',
            '{"x":NaN}',
            '{"x":Infinity}',
            '{"x":-Infinity}',
            '{"x":}',
            '{"x":01}',
            '{"x":1.}',
            "﻿{}",
            "",
        ):
            with self.assertRaises(ValueError, msg=text):
                cmp.loads(text)
        with self.assertRaises(cmp.InvalidJSONError):
            cmp.loads('{"x":1,"x":2}')

    def test_non_ascii_digits_are_rejected_by_the_hooks(self):
        for hook, token in (
            (cmp.PARSE_HOOKS["parse_int"], "1١"),
            (cmp.PARSE_HOOKS["parse_float"], "1.١"),
            (cmp.PARSE_HOOKS["parse_int"], "1_0"),
        ):
            with self.assertRaises(cmp.InvalidJSONError):
                hook(token)
        dec = json.JSONDecoder(**cmp.PARSE_HOOKS)
        dec.scan_once = json.scanner.py_make_scanner(dec)  # v3.12.3 passes '1١' here, v3.12.14 does not match it
        with self.assertRaises(ValueError):
            dec.decode("[1١]")


class Limits(unittest.TestCase):
    def test_limits_are_the_preregistered_ones(self):
        self.assertEqual({k: getattr(cmp, k) for k in EXP["limits"]}, EXP["limits"])
        self.assertEqual([list(p) for p in cmp.ENVIRONMENT_EXCEPTIONS], EXP["environment_exceptions"])

    def test_boundaries(self):
        d40, i40 = "1." + "2" * 39, "1" * 40
        admitted = (i40, d40, "1e9999", "1e-9999", "1e400", "2e400", "1e-4000", "2e-4000", "-" + d40 + "e-9999")
        for text in admitted:
            cmp.loads(text)
        rejected = {i40 + "1": "41 digits", d40 + "1": "41 coefficient", "1e10000": "5 digits", "1e-10000": "5 digits",
                    "1e00001": "5 digits", "1" * 49: "49 characters", "[" * 33 + "]" * 33: "depth 33"}  # fmt: skip
        for text, message in rejected.items():
            with self.assertRaisesRegex(cmp.LimitExceededError, message):
                cmp.loads(text)
        self.assertEqual(len("-" + d40 + "e-9999"), cmp.MAX_NUMBER_TOKEN_CHARS)
        cmp.loads("[" * 32 + "]" * 32)

    def test_byte_ceiling_before_decoding(self):
        n = cmp.MAX_INPUT_BYTES
        cmp.loads(b'{"x":"' + b"a" * (n - 8) + b'"}')
        with self.assertRaises(cmp.LimitExceededError):
            cmp.loads(b'{"x":"' + b"\xff" * (n - 7) + b'"}')  # invalid UTF-8, but the ceiling is checked first
        with self.assertRaises(cmp.LimitExceededError):
            cmp.loads('{"x":"' + "é" * (n // 2) + '"}')  # fewer characters than bytes

    def test_limits_hold_before_int_or_decimal_conversion(self):
        with (
            mock.patch.object(cmp, "Decimal", wraps=Decimal) as spy,
            mock.patch.object(cmp, "int", create=True, wraps=int) as ispy,
        ):
            for text in ("1e10000", "1." + "2" * 40, "1" * 41, "1" * 5000):
                with self.assertRaises(cmp.LimitExceededError):
                    cmp.loads(text)
            spy.assert_not_called()
            ispy.assert_not_called()
            cmp.loads("[1e400, 12]")
            self.assertEqual((spy.call_count, ispy.call_count), (1, 1))

    def test_interpreter_integer_protection_is_untouched(self):
        before = sys.get_int_max_str_digits()
        cmp.loads("[" + ", ".join(["1" * 40] * 50) + "]")
        self.assertEqual(sys.get_int_max_str_digits(), before)

    def test_controlled_nesting_errors(self):
        with self.assertRaisesRegex(cmp.LimitExceededError, "recursion limit while decoding"):
            cmp.loads("[" * 100_000 + "]" * 100_000)
        deep = []
        for _ in range(4999):
            deep = [deep]
        with self.assertRaises(cmp.LimitExceededError):
            cmp.compare(deep, deep)
        with self.assertRaises(cmp.LimitExceededError):
            cmp.as_json(deep)
        with self.assertRaises(RecursionError):  # negative control
            baseline.compare(deep, deep)


class Structure(unittest.TestCase):
    def paths(self, a, b, **kw):
        return [(cmp.render(p), w) for p, w, *_ in cmp.compare(cmp.loads(a), cmp.loads(b), **kw)]

    def test_keys_order_arrays_and_nesting(self):
        self.assertEqual(self.paths('{"a":1,"b":2}', '{"b":2,"a":1}'), [("$", "key order")])
        self.assertEqual(self.paths('{"a":1}', '{"a":1,"b":2}'), [("$", "keys")])
        self.assertEqual(self.paths("[1,2]", "[2,1]"), [("$[0]", "value"), ("$[1]", "value")])
        self.assertEqual(self.paths("[1]", "[1,1]"), [("$", "length")])
        self.assertEqual(self.paths('{"a":{"b":[{"c":1.5}]}}', '{"a":{"b":[{"c":1.51}]}}'), [("$.a.b[0].c", "value")])
        self.assertEqual(self.paths('{"a":{"b":[{"c":1.5}]}}', '{"a":{"b":[{"c":1.50}]}}'), [])

    def test_exactly_three_exempt_values(self):
        env = '{"environment":{"python":"a","platform":"b","machine":"c","lxml":"d"},"other":{"python":"a"}}'
        self.assertEqual(self.paths(env, env.replace('"a"', '"x"', 1).replace('"b"', '"y"').replace('"c"', '"z"')), [])
        self.assertEqual(self.paths(env, env.replace('"d"', '"e"')), [("$.environment.lxml", "value")])
        self.assertEqual(self.paths(env, env.replace('"python":"a",', "", 1)), [("$.environment", "keys")])
        self.assertEqual(self.paths(env, env[::-1].replace('"a"', '"x"', 1)[::-1]), [("$.other.python", "value")])
        self.assertEqual(self.paths(env, env.replace('"a"', '"x"', 1), exceptions=()), [("$.environment.python", "value")])
        self.assertEqual(cmp.compare([1], [2], (), ()), [((0,), "value", 1, 2)])  # positional signature kept


class Diagnostics(unittest.TestCase):
    def test_numbers_are_shown_whole_as_valid_json(self):
        for text in ("1e400", "-1e-4000", "0e-3", "-0e0", "1e0", "9007199254740993.0", "1." + "2" * 39):
            value = cmp.loads(text)
            shown = cmp.short(value)
            self.assertRegex(shown, f"^{JSON_NUMBER.pattern}$")
            self.assertEqual(Decimal(shown).as_tuple(), value.as_tuple())  # display fidelity, not the equality rule
        self.assertEqual(cmp.short(cmp.loads('{"v":[1e400,"s",null,true,-0.0]}')), '{"v": [1E+400, "s", null, true, -0.0]}')

    def test_long_strings_are_cut_with_identity(self):
        a, b = cmp.short("x" * 200 + "a"), cmp.short("x" * 200 + "b")
        self.assertNotEqual(a, b)
        self.assertIn("(201 chars, sha256 ", a)
        self.assertEqual(cmp.short("\ud800"), '"\\ud800"')

    def test_cli_exit_codes_and_lines(self):
        with tempfile.TemporaryDirectory(prefix="json-numeric-test-") as tmp:
            files = {}
            for name, text in {"a": '{"x":1e400}', "b": '{"x":2e400}', "e": '{"environment":{"python":{"v":1e400}},"x":"\\ud800"}',
                               "f": '{"environment":{"python":{"v":2e400}},"x":"\\udc00"}'}.items():  # fmt: skip
                files[name] = Path(tmp) / f"{name}.json"
                files[name].write_text(text, encoding="utf-8")
            for key, data in build_fixtures.generated().items():
                files[key] = Path(tmp) / f"{key}.json"
                files[key].write_bytes(data)
            code, out, err = cli(files["a"], files["a"])
            self.assertEqual((code, err), (0, ""))
            code, out, err = cli(files["a"], files["b"])
            self.assertEqual((code, err), (1, ""))
            self.assertIn("DIFFERS $.x (decimal value): committed 1E+400 | replay 2E+400", out)
            code, out, err = cli(files["e"], files["f"])
            self.assertEqual((code, err), (1, ""))
            self.assertIn('exempt $.environment.python: committed {"v": 1E+400} | replay {"v": 2E+400}', out)
            self.assertIn('committed "\\ud800" | replay "\\udc00"', out)
            for key, message in (("G02", "more than 4194304 bytes"), ("G03", "5000 characters"), ("G04", "recursion limit")):
                code, out, err = cli(files[key], files["a"])
                self.assertEqual((code, err), (2, ""), key)
                self.assertIn(message, out, key)
            self.assertEqual(cli(files["a"], Path(tmp) / "missing.json")[0], 2)
            self.assertEqual(cli(files["a"])[0], 2)


class NativeObjects(unittest.TestCase):
    def test_as_json_compares_emitted_text_only(self):
        self.assertTrue(9007199254740993.0 == 9007199254740992.0)  # lost before as_json() sees it
        self.assertEqual(cmp.compare(cmp.as_json({"x": 9007199254740993.0}), cmp.as_json({"x": 9007199254740992.0})), [])
        binary = 0.1
        tenth = cmp.as_json({"x": binary})["x"]
        self.assertEqual((type(tenth), tenth), (Decimal, Decimal("0.1")))
        self.assertNotEqual(tenth, Decimal(binary))  # not the binary value 0.1000000000000000055511151231257827...

    def test_as_json_rejects_nonfinite_and_native_decimal(self):
        for value in (float("nan"), float("inf"), Decimal("1.5"), Decimal("NaN")):
            with self.assertRaises(cmp.UnsupportedValueError, msg=repr(value)):
                cmp.as_json({"x": value})

    def test_as_json_keeps_str_subclass_handling(self):
        class S(str):  # stands in for lxml's _ElementUnicodeResult
            __slots__ = ()

        self.assertIs(type(cmp.as_json({"x": S("a")})["x"]), str)
        with self.assertRaises(TypeError):  # compare() itself still refuses it, as before
            cmp.compare(S("a"), S("a"))

    def test_compare_rejects_native_float_and_nonfinite_decimal(self):
        for value in (1.0, Decimal("NaN"), Decimal("-Infinity"), (1,)):
            with self.assertRaises(cmp.UnsupportedValueError, msg=repr(value)):
                cmp.compare({"x": value}, {"x": value})


class RetainedResults(unittest.TestCase):
    def test_self_comparison_and_derived_mutations(self):
        text = EVIDENCE.read_text(encoding="utf-8")
        doc = cmp.loads(text)
        self.assertEqual(cmp.compare(doc, doc), [])
        moved = cmp.loads(text.replace('"python": "3.12.3', '"python": "3.12.14', 1))
        self.assertEqual(cmp.compare(doc, moved), [])
        mutated = cmp.compare(doc, cmp.loads(text.replace('"context_bytes": 989,', '"context_bytes": 989.0,', 1)))
        self.assertEqual([(w, x, y) for _, w, x, y in mutated], [("type", "integer", "decimal")])
        spans = SPANS.read_text(encoding="utf-8")
        nudged = spans.replace("-0.48514337270399616", "-0.48514337270399617", 1)
        self.assertEqual(len(cmp.compare(cmp.loads(spans), cmp.loads(nudged))), 1)
        self.assertEqual(baseline.compare(baseline.loads(spans), baseline.loads(nudged)), [])  # negative control


class MainInProcess(unittest.TestCase):
    def test_main_returns_codes_without_raising(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cmp.main([str(EVIDENCE), str(EVIDENCE)]), 0)
        self.assertIn("differences outside the 3 exempt paths: 0", out.getvalue())


if __name__ == "__main__":
    unittest.main()

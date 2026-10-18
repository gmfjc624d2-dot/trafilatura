"""Write the byte-exact JSON fixtures, their identities and the pre-registered expectations.

  python build_fixtures.py build   # writes fixtures/cases/*.json, files.json, expectations.json
  python build_fixtures.py check   # rebuilds in memory, compares bytes (exit 1 if different)

Every fixture is the exact text below, with no final newline. Four large inputs (G01-G04) are not
committed; generated() rebuilds them byte for byte and files.json pins their sha256. Written
before the repaired comparator existed. Python 3.12 standard library only.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

LIMITS = {
    "MAX_INPUT_BYTES": 4_194_304,
    "MAX_DEPTH": 32,
    "MAX_NUMBER_TOKEN_CHARS": 48,
    "MAX_INTEGER_DIGITS": 40,
    "MAX_COEFFICIENT_DIGITS": 40,
    "MAX_EXPONENT_DIGITS": 4,
}
LIMITS_BASIS = {
    "measured": "results/measurement/retained_json.json (33 retained JSON files): at most 246236 bytes, depth 7,"
    " number tokens of at most 20 characters, 6 integer digits, 18 coefficient digits, no exponent",
    "MAX_INPUT_BYTES": "4 MiB, 17 times the largest retained file; checked on the bytes before decoding",
    "MAX_DEPTH": "32 nested containers, 4.5 times the deepest retained file (7)",
    "MAX_INTEGER_DIGITS": "40 digits (sign not counted), far below the interpreter's 4300-digit int/str limit",
    "MAX_COEFFICIENT_DIGITS": "40 digits before the exponent, '.' and sign not counted; leading zeros count",
    "MAX_EXPONENT_DIGITS": "4 digits of exponent text, sign not counted, leading zeros counted:"
    " admits 1e400, 2e400, 1e-4000, 2e-4000 and 1e9999, rejects 1e10000 and 1e00001",
    "MAX_NUMBER_TOKEN_CHARS": "48 = sign + 40 digits + '.' + 'e' + exponent sign + 4 digits; the first, cheapest check",
}

POLICY = {
    "P1_parsing": "integer tokens become int and fraction/exponent tokens become decimal.Decimal, both converted from the"
    " token text after the limits below are checked; JSON types are 'boolean', 'integer' and 'decimal' and are never"
    " equal to each other; duplicate object keys and the literals NaN, Infinity and -Infinity are invalid input;"
    " 1e400 is a finite number token, not a non-finite constant",
    "P2_decimal_equality": "two decimals are equal when a == b (exact numeric value) and, if both are zero, a.is_signed()"
    " == b.is_signed(); so 1.0 == 1.00 == 1e0, 0.0 != -0.0, -0.0 == -0e0; no compare_total, no spelling equality,"
    " no normalize/quantize/unary plus, no float; the integer token -0 parses as int 0 (legacy policy) and equals 0",
    "P3_structure": "unchanged complete recursive comparison: JSON type, object key sets and key order, array length and"
    " order, scalars; only the values at environment.python, environment.platform and environment.machine may differ"
    " and their keys must exist on both sides; compare() rejects native float, non-finite Decimal and other non-JSON"
    " values (UnsupportedValueError) and containers nested deeper than MAX_DEPTH (LimitExceededError)",
    "P4_as_json": "json.dumps(value, ensure_ascii=False, allow_nan=False, default=<reject>) and then the exact parser:"
    " str subclasses become str as before; a float is compared by the text it emits (its repr), so precision already"
    " lost in the float is not recovered; nan/inf and native Decimal are rejected explicitly (UnsupportedValueError)",
    "P5_diagnostics": "display data only, never compared: a decimal is shown with str() (finite, every digit, a valid"
    " JSON number); numbers and containers are never cut; a string longer than 160 characters is cut and labelled with"
    " its length and a sha256 prefix; text that cannot be encoded as UTF-8 is shown with \\u escapes; value tags name"
    " the JSON type; CLI exit 0 equal, 1 different, 2 invalid/unreadable/unsupported; limits and recursion are"
    " reported as invalid input, never as equality and never as a traceback",
    "P6_limits": "LIMITS are enforced as follows: the byte ceiling on the bytes read (at most MAX_INPUT_BYTES + 1 are"
    " read) before UTF-8 decoding; the numeric limits in the parse_int/parse_float hooks on the token text before"
    " int() or Decimal() runs, the exponent text length before any conversion; tokens must be ASCII JSON number"
    " characters; the interpreter's global int/str digit limit is left unchanged",
    "P7_scope": "the hooks run after the json scanner has matched the whole token (that scan is bounded only by the byte"
    " ceiling); no new lexical parser; no claim of safety for arbitrary input",
}

ENV = '{"environment":{"python":"3.12.3","platform":"Linux-x86_64","machine":"x86_64","lxml":"6.1.3"},"value":1}'
ENV_EXEMPT = '{"environment":{"python":"3.12.14","platform":"macOS-arm64","machine":"arm64","lxml":"6.1.3"},"value":1}'
ENV_LXML = '{"environment":{"python":"3.12.3","platform":"Linux-x86_64","machine":"x86_64","lxml":"6.1.4"},"value":1}'
ENV_NO_PY = '{"environment":{"platform":"Linux-x86_64","machine":"x86_64","lxml":"6.1.3"},"value":1}'
D40 = "1.234567890123456789012345678901234567890"
I40 = "1234567890123456789012345678901234567890"


def dv(a, b, path="$.x"):
    return f"DIFFERS {path} (decimal value): committed {a} | replay {b}"


def ty(a, b, path="$.x"):
    return f'DIFFERS {path} (type): committed "{a}" | replay "{b}"'


def inv(text, limit=False):
    return f"INVALID INPUT (committed{', limit' if limit else ''}): {text}"


# id: (family, what, a text, b text or None (= a), requirement exit, requirement stdout lines, baseline exit, baseline lines)
# exits: equal 0, different 1, invalid 2, crash = traceback
CASES = [
    ("K01", "collision", "overflow", '{"x":1e400}', '{"x":2e400}', "different", [dv("1E+400", "2E+400")], "equal", []),
    ("K02", "collision", "underflow", '{"x":1e-4000}', '{"x":2e-4000}', "different", [dv("1E-4000", "2E-4000")], "equal", []),
    ("K03", "collision", "underflow vs zero", '{"x":1e-4000}', '{"x":0.0}', "different", [dv("1E-4000", "0.0")], "equal", []),
    (
        "K04",
        "collision",
        "negative underflow vs -0.0",
        '{"x":-1e-4000}',
        '{"x":-0.0}',
        "different",
        [dv("-1E-4000", "-0.0")],
        "equal",
        [],
    ),
    (
        "K05",
        "collision",
        "finite rounding beyond 2**53",
        '{"x":9007199254740993.0}',
        '{"x":9007199254740992.0}',
        "different",
        [dv("9007199254740993.0", "9007199254740992.0")],
        "equal",
        [],
    ),
    (
        "K06",
        "collision",
        "finite rounding at 17 digits",
        '{"x":0.1}',
        '{"x":0.10000000000000001}',
        "different",
        [dv("0.1", "0.10000000000000001")],
        "equal",
        [],
    ),
    (
        "K07",
        "collision",
        "two overflowing exponents",
        '{"x":1e400}',
        '{"x":1e9999}',
        "different",
        [dv("1E+400", "1E+9999")],
        "equal",
        [],
    ),
    (
        "K08",
        "collision",
        "40 digits, last digit differs",
        f'{{"x":{D40}}}',
        f'{{"x":{D40[:-1]}1}}',
        "different",
        [dv(D40, D40[:-1] + "1")],
        "equal",
        [],
    ),
    ("E01", "spelling", "trailing zero", '{"x":1.0}', '{"x":1.00}', "equal", [], "equal", []),
    ("E02", "spelling", "fraction vs exponent", '{"x":1.0}', '{"x":1e0}', "equal", [], "equal", []),
    ("E03", "spelling", "E+2 vs 100.0", '{"x":1E+2}', '{"x":100.0}', "equal", [], "equal", []),
    ("E04", "spelling", "1e400 vs 10e399", '{"x":1e400}', '{"x":10e399}', "equal", [], "equal", []),
    ("E05", "spelling", "1e-4000 vs 0.1e-3999", '{"x":1e-4000}', '{"x":0.1e-3999}', "equal", [], "equal", []),
    ("E06", "spelling", "-0.0 vs -0e0", '{"x":-0.0}', '{"x":-0e0}', "equal", [], "equal", []),
    ("E07", "spelling", "0.0 vs 0e5", '{"x":0.0}', '{"x":0e5}', "equal", [], "equal", []),
    ("E08", "spelling", "integer -0 vs 0 (legacy policy)", '{"x":-0}', '{"x":0}', "equal", [], "equal", []),
    ("E09", "spelling", "exponent with a leading zero", '{"x":1e0400}', '{"x":1e400}', "equal", [], "equal", []),
    ("Z01", "signed zero", "0.0 vs -0.0", '{"x":0.0}', '{"x":-0.0}', "different", [dv("0.0", "-0.0")], "different", []),
    ("Z02", "signed zero", "0e-3 vs -0e0", '{"x":0e-3}', '{"x":-0e0}', "different", [dv("0.000", "-0")], "different", []),
    (
        "T01",
        "category",
        "integer vs decimal",
        '{"x":1}',
        '{"x":1.0}',
        "different",
        [ty("integer", "decimal")],
        "different",
        [],
    ),
    (
        "T02",
        "category",
        "boolean vs integer",
        '{"x":true}',
        '{"x":1}',
        "different",
        [ty("boolean", "integer")],
        "different",
        [],
    ),
    ("T03", "category", "false vs 0", '{"x":false}', '{"x":0}', "different", [ty("boolean", "integer")], "different", []),
    ("T04", "category", "0 vs 0.0", '{"x":0}', '{"x":0.0}', "different", [ty("integer", "decimal")], "different", []),
    ("T05", "category", "-0 vs -0.0", '{"x":-0}', '{"x":-0.0}', "different", [ty("integer", "decimal")], "different", []),
    ("T06", "category", "null vs 0", '{"x":null}', '{"x":0}', "different", [ty("null", "integer")], "different", []),
    ("T07", "category", "string vs integer", '{"x":"1"}', '{"x":1}', "different", [ty("string", "integer")], "different", []),
    (
        "I01",
        "invalid",
        "duplicate key",
        '{"x":1,"x":1}',
        "OK",
        "invalid",
        [inv("duplicate object key(s) ['x']")],
        "invalid",
        [],
    ),
    ("I02", "invalid", "NaN literal", '{"x":NaN}', "OK", "invalid", [inv("non-standard JSON constant NaN")], "invalid", []),
    (
        "I03",
        "invalid",
        "Infinity literal",
        '{"x":Infinity}',
        "OK",
        "invalid",
        [inv("non-standard JSON constant Infinity")],
        "invalid",
        [],
    ),
    (
        "I04",
        "invalid",
        "-Infinity literal",
        '{"x":-Infinity}',
        "OK",
        "invalid",
        [inv("non-standard JSON constant -Infinity")],
        "invalid",
        [],
    ),
    ("I05", "invalid", "missing value", '{"x":}', "OK", "invalid", [inv("Expecting value")], "invalid", []),
    ("I06", "invalid", "trailing data", '{"x":1} x', "OK", "invalid", [inv("Extra data")], "invalid", []),
    (
        "I07",
        "invalid",
        "invalid UTF-8 byte",
        b'{"x":"\xff"}',
        "OK",
        "invalid",
        [inv("codec can't decode byte 0xff")],
        "invalid",
        [],
    ),
    ("I08", "invalid", "leading zero", '{"x":01}', "OK", "invalid", [inv("Expecting ',' delimiter")], "invalid", []),
    ("I09", "invalid", "UTF-8 BOM", b'\xef\xbb\xbf{"x":1}', "OK", "invalid", [inv("Unexpected UTF-8 BOM")], "invalid", []),
    ("I10", "invalid", "missing file", None, "OK", "invalid", [inv("No such file or directory")], "invalid", []),
    ("I11", "invalid", "empty file", b"", "OK", "invalid", [inv("Expecting value")], "invalid", []),
    (
        "I12",
        "invalid",
        "fraction without digits",
        '{"x":1.}',
        "OK",
        "invalid",
        [inv("Expecting ',' delimiter")],
        "invalid",
        [],
    ),
    ("L01", "limit", "40-digit integer (admitted)", f'{{"x":{I40}}}', None, "equal", [], "equal", []),
    (
        "L02",
        "limit",
        "41-digit integer",
        f'{{"x":{I40}1}}',
        None,
        "invalid",
        [inv("integer token has 41 digits; limit 40", True)],
        "equal",
        [],
    ),
    ("L03", "limit", "40 coefficient digits (admitted)", f'{{"x":{D40}}}', None, "equal", [], "equal", []),
    (
        "L04",
        "limit",
        "41 coefficient digits",
        f'{{"x":{D40}1}}',
        None,
        "invalid",
        [inv("number token has 41 coefficient digits; limit 40", True)],
        "equal",
        [],
    ),
    ("L05", "limit", "1e9999 (admitted)", '{"x":1e9999}', None, "equal", [], "equal", []),
    ("L06", "limit", "1e-9999 (admitted)", '{"x":1e-9999}', None, "equal", [], "equal", []),
    ("L07", "limit", "1e10000", '{"x":1e10000}', None, "invalid", [inv("exponent has 5 digits; limit 4", True)], "equal", []),
    (
        "L08",
        "limit",
        "1e-10000",
        '{"x":1e-10000}',
        None,
        "invalid",
        [inv("exponent has 5 digits; limit 4", True)],
        "equal",
        [],
    ),
    (
        "L09",
        "limit",
        "exponent text 00001",
        '{"x":1e00001}',
        None,
        "invalid",
        [inv("exponent has 5 digits; limit 4", True)],
        "equal",
        [],
    ),
    (
        "L10",
        "limit",
        "49-character token",
        f'{{"x":{I40}123456789}}',
        None,
        "invalid",
        [inv("number token has 49 characters; limit 48", True)],
        "equal",
        [],
    ),
    ("L11", "limit", "depth 32 (admitted)", "[" * 32 + "]" * 32, None, "equal", [], "equal", []),
    (
        "L12",
        "limit",
        "depth 33",
        "[" * 33 + "]" * 33,
        None,
        "invalid",
        [inv("nesting depth 33 exceeds limit 32", True)],
        "equal",
        [],
    ),
    ("G01", "limit", "exactly MAX_INPUT_BYTES (generated)", "generated", None, "equal", [], "equal", []),
    (
        "G02",
        "limit",
        "MAX_INPUT_BYTES + 1 (generated)",
        "generated",
        None,
        "invalid",
        [inv("input has more than 4194304 bytes", True)],
        "equal",
        [],
    ),
    (
        "G03",
        "limit",
        "5000-digit integer (generated)",
        "generated",
        None,
        "invalid",
        [inv("number token has 5000 characters; limit 48", True)],
        "invalid",
        ["Exceeds the limit (4300 digits)"],
    ),
    (
        "G04",
        "limit",
        "100000 nested arrays (generated)",
        "generated",
        None,
        "invalid",
        [inv("nesting exceeds the interpreter recursion limit while decoding", True)],
        "crash",
        ["RecursionError"],
    ),
    (
        "R01",
        "structure",
        "key order",
        '{"a":1,"b":2}',
        '{"b":2,"a":1}',
        "different",
        ['DIFFERS $ (key order): committed ["a", "b"] | replay ["b", "a"]'],
        "different",
        [],
    ),
    (
        "R02",
        "structure",
        "missing key",
        '{"a":1}',
        '{"a":1,"b":2}',
        "different",
        ['DIFFERS $ (keys): committed [] | replay ["b"]'],
        "different",
        [],
    ),
    (
        "R03",
        "structure",
        "array order",
        "[1,2]",
        "[2,1]",
        "different",
        ["DIFFERS $[0] (integer value): committed 1 | replay 2", "DIFFERS $[1] (integer value): committed 2 | replay 1"],
        "different",
        [],
    ),
    (
        "R04",
        "structure",
        "array length",
        "[1]",
        "[1,1]",
        "different",
        ["DIFFERS $ (length): committed 1 | replay 2"],
        "different",
        [],
    ),
    (
        "R05",
        "structure",
        "nested equal spelling",
        '{"a":{"b":[{"c":1.5}]}}',
        '{"a":{"b":[{"c":1.50}]}}',
        "equal",
        [],
        "equal",
        [],
    ),
    (
        "R06",
        "structure",
        "nested decimal differs",
        '{"a":{"b":[{"c":1.5}]}}',
        '{"a":{"b":[{"c":1.51}]}}',
        "different",
        [dv("1.5", "1.51", "$.a.b[0].c")],
        "different",
        [],
    ),
    ("X01", "exception", "python/platform/machine differ", ENV, ENV_EXEMPT, "equal", [], "equal", []),
    (
        "X02",
        "exception",
        "lxml differs",
        ENV,
        ENV_LXML,
        "different",
        ['DIFFERS $.environment.lxml (string value): committed "6.1.3" | replay "6.1.4"'],
        "different",
        [],
    ),
    (
        "X03",
        "exception",
        "exempt key missing",
        ENV,
        ENV_NO_PY,
        "different",
        ['DIFFERS $.environment (keys): committed ["python"] | replay []'],
        "different",
        [],
    ),
    (
        "X04",
        "exception",
        "a similar field elsewhere",
        ENV[:-1] + ',"other":{"python":"3.12.3"}}',
        ENV[:-1] + ',"other":{"python":"3.12.14"}}',
        "different",
        ['DIFFERS $.other.python (string value): committed "3.12.3" | replay "3.12.14"'],
        "different",
        [],
    ),
    (
        "X05",
        "exception",
        "exempt value with decimals",
        '{"environment":{"python":{"v":1e400},"platform":"p","machine":"m"}}',
        '{"environment":{"python":{"v":2e400},"platform":"p","machine":"m"}}',
        "equal",
        ['exempt $.environment.python: committed {"v": 1E+400} | replay {"v": 2E+400}'],
        "equal",
        ['exempt $.environment.python: committed {"v": Infinity} | replay {"v": Infinity}'],
    ),
    (
        "D01",
        "diagnostics",
        "lone surrogate escapes",
        '{"x":"\\ud800"}',
        '{"x":"\\udc00"}',
        "different",
        ['DIFFERS $.x (string value): committed "\\ud800" | replay "\\udc00"'],
        "crash",
        ["UnicodeEncodeError"],
    ),
]

# in-process cases: id -> (what, repaired observation, baseline observation); run_cases.py defines the observations
API_CASES = {
    "A01": (
        "parse and compare K, E and Z texts under prec=1, Emax=1, Emin=-1 and every signal trapped",
        {"verdicts": "as the CLI requirements", "low_precision_equals_default": True, "caller_context_unchanged": True},
        {
            "verdicts": "as the CLI baseline predictions",
            "low_precision_equals_default": True,
            "caller_context_unchanged": True,
        },
    ),
    "A02": (
        "sys.get_int_max_str_digits() unchanged by importing and using the module",
        {"unchanged": True},
        {"unchanged": True},
    ),
    "A03": (
        "as_json() of floats: 9007199254740993.0 vs 9007199254740992.0, and of 0.1",
        {"collision_after_as_json": "equal", "x_type": "decimal", "x_text": "0.1", "emitted_equals_binary_exact": False},
        {"collision_after_as_json": "equal", "x_type": "float", "x_text": "0.1", "emitted_equals_binary_exact": True},
    ),
    "A04": ("as_json({'x': nan})", "error:UnsupportedValueError", "error:InvalidJSONError"),
    "A05": ("as_json({'x': inf})", "error:UnsupportedValueError", "error:InvalidJSONError"),
    "A06": ("as_json({'x': Decimal('1.5')}) (native Decimal)", "error:UnsupportedValueError", "error:TypeError"),
    "A07": ("as_json({'x': str subclass}) gives a plain str", "str", "str"),
    "A08": ("compare() of native floats", "error:UnsupportedValueError", "equal"),
    "A09": ("compare() of Decimal('NaN')", "error:UnsupportedValueError", "error:TypeError"),
    "A10": ("compare() of in-process lists nested 5000 deep", "error:LimitExceededError", "error:RecursionError"),
    "A11": ("compare() of in-process lists nested 33 deep", "error:LimitExceededError", "equal"),
    "A12": ("compare() of in-process lists nested 32 deep", "equal", "equal"),
    "A13": ("loads('-0') (legacy integer policy)", {"type": "integer", "text": "0"}, {"type": "integer", "text": "0"}),
    "A14": (
        "loads('-0.0') keeps the sign",
        {"type": "decimal", "negative_sign": True},
        {"type": "float", "negative_sign": True},
    ),
    "A15": (
        "compare(a, b) and compare(a, b, exceptions=()) when only environment.python differs",
        {"default": [], "no_exceptions": ["$.environment.python"]},
        {"default": [], "no_exceptions": ["$.environment.python"]},
    ),
    "A16": ("loads() of an in-memory str of MAX_INPUT_BYTES + 1 UTF-8 bytes", "error:LimitExceededError", "ok"),
}

# retained JSON: self-comparison of every file in results/measurement/retained_json.json, plus derived mutations
DERIVED = [
    (
        "S02a",
        "research/public-sphinx-evidence-integrity-20261018-01/results/run1-linux-py3.12/results.json",
        {"op": "set", "path": ["environment", "python"], "value": "3.12.14 (main) [Clang]"},
        "equal",
        "equal",
    ),
    (
        "S02b",
        "research/public-sphinx-evidence-integrity-20261018-01/results/run1-linux-py3.12/results.json",
        {"op": "set", "path": ["environment", "lxml"], "value": "6.1.4"},
        "different",
        "different",
    ),
    (
        "S02c",
        "research/public-sphinx-evidence-integrity-20261018-01/results/run1-linux-py3.12/results.json",
        {"op": "text", "old": '"context_bytes": 989,', "new": '"context_bytes": 989.0,'},
        "different",
        "different",
    ),
    (
        "S02d",
        "research/public-evidence-spans-20261018-01/results/run1-linux-py3.12/results.json",
        {"op": "text", "old": "-0.48514337270399616", "new": "-0.48514337270399617"},
        "different",
        "equal",
    ),
    (
        "S02e",
        "research/public-evidence-spans-20261018-01/results/run1-linux-py3.12/results.json",
        {"op": "text", "old": "-0.48514337270399616", "new": "-0.485143372703996160"},
        "equal",
        "equal",
    ),
]

# executed evidence about this interpreter (not compared on replay; versions differ)
INTERPRETER = {
    "O1": "pure-Python scanner (json.scanner.py_make_scanner) on '[\\u0661]': v3.12.3 predicted to match \\d and give [1]"
    " with default hooks and an InvalidJSONError with the repaired hooks; v3.12.14 predicted JSONDecodeError for both",
    "O2": "Decimal('1e999999999999999999') under the default context (Emax=999999): predicted to construct, adjusted() =="
    " 999999999999999999, no signal",
    "O3": "Decimal('1e9999999999999999999') (exponent beyond MAX_EMAX): predicted InvalidOperation under the default"
    " context and NaN when InvalidOperation is not trapped",
    "O4": "json.loads of 100000 nested arrays: RecursionError (message recorded)",
}


def generated():
    n = LIMITS["MAX_INPUT_BYTES"]
    return {
        "G01": b'{"x":"' + b"a" * (n - 8) + b'"}',
        "G02": b'{"x":"' + b"a" * (n - 7) + b'"}',
        "G03": b'{"x":' + b"1" * 5000 + b"}",
        "G04": b"[" * 100_000 + b"]" * 100_000,
    }


def raw(text):
    return text if isinstance(text, bytes) else text.encode("utf-8")


def build():
    files, table = {}, []
    files["fixtures/cases/OK.json"] = b'{"x":1}'
    for cid, family, what, a, b, req, req_lines, base, base_lines in CASES:
        if a == "generated":
            pa = f"generated:{cid}"
        else:
            pa = f"fixtures/cases/{cid}_a.json"
            if a is not None:
                files[pa] = raw(a)
        pb = pa if b is None else ("fixtures/cases/OK.json" if b == "OK" else f"fixtures/cases/{cid}_b.json")
        if b not in (None, "OK"):
            files[pb] = raw(b)
        table.append(
            {
                "id": cid,
                "family": family,
                "what": what,
                "committed": pa,
                "replay": pb,
                "requirement": {"outcome": req, "stdout_contains": req_lines},
                "baseline_prediction": {"outcome": base, "output_contains": base_lines},
            }
        )
    meta = {
        "note": "identities of the fixture bytes, written by scripts/build_fixtures.py before the repaired comparator existed",
        "files": {p: {"bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()} for p, d in sorted(files.items())},
        "generated": {k: {"bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()} for k, d in generated().items()},
    }
    exp = {
        "schema": 1,
        "request_id": "public-json-numeric-integrity-20261018-01",
        "continues": "b4fa1424ead6fe23e93ed1ca6a698e401f2b403b",
        "status": "PRE-REGISTERED: committed before the repaired comparator, the runner and the tests existed, and before"
        " the baseline ran on these cases. Not edited after results are seen; post-run notes go to REPORT.md.",
        "baseline": {
            "file": "scripts/compare_results_baseline_9a7933f.py",
            "copied_from": "research/public-sphinx-evidence-integrity-20261018-01/scripts/compare_results.py",
            "sha256": "9a7933f84a550e07ad862733cde7f1090eece844776836fb7ba4a8a99c6a50dc",
            "git_blob": "89a247187b82181b8883fcfd65f497c8f36c7f1f",
        },
        "limits": LIMITS,
        "limits_basis": LIMITS_BASIS,
        "policy": POLICY,
        "environment_exceptions": [["environment", "python"], ["environment", "platform"], ["environment", "machine"]],
        "outcomes": "equal: exit 0; different: exit 1; invalid: exit 2 without traceback; crash: a Python traceback",
        "requirement_note": "requirement.stdout_contains is checked on the repaired comparator only (its display format);"
        " for the baseline only the outcome is graded against the requirement, and baseline_prediction.output_contains"
        " (stdout or stderr) records the predicted defect",
        "cli_cases": table,
        "api_cases": {k: {"what": w, "repaired": r, "baseline": b} for k, (w, r, b) in API_CASES.items()},
        "retained_self_comparison": "every file listed in results/measurement/retained_json.json, sha256-pinned there:"
        " loads() succeeds and compare(x, x) == [] for both comparators; the two largest also through the CLI (exit 0)",
        "derived_mutations": [
            {
                "id": i,
                "file": f,
                "mutation": m,
                "repaired": r,
                "baseline": b,
                "note": "text mutations replace the first occurrence",
            }
            for i, f, m, r, b in DERIVED
        ],
        "interpreter_observations": INTERPRETER,
    }
    files["fixtures/files.json"] = (json.dumps(meta, indent=2) + "\n").encode("utf-8")
    files["fixtures/expectations.json"] = (json.dumps(exp, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return files


def main():
    files = build()
    if sys.argv[1] == "build":
        for rel, data in files.items():
            (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / rel).write_bytes(data)
        print(f"wrote {len(files)} files; cases: {len(CASES)} CLI, {len(API_CASES)} in-process, {len(DERIVED)} derived")
        return 0
    differ = [rel for rel, d in files.items() if not (ROOT / rel).exists() or (ROOT / rel).read_bytes() != d]
    print("check: " + ("identical" if not differ else f"DIFFERS: {differ}"))
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())

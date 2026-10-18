"""Compare two JSON result documents completely and recursively, with exact numbers.

Usage: python compare_results.py COMMITTED_JSON REPLAY_JSON
Successor of compare_results_baseline_9a7933f.py, which parsed fractions and exponents as float,
so 1e400 and 2e400 both became inf and compared equal. The policy is in fixtures/expectations.json:
* integer tokens are parsed as int, fraction/exponent tokens as decimal.Decimal, both from the token
  text; the JSON types boolean, integer and decimal are never equal to each other;
* two decimals are equal when == holds (exact numeric value) and, for zeros, their signs agree;
* everything else is compared as before: JSON type, object keys and their order, array length and
  order, scalars. Only the values at ENVIRONMENT_EXCEPTIONS may differ, and their keys must exist;
* limits: MAX_INPUT_BYTES on the bytes before decoding; the number-token limits in the parse hooks,
  on the token text before int() or Decimal(); MAX_DEPTH after parsing and in compare(). The hooks
  run after the json scanner has matched a whole token, so that scan is bounded only by the byte
  ceiling. This is not a lexical parser and makes no safety claim for arbitrary input.
Exit 0: no difference outside the exceptions; 1: differences, each printed with its path;
2: invalid, unreadable or unsupported input, including every limit, never a traceback.
"""

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

ENVIRONMENT_EXCEPTIONS = (("environment", "python"), ("environment", "platform"), ("environment", "machine"))
MAX_INPUT_BYTES = 4_194_304
MAX_DEPTH = 32
MAX_NUMBER_TOKEN_CHARS = 48
MAX_INTEGER_DIGITS = 40
MAX_COEFFICIENT_DIGITS = 40
MAX_EXPONENT_DIGITS = 4
SHOW_STRING_CHARS = 160
NUMBER_CHARS = frozenset("0123456789+-.eE")


class InvalidJSONError(ValueError):
    pass


class LimitExceededError(InvalidJSONError):
    "The input, a number token or the nesting is beyond the limits above."


class UnsupportedValueError(InvalidJSONError, TypeError):
    "A native value that is no exact JSON value: float, non-finite Decimal, str subclass, other types."


def _object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        seen, duplicates = set(), set()
        for key, _ in pairs:
            (duplicates if key in seen else seen).add(key)
        raise InvalidJSONError(f"duplicate object key(s) {sorted(duplicates)}")
    return result


def _constant(name):
    raise InvalidJSONError(f"non-standard JSON constant {name}")


def _token_text(token):
    "Checks on the text the scanner matched, before any conversion; returns it without its sign."
    if len(token) > MAX_NUMBER_TOKEN_CHARS:
        raise LimitExceededError(f"number token has {len(token)} characters; limit {MAX_NUMBER_TOKEN_CHARS}")
    if not (token.isascii() and NUMBER_CHARS.issuperset(token)):  # v3.12.3's pure-Python scanner passes \d digits
        raise InvalidJSONError(f"number token {token!r} is not ASCII JSON number text")
    return token.removeprefix("-")


def _int_token(token):
    digits = _token_text(token)
    if len(digits) > MAX_INTEGER_DIGITS:
        raise LimitExceededError(f"integer token has {len(digits)} digits; limit {MAX_INTEGER_DIGITS}")
    return int(token)  # -0 becomes 0: integers have no signed zero (legacy policy)


def _decimal_token(token):
    mantissa, _, exponent = _token_text(token).replace("E", "e").partition("e")
    coefficient = len(mantissa) - mantissa.count(".")
    if coefficient > MAX_COEFFICIENT_DIGITS:
        raise LimitExceededError(f"number token has {coefficient} coefficient digits; limit {MAX_COEFFICIENT_DIGITS}")
    exponent_digits = len(exponent.lstrip("+-"))
    if exponent_digits > MAX_EXPONENT_DIGITS:  # bounded as text: context Emax does not bound construction
        raise LimitExceededError(f"exponent has {exponent_digits} digits; limit {MAX_EXPONENT_DIGITS}")
    return Decimal(token)  # exact: no context rounding, no float


PARSE_HOOKS = {
    "parse_int": _int_token,
    "parse_float": _decimal_token,
    "parse_constant": _constant,
    "object_pairs_hook": _object,
}


def _check_depth(doc):
    stack = [(doc, 1)]
    while stack:
        node, level = stack.pop()
        if type(node) in (dict, list):
            if level > MAX_DEPTH:
                raise LimitExceededError(f"nesting depth {level} exceeds limit {MAX_DEPTH}")
            stack += [(v, level + 1) for v in (node.values() if type(node) is dict else node)]
    return doc


def loads(text):
    "Parse JSON text (str, or UTF-8 bytes) with exact numbers and the limits above."
    if isinstance(text, (bytes, bytearray)):
        if len(text) > MAX_INPUT_BYTES:
            raise LimitExceededError(f"input has more than {MAX_INPUT_BYTES} bytes")
        text = bytes(text).decode("utf-8")
    elif not isinstance(text, str):
        raise UnsupportedValueError(f"loads() takes str or bytes, not {type(text).__name__}")
    if len(text) > MAX_INPUT_BYTES or (
        4 * len(text) > MAX_INPUT_BYTES and len(text.encode("utf-8", "surrogatepass")) > MAX_INPUT_BYTES
    ):
        raise LimitExceededError(f"input has more than {MAX_INPUT_BYTES} bytes")
    try:
        doc = json.loads(text, **PARSE_HOOKS)
    except RecursionError:
        raise LimitExceededError("nesting exceeds the interpreter recursion limit while decoding") from None
    return _check_depth(doc)


def load(path):
    with Path(path).open("rb") as handle:
        data = handle.read(MAX_INPUT_BYTES + 1)  # the ceiling holds before anything is decoded
    return loads(data)


def _unsupported(value):
    raise UnsupportedValueError(
        f"as_json() does not serialize {type(value).__name__}; a native Decimal is rejected, not converted"
    )


def as_json(value):
    """An in-memory value as a result file records it: finite native serialization, then exact parsing.

    str subclasses (lxml's xpath() strings) become str, as before. A float is compared by the text it
    emits (its shortest repr): precision already lost when the float was made is not recovered.
    nan, inf and native Decimal are rejected.
    """
    try:
        text = json.dumps(value, ensure_ascii=False, allow_nan=False, default=_unsupported)
    except UnsupportedValueError:
        raise
    except RecursionError:
        raise LimitExceededError("nesting exceeds the interpreter recursion limit while serializing") from None
    except (ValueError, TypeError) as err:  # nan/inf with allow_nan=False, a circular reference, a non-str key
        raise UnsupportedValueError(f"not finite JSON: {err}") from None
    return loads(text)


def json_type(value):
    kind = type(value)
    if value is None:
        return "null"
    for name, t in (("boolean", bool), ("integer", int), ("string", str), ("array", list), ("object", dict)):
        if kind is t:
            return name
    if kind is Decimal:
        if not value.is_finite():
            raise UnsupportedValueError(f"non-finite Decimal {value}")
        return "decimal"
    if kind is float:
        raise UnsupportedValueError("native float: compare values from loads(), or use as_json() to compare its emitted text")
    raise UnsupportedValueError(f"not a JSON value: {kind.__name__}")


def _json_string(text):
    shown = json.dumps(text, ensure_ascii=False)
    try:
        shown.encode("utf-8")
    except UnicodeEncodeError:  # lone surrogates from \ud800-style escapes: show the escapes
        shown = json.dumps(text)
    return shown


def render(path):
    out = "$"
    for p in path:
        if isinstance(p, int):
            out += f"[{p}]"
        elif p.isidentifier():
            out += f".{p}"
        else:
            out += f"[{_json_string(p)}]"
    return out


def compare(a, b, exceptions=ENVIRONMENT_EXCEPTIONS, path=()):
    "Every difference between a and b as (path, what, a_part, b_part), skipping only the exempted paths."
    if path in exceptions:
        return []
    ta, tb = json_type(a), json_type(b)
    if ta != tb:
        return [(path, "type", ta, tb)]
    if ta in ("object", "array") and len(path) >= MAX_DEPTH:
        raise LimitExceededError(f"nesting depth {len(path) + 1} exceeds limit {MAX_DEPTH} at {render(path)}")
    if ta == "object":
        diffs = []
        if set(a) != set(b):
            diffs.append((path, "keys", sorted(set(a) - set(b)), sorted(set(b) - set(a))))
        elif list(a) != list(b):
            diffs.append((path, "key order", list(a), list(b)))
        for key in a:
            if key in b:
                diffs += compare(a[key], b[key], exceptions, (*path, key))
        return diffs
    if ta == "array":
        diffs = [] if len(a) == len(b) else [(path, "length", len(a), len(b))]
        for i, (x, y) in enumerate(zip(a, b, strict=False)):
            diffs += compare(x, y, exceptions, (*path, i))
        return diffs
    if ta == "decimal":  # exact value; == alone treats 0.0 and -0.0 as equal
        same = a == b and (not a.is_zero() or a.is_signed() == b.is_signed())
    else:
        same = a == b
    return [] if same else [(path, "value", a, b)]


def lookup(doc, path):
    for p in path:
        if not isinstance(doc, dict) or p not in doc:
            return "<missing>"
        doc = doc[p]
    return doc


def short(value, level=0):
    "Display text for a diagnostic line, never compared: every digit of a number, valid JSON numbers only."
    kind = type(value)
    if kind is Decimal:
        return str(value) if value.is_finite() else f"<non-finite Decimal {value}>"
    if kind is int:
        try:
            return str(value)
        except ValueError:  # beyond the interpreter's int/str digit limit (only from in-process callers)
            return f"<integer of {value.bit_length()} bits>"
    if kind is str:
        if len(value) <= SHOW_STRING_CHARS:
            return _json_string(value)
        digest = hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()[:16]
        return f"{_json_string(value[:SHOW_STRING_CHARS])}... ({len(value)} chars, sha256 {digest})"
    if value is None or kind is bool:
        return json.dumps(value)
    if kind in (list, dict) and level >= MAX_DEPTH:
        return "[...]" if kind is list else "{...}"
    if kind is list:
        return "[" + ", ".join(short(v, level + 1) for v in value) + "]"
    if kind is dict:
        return "{" + ", ".join(f"{short(k, level + 1)}: {short(v, level + 1)}" for k, v in value.items()) + "}"
    return f"<{kind.__name__}>"


def _tag(what, value):
    return f"{json_type(value)} value" if what == "value" else what


def _load_reporting(label, path):
    "(True, document), or (False, None) after printing why the input is invalid."
    try:
        return True, load(path)
    except LimitExceededError as err:
        print(f"INVALID INPUT ({label}, limit): {err}")
    except (OSError, ValueError) as err:
        print(f"INVALID INPUT ({label}): {err}")
    return False, None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: compare_results.py COMMITTED_JSON REPLAY_JSON")
        return 2
    docs = []
    for label, path in zip(("committed", "replay"), argv, strict=True):
        ok, doc = _load_reporting(label, path)
        if not ok:
            return 2
        docs.append(doc)
    a, b = docs
    for path in ENVIRONMENT_EXCEPTIONS:
        print(f"exempt {render(path)}: committed {short(lookup(a, path))} | replay {short(lookup(b, path))}")
    try:
        diffs = compare(a, b)
    except (InvalidJSONError, RecursionError) as err:
        print(f"UNSUPPORTED: {err}")
        return 2
    for path, what, x, y in diffs:
        print(f"DIFFERS {render(path)} ({_tag(what, x)}): committed {short(x)} | replay {short(y)}")
    print(f"differences outside the {len(ENVIRONMENT_EXCEPTIONS)} exempt paths: {len(diffs)}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())

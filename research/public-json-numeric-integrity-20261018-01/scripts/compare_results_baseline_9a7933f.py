"""Compare two JSON result documents completely and recursively.

Usage: python compare_results.py COMMITTED_JSON REPLAY_JSON
Every path is compared: the JSON type (true, 1 and 1.0 are three different values), object keys
and their order, array length and order, every scalar. Only the values at the exact paths in
ENVIRONMENT_EXCEPTIONS may differ, and their keys must exist on both sides. Duplicate object keys
and NaN/Infinity make an input invalid. Exit 0: no difference outside the exceptions;
1: differences, each printed with its path; 2: invalid or unreadable input.
Replaces compare_results_baseline_7345bfe.py, which compared a partial digest (D3).
"""

import json
import sys
from pathlib import Path

ENVIRONMENT_EXCEPTIONS = (("environment", "python"), ("environment", "platform"), ("environment", "machine"))


class InvalidJSONError(ValueError):
    pass


def _object(pairs):
    keys = [k for k, _ in pairs]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise InvalidJSONError(f"duplicate object key(s) {duplicates}")
    return dict(pairs)


def _constant(name):
    raise InvalidJSONError(f"non-standard JSON constant {name}")


def loads(text):
    return json.loads(text, object_pairs_hook=_object, parse_constant=_constant)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def as_json(value):
    "An in-memory output as a result file records it (e.g. lxml's str subclasses from xpath() become str)."
    return loads(json.dumps(value, ensure_ascii=False))


def json_type(value):
    for name, t in (("null", type(None)), ("boolean", bool), ("integer", int), ("float", float), ("string", str)):
        if type(value) is t:
            return name
    if type(value) is list:
        return "array"
    if type(value) is dict:
        return "object"
    raise TypeError(type(value))


def render(path):
    out = "$"
    for p in path:
        if isinstance(p, int):
            out += f"[{p}]"
        elif p.isidentifier():
            out += f".{p}"
        else:
            out += f"[{json.dumps(p, ensure_ascii=False)}]"
    return out


def compare(a, b, exceptions=ENVIRONMENT_EXCEPTIONS, path=()):
    "Every difference between a and b as (path, what, a_part, b_part), skipping only the exempted paths."
    if path in exceptions:
        return []
    ta, tb = json_type(a), json_type(b)
    if ta != tb:
        return [(path, "type", ta, tb)]
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
    same = repr(a) == repr(b) if ta == "float" else a == b  # repr keeps -0.0 and 0.0 apart
    return [] if same else [(path, "value", a, b)]


def lookup(doc, path):
    for p in path:
        if not isinstance(doc, dict) or p not in doc:
            return "<missing>"
        doc = doc[p]
    return doc


def short(value):
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 160 else text[:160] + f"... ({len(text)} chars)"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        a, b = load(argv[0]), load(argv[1])
    except (OSError, ValueError) as err:
        print(f"INVALID INPUT: {err}")
        return 2
    for path in ENVIRONMENT_EXCEPTIONS:
        print(f"exempt {render(path)}: committed {short(lookup(a, path))} | replay {short(lookup(b, path))}")
    diffs = compare(a, b)
    for path, what, x, y in diffs:
        print(f"DIFFERS {render(path)} ({what}): committed {short(x)} | replay {short(y)}")
    print(f"differences outside the {len(ENVIRONMENT_EXCEPTIONS)} exempt paths: {len(diffs)}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())

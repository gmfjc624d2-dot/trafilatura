"""Measure the JSON files already retained under research/ to size the comparator's limits.

Usage: python measure_retained.py REPO_ROOT OUTPUT_JSON
Reads the git-tracked research/**/*.json files listed by `git ls-files` (this directory
excluded) and records, per file: bytes, nesting depth (a scalar is 0, a container 1 + its
deepest child), longest string, and every number token as the json scanner hands it to the
parse_int / parse_float hooks (token length, integer digits, coefficient digits, exponent
digits). Hooks only record text; nothing is converted with a limit here. Standard library only.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

THIS = "research/public-json-numeric-integrity-20261018-01/"


def depth_and_strings(doc):
    "Iterative walk: (max depth, longest string in chars, number of object keys)."
    deepest, longest, keys, stack = 0, 0, 0, [(doc, 0)]
    while stack:
        node, level = stack.pop()
        if isinstance(node, dict):
            keys += len(node)
            longest = max([longest, *(len(k) for k in node)])
            stack += [(v, level + 1) for v in node.values()]
            deepest = max(deepest, level + 1)
        elif isinstance(node, list):
            stack += [(v, level + 1) for v in node]
            deepest = max(deepest, level + 1)
        elif isinstance(node, str):
            longest = max(longest, len(node))
    return deepest, longest, keys


def token_shape(token):
    body = token.removeprefix("-")
    mantissa, _, exponent = body.replace("E", "e").partition("e")
    return {
        "chars": len(token),
        "coefficient_digits": sum(c.isdigit() for c in mantissa),
        "exponent_digits": len(exponent.lstrip("+-")),
    }


def measure(path):
    data = path.read_bytes()
    ints, decs, constants, duplicates = [], [], [], []

    def pairs(items):
        names = [k for k, _ in items]
        duplicates.append(len(names) - len(set(names)))
        return dict(items)

    doc = json.loads(
        data.decode("utf-8"),
        parse_int=lambda t: ints.append(t) or 0,
        parse_float=lambda t: decs.append(t) or 0,
        parse_constant=lambda t: constants.append(t) or 0,
        object_pairs_hook=pairs,
    )
    duplicates = sum(duplicates)
    deepest, longest, keys = depth_and_strings(doc)
    shapes = [token_shape(t) for t in ints + decs]
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "depth": deepest,
        "longest_string_chars": longest,
        "object_keys": keys,
        "duplicate_keys": duplicates,
        "nonfinite_constants": constants,
        "integer_tokens": len(ints),
        "fraction_or_exponent_tokens": len(decs),
        "fraction_or_exponent_examples": sorted(set(decs), key=lambda t: (-len(t), t))[:5],
        "max_token_chars": max((s["chars"] for s in shapes), default=0),
        "max_integer_digits": max((token_shape(t)["coefficient_digits"] for t in ints), default=0),
        "max_coefficient_digits": max((token_shape(t)["coefficient_digits"] for t in decs), default=0),
        "max_exponent_digits": max((s["exponent_digits"] for s in shapes), default=0),
    }


def main():
    repo, out = Path(sys.argv[1]), Path(sys.argv[2])
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "research/*.json"], capture_output=True, text=True, check=True
    ).stdout.split()
    files = {p: measure(repo / p) for p in sorted(listed) if not p.startswith(THIS)}
    keys = ("bytes", "depth", "longest_string_chars", "max_token_chars", "max_integer_digits")
    keys += ("max_coefficient_digits", "max_exponent_digits", "fraction_or_exponent_tokens", "duplicate_keys")
    overall = {k: max(f[k] for f in files.values()) for k in keys}
    overall["files"] = len(files)
    overall["nonfinite_constants"] = sorted({c for f in files.values() for c in f["nonfinite_constants"]})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"overall": overall, "files": files}, indent=2) + "\n", encoding="utf-8", newline="\n")
    for p, f in files.items():
        print(
            f"{f['bytes']:7d} B depth {f['depth']:2d} ints {f['integer_tokens']:5d} dec {f['fraction_or_exponent_tokens']:4d}"
            f" maxint {f['max_integer_digits']:2d} maxcoef {f['max_coefficient_digits']:2d} {p}"
        )
    print(json.dumps(overall, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

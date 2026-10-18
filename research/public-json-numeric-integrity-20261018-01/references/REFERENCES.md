# Primary references (checked directly, not inherited)

`docs.python.org` was refused by this session's network policy (CONNECT 403, `logs/01_references.log`),
so the rendered pages named in the request could not be read here. The rendered documentation is
built from `Doc/library/*.rst` in the CPython repository. Those sources and the library code were
fetched at tag **v3.12.14** (tag object `4b65faa0b452113bf130086fb1519be6d9cd9b06`, commit
`2abcf904b8dac8c999d2b3aac76681abb333798a`), the intended native interpreter, and at **v3.12.3**,
the local Linux interpreter. They came from `raw.githubusercontent.com/python/cpython/<tag>/<path>`.
The current 3.12 web pages may show a later 3.12.x. Only short quotations are kept here; the git blob
ids identify the full files.

## Three kinds of statement

* **Documented**: quoted below from the v3.12.14 sources, with line numbers.
* **Policy**: what this repair chooses; it is in `fixtures/expectations.json` and was recorded before
  the repaired code existed.
* **Executed evidence**: observed on Linux, Python 3.12.3 (C `_json` scanner, libmpdec 2.5.1), in
  the logs. It is not a statement about v3.12.14 or macOS.

## Files

| path | v3.12.14 git blob | v3.12.3 git blob | local `/usr/lib/python3.12` |
|---|---|---|---|
| `Doc/library/json.rst` | `7c4d9bb518ea16ad23dc7e6db9c3d73eef8f5bfa` | `226d1c3d…` | n/a |
| `Doc/library/decimal.rst` | `654451f7f277340b6dabf11f1f1cd65783f23dbb` | `4d99c6d9…` | n/a |
| `Doc/library/stdtypes.rst` | `31b0f6f12544bc228bb5d855ebcb5867be507731` | `249a1c58…` | n/a |
| `Lib/json/scanner.py` | `090897515fe2f3818767a6dcf7b2310dca2c850a` | `7a61cfc2…` | identical to v3.12.3 |
| `Lib/json/decoder.py` | `5e5effeac02551c7732b88c55a870216c526dc52` | `c5d9ae2d…` | identical to v3.12.3 |
| `Lib/json/__init__.py` | `ed2c74771ea87ddc9349099c37b17d3cda213040` | same blob | identical |
| `Modules/_json.c` | `c90de05b046b0040d18d381bcf19e71f09f43dad` | same blob | (compiled) |

## json (`Doc/library/json.rst`, v3.12.14)

* L22-24: "Be cautious when parsing JSON data from untrusted sources. A malicious JSON string may
  cause the decoder to consume considerable CPU and memory resources. Limiting the size of data to
  be parsed is recommended."
* L289-294, `json.load(parse_float=)`: "If set, a function that is called with the string of every
  JSON float to be decoded. If `None` (the default), it is equivalent to `float(num_str)`. This can
  be used to parse JSON floats into custom datatypes, for example `decimal.Decimal`."
* L297-302, `parse_int`: "called with the string of every JSON int to be decoded. If `None` (the
  default), it is equivalent to `int(num_str)`."
* L305-310, `parse_constant`: "called with one of the following strings: `'-Infinity'`,
  `'Infinity'`, or `'NaN'`. This can be used to raise an exception if invalid JSON numbers are
  encountered."
* L279-285, `object_pairs_hook`: "called with the result of any object literal decoded with an
  ordered list of pairs."
* L330-335: "Changed in version 3.11: The default *parse_int* of `int()` now limits the maximum
  length of the integer string via the interpreter's integer string conversion length limitation".
* L666-678, repeated names: "this module does not raise an exception; instead, it ignores all but
  the last name-value pair for a given name".
* L705-706: "This module does not impose any such limits beyond those of the relevant Python
  datatypes themselves or the Python interpreter itself." The list above it includes nesting depth
  and the range and precision of numbers.
* L178-183, `dumps(allow_nan=False)`: "serialization of out-of-range `float` values (`nan`, `inf`,
  `-inf`) will result in a `ValueError`".

## The scanner (`Lib/json/scanner.py`, `Modules/_json.c`, v3.12.14)

* `scanner.py` L11-13 and L50-54, the pure-Python scanner: the number pattern is
  `(-?(?:0|[1-9][0-9]*))(\.[0-9]+)?([eE][-+]?[0-9]+)?`. Then
  `res = parse_float(integer + (frac or '') + (exp or ''))` if there is a fraction or an exponent,
  otherwise `res = parse_int(integer)`. The hook therefore receives the token text **after** the
  lexical match.
* `_json.c` L967-981, the C scanner used by default (`make_scanner = c_make_scanner or
  py_make_scanner`): if `parse_float` is not `float` (or `parse_int` is not `int`), it copies "the
  section we determined to be a number" and calls the hook with it. Otherwise it calls
  `PyFloat_FromString` / `PyLong_FromString` directly (L983-998). Digits are matched as
  `'0'`..`'9'` only.
* `_json.c` L1043-1056: nested objects and arrays are entered through `_Py_EnterRecursiveCall`, so
  nesting is bounded only by the interpreter's recursion limit (`RecursionError`).
* **Difference between v3.12.3 and v3.12.14** (`logs/01_references.log`): `_json.c` is identical,
  but the v3.12.3 pure-Python pattern uses `\d` (`(-?(?:0|[1-9]\d*))(\.\d+)?([eE][-+]?\d+)?`). In a
  `str` pattern without `re.ASCII`, `\d` also matches non-ASCII Unicode decimal digits. On v3.12.3
  the fallback scanner can therefore hand such digits to the hooks. Policy: the hooks accept ASCII
  JSON number characters only.

## decimal (`Doc/library/decimal.rst`, v3.12.14)

* L346-353, `Decimal(value)`: a string "should conform to the decimal numeric string syntax after
  leading and trailing whitespace characters, as well as underscores throughout, are removed".
  L366-369: "Other Unicode decimal digits are also permitted where `digit` appears above." The
  constructor accepts more than JSON does, which is a second reason for the ASCII check.
* L382-385: "The *context* precision does not affect how many digits are stored. That is determined
  exclusively by the number of digits in *value*."
* L387-390: "The purpose of the *context* argument is determining what to do if *value* is a
  malformed string. If the context traps `InvalidOperation`, an exception is raised; otherwise, the
  constructor returns a new Decimal with the value of `NaN`."
* L642-643, `is_signed()`: "Return `True` if the argument has a negative sign and `False` otherwise.
  Note that zeros and NaNs can both carry signs."
* L1839-1842: signed zeros "keep the sign that would have resulted if the calculation had been
  carried out to greater precision. Since their magnitude is zero, both positive and negative zeros
  are treated as equal and their sign is informational." `==` therefore cannot separate `0.0` from
  `-0.0`. The policy adds `is_signed()` for zeros.
* L133: the default context has `Emax=999999`. L1541: `MAX_EMAX` is `999999999999999999` on
  64-bit. Context exponent bounds govern arithmetic results. The text above does not say that they
  bound a value constructed from a string. Whether they do is executed evidence here
  (`interpreter_observations.json`), not a documented guarantee, and it is why exponent text is
  bounded before conversion.

## Integer string conversion (`Doc/library/stdtypes.rst`, v3.12.14, section `int_max_str_digits`)

* L5541-5542: "The limit is applied to the number of digit characters in the input or output string
  when a non-linear conversion algorithm would be involved."
* L5567: "The default limit is 4300 digits".
* L5589-5606: the limit applies to `int(string)`, `str(integer)`, `repr(integer)`. It does **not**
  apply to "`str` to `float`" or "`str` to `decimal.Decimal`". A long coefficient or exponent in a
  JSON fraction token is therefore not covered by the interpreter's protection. This repair adds its
  own limits and leaves the global setting untouched.

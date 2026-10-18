# Source, attribution and license of the documentation excerpts

**What is excerpted.** 23 short passages of the Python 3.12 documentation page
"urllib.request — Extensible library for opening URLs",
<https://docs.python.org/3.12/library/urllib.request.html>, taken from the reST source that
page is built from:

| | |
|---|---|
| repository | <https://github.com/python/cpython> (public), branch `3.12` |
| commit | `58ed60b7415e218ce3d608302e39b5e55bfb0e88` (2026-10-01T19:49:16Z) |
| file | `Doc/library/urllib.request.rst`, git blob `09a8c0edc5ef7b58f5547d2f4584f13d451f90da`, sha256 `55e3d9c4988694d529b6856af5ce7b691233821b7f1bf563d4d3dd265b3b7d5f`, 63203 bytes (not retained in full) |
| retained | `urllib.request.rst.excerpts.json`: the exact source lines of each excerpt with line numbers and sha256 |
| retrieved | 2026-10-18, anonymous `git clone --depth 1 --filter=blob:none --sparse --branch 3.12` |

**Why the reST source and not the HTML page.** A direct request for the HTML page from this
Linux session was refused by the session's network policy (`CONNECT tunnel failed, response
403`, `logs/00_source_fetch_docs_python_org.log`). No HTML byte was used. The plain text in
`../fixtures/urllib_request_3.12_excerpts.txt` is this benchmark's rendering of the source
lines (rules below), so it can differ in small ways from the text shown on the HTML page.

**Copyright.** Copyright © 2001-2023 Python Software Foundation. All rights reserved.
Copyright © 2000 BeOpen.com. All rights reserved. Copyright © 1995-2000 Corporation for National
Research Initiatives. All rights reserved. Copyright © 1991-1995 Stichting Mathematisch Centrum.
All rights reserved. (`Doc/copyright.rst` at the commit above.)

**License.** "Python software and documentation are licensed under the Python Software
Foundation License Version 2" (`Doc/license.rst`). The license agreement is retained verbatim in
`LICENSE-PSF-cpython-3.12` (CPython's `LICENSE` at the commit above, sha256
`3b2f81fe21d181c499c59a256c8e1968455d6689d269aa85373bfb6af41da3bf`), as its clause 2 requires.
The excerpts stay under that license; everything else in this directory (code, synthetic
fixture, oracle, results) is original to this benchmark and under the repository's Apache-2.0
license.

**Summary of changes (PSF License clause 3).** Selected paragraphs, signatures and admonitions
only, each rendered to one line of plain text by `scripts/build_fixtures.py`:
`` ``literal`` `` and `*emphasis*` markup removed; roles shown by their target (`~` keeps the last
dotted component, `:func:`/`:meth:` get `()`); line breaks and repeated spaces collapsed;
signatures prefixed `urllib.request.` / `class urllib.request.` as on the HTML page;
`.. note::`, `.. warning::`, `.. versionchanged:: X` and `.. deprecated:: X` rendered as
`Note: `, `Warning: `, `Changed in version X: ` and `Deprecated since version X.`.
No wording was changed.

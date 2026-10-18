# Two-parser corroboration for explicit Sphinx API ids (lxml + html5lib 1.1)

Request `public-sphinx-parser-corroboration-20261018-01`, continuing
`5c41ba875753666d0b3fb780e14f046f77a7ad01`. Local head and remote were both that commit, so the
branch had not moved. **Linux evidence only** (Python 3.12.3, lxml 6.1.3, libxml2 2.14.6, html5lib
1.1, x86_64). It is not macOS qualification.

The deliverable is structural evidence for triage. It is not admission, not a new extractor or
router, and not a claim that two parsers establish source truth.

The existing conservative policy is kept unchanged: `anchor_unit.py` (sha256 `9c013517…`) runs
pinned and read-only, so any lxml diagnostic still means REVIEW.

Order of work, each step pushed before the next:
* `6df1d6f`: pre-registration (`fixtures/expectations.json`), committed before the module, replay
  and tests existed and before html5lib parsed a fixture.
* the results commit.
* the fresh-clone recovery check.

## 1. Acquisition and provenance (`wheels/`, `logs/00`-`03`)

| wheel | sha256 | uploaded | license (notice kept) | declares |
|---|---|---|---|---|
| `html5lib-1.1-py2.py3-none-any.whl` (112173 B) | `0d78f8fd…e041d` | 2020-06-22 | MIT (dist-info LICENSE, AUTHORS.rst) | `six (>=1.9)`, `webencodings`; extras only for genshi, chardet, lxml |
| `six-1.17.0-py2.py3-none-any.whl` (11050 B) | `4721f391…c3274` | 2024-12-04 | MIT (dist-info LICENSE) | none |
| `webencodings-0.5.1-py2.py3-none-any.whl` (11774 B) | `a0af1213…14a78` | 2017-04-05 | BSD (see below) | none |

**Checks on the bytes.** The registry digest and size were checked, then the bytes themselves:

* `scripts/verify_wheels.py` (standard library only) checks zip integrity, every RECORD hash and
  size (38, 5 and 10 entries), the METADATA name, version, license and requirements, the WHEEL
  purelib flag and tags, the absence of native members, the license notices, and that
  `wheels/requirements.lock` pins exactly these hashes (`logs/02_verify_wheels.log`).
* Neither the webencodings 0.5.1 wheel nor its sdist contains a license file. Its METADATA says
  `License: BSD`, and its `__init__.py` says "see LICENSE". The notice kept is the LICENSE at the
  project's `v0.5.1` tag (lightweight tag, commit `fa2cb5d7…`, blob `3d0d3e70…`).

**Release history and choices.**

* html5lib 1.1 is its latest PyPI release (2020-06-22). Its classifiers stop at Python 3.8. Running
  it on 3.12 here is executed evidence on Linux, not a compatibility claim for macOS, and its age
  says nothing about whether the project is maintained.
* six 1.17.0 is the latest six; its `six.py` defines `find_spec`.
* webencodings 0.5.1 is the release html5lib 1.1 was published with. 0.6.0 and 0.6.1 (both
  2026-08-15, Python >=3.10, with moved project URLs) also satisfy the unversioned requirement. They
  were not chosen because html5lib 1.1 was not examined with them here.

**Alternatives.** TurboHTML was not acquired or benchmarked: no performance bottleneck has been
identified. Its macOS arm64 wheel is the request's statement and was not checked here. html5lib was
selected for integration simplicity (pure Python, stdlib ElementTree), not for demonstrated
maintenance or speed.

**Chronology** (`logs/00_acquisition_chronology.md`): the first acquisition was not written to a
log at the time. It is summarised from the session, with that gap kept. A second, logged download
followed (`logs/01_acquisition.log`); it was not needed and is byte-identical to the first.

**Environment** (`logs/03_environment.log`), all untracked and outside the repository:
* a fresh venv holding only lxml 6.1.3, installed offline from the local uv cache (this is the
  existing lxml; no native wheel is retained);
* the three retained wheels installed by
  `pip install --no-index --find-links wheels --require-hashes --target <site>`;
* every run inside `unshare -rn`;
* chardet not importable.

## 2. The parsing contract

* **Both parsers get the complete original bytes.** lxml uses
  `lxml.html.document_fromstring(data, parser=HTMLParser())`, as the helper does. html5lib uses
  `HTMLParser(tree=getTreeBuilder("etree"), strict=False, namespaceHTMLElements=True, debug=False)`
  and `.parse(data, override_encoding=None, transport_encoding=None, useChardet=False,
  scripting=False)`. All of these options are written into every report.
* **Why `strict=False`.** `strict=True` raises `ParseError` at N1's first error; a negative-control
  test shows this. With `strict=False` every error is kept.
* **The returned root.** `getTreeBuilder("etree")` uses the stdlib `xml.etree.ElementTree` with
  `fullTree=False`, so `parse()` returns the html element.
* **Decoding policy.** html5lib 1.1 checks a BOM first and only then `override_encoding`, which is
  the keyword in 1.1: the `parse()` docstring still says "encoding". After that it uses
  `transport_encoding`, a meta prescan of the first 1024 bytes, chardet only if enabled and
  installed, and finally windows-1252. A meta charset equal to the prescan upgrades certainty to
  `certain`. Each parser's choice is recorded and compared through `codecs.lookup(name).name`.
  A disagreement is REVIEW; this is unit-tested by a mutation, since no fixture disagrees. Nothing
  is re-encoded.
* **Names.** html5lib tags `{http://www.w3.org/1999/xhtml}x` map to `x`, and that is the only
  mapping. Other namespaces keep their full tag and never match dt/dd/dl/a. lxml tags are used as
  they are. Comments and PIs are their own node kinds in both trees.
* **Selection rule.** The `anchor_unit.py` rule is mirrored over one small node view of each tree:
  * every exact id match is listed, with document order (and lxml's sourceline);
  * more than one match gives no unit, never a first-match choice;
  * the unit is the dt/dd group, with boundaries (dl, its parent, all dl children, neighbours,
    enclosing object), ordered topology and links.

  The mirror is checked against `select_unit()` on the lxml tree (reasons, membership, text). It
  agrees on all 8 cases.
* **Text rule.** An element's text is its text, then each child's text and tail in order. Comment
  and PI data are excluded but their tails kept. Tails between top-level unit elements are
  included; the last element's tail is excluded. There is no normalisation, and equality means
  exact string equality.

## 3. Results (`results/run1-linux-py3.12/`, `logs/10_replay_run1.log`)

| case | helper (unchanged policy) | lxml diagnostics | html5lib errors | descriptions lxml / html5lib | unit text equal | disposition |
|---|---|---|---|---|---|---|
| N1 late diagnostic | REVIEW | line 3 ERR_TAG_NAME_MISMATCH | line 3 unexpected-end-tag span | 1 / 1 | yes | REVIEW |
| N2 comment lookalike | OK_STRUCTURAL_UNIT | none | none | 1 / 1 | yes | STRUCTURE_CORROBORATED |
| N3 windows-1252 | OK_STRUCTURAL_UNIT | none | none (encoding windows-1252, certain) | 1 / 1 | yes | STRUCTURE_CORROBORATED |
| N4 external diagnostic | REVIEW | line 12 | line 12 unexpected-end-tag span | 1 / 1 | yes | REVIEW |
| N5 clean | OK_STRUCTURAL_UNIT | none | none | 1 / 1 | yes | STRUCTURE_CORROBORATED |
| C17 duplicate live id (existing case, not a new discovery) | REVIEW | line 19 DTD_ID_REDEFINED | none | no unit in either tree (2 matches each) | - | REVIEW |
| C1 dd reparenting (new) | **OK_STRUCTURAL_UNIT** | none | 2 | **1 / 2** | yes | REVIEW |
| C2 text/tail (new) | OK_STRUCTURAL_UNIT | none | 1 | 1 / 1 | yes | REVIEW |

There were 289 checks: 275 pass, 2 fail and 12 recorded without a prediction.

The new fixtures show what the second parser adds. In **C1**, the lxml-only policy accepts the unit
(no diagnostic, one description), while HTML5 tree construction closes the first `dd` and reads two.
Membership, boundaries and topology differ even though the unit texts are identical, so the case is
REVIEW. This shows that equal text is not structural agreement. It does not say which parser is
"right".

In **C2**, both trees exclude the comment and the `<?pi …?>` data, keep their tails, and drop the
final dd tail. Both texts equal the expected `tail()¶\nAlpha Beta Gamma Delta Epsilon, see
pkg.other.`. html5lib reports `expected-tag-name-but-got-question-mark`, so the case is REVIEW.
The whole-unit byte counts in the reports are sizes only: they do not mean that any caller's prompt
fits, and nothing is truncated.

## 4. Every failure and unexpected observation (all kept)

* **C1, prediction wrong:** I predicted `unexpected-end-tag` for the second error. html5lib 1.1
  reports `end-tag-too-early` (`div`, line 11, col 26): its block end-tag handler uses that code
  whether or not the element is still in scope. The tree is as predicted.
* **C2, a real ElementTree behaviour:** the check that the text rule equals `itertext()` fails. On
  CPython 3.12.3 the C-accelerated `Element.itertext()` yields comment data, while the pure-Python
  implementation does not (`logs/12_posthoc_itertext.log`, post-hoc). So `itertext()` is not the
  text rule, and the explicit rule is what the reports use. Consequences, unchanged since the run:
  * the check fails and adds `CONSISTENCY_CHECK_FAILED` (C2 is REVIEW either way);
  * two focused tests that assumed `itertext()` skips comments fail (`logs/11_unittest_run1.log`:
    13 tests, 11 OK, 2 FAIL).

  The tests and predictions were not edited.
* **Recorded without prediction (C2):** lxml reported no diagnostic, the helper said
  OK_STRUCTURAL_UNIT, and libxml2 2.14.6 turned `<?pi …?>` into a comment node, as html5lib did, so
  the topologies agree.
* **Recorded (C17):** html5lib reports no error for the duplicate ids; libxml2 reports
  `DTD_ID_REDEFINED`.

## 5. Limits

* Eight synthetic or earlier-public fixtures, one interpreter. html5lib's error codes and positions
  are html5lib's own, not spec error codes. libxml2 2.14's tree construction is its own and is not
  HTML5's.
* STRUCTURE_CORROBORATED is only "two repaired interpretations agree". It gives no consumer
  permission, says nothing about semantic completeness, and is no admission.
* The itertext check makes any unit containing a comment fail consistency on this CPython build,
  which is a conservative REVIEW. It was not changed after the run.

## 6. Commands (Linux, from this directory) and macOS replay

| command | exit | log |
|---|---|---|
| `python3.12 -I scripts/verify_wheels.py` | 0 | `logs/02_verify_wheels.log` |
| environment build (uv venv, offline lxml, pip `--target` with `--require-hashes`) | 0 | `logs/03_environment.log` |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<site> <venv>/bin/python -W default scripts/replay.py results/run1-linux-py3.12` | 1 (2 kept failures) | `logs/10_replay_run1.log` |
| `… -m unittest discover -s scripts -v` | 1 (2 kept failures) | `logs/11_unittest_run1.log` |

No warnings were printed under `-W default`. No old suite, fixture builder, live documentation,
model or network was used after acquisition.

**macOS, Python 3.12, offline after the clone (not run here).** You need an existing Python 3.12
with lxml (Linux used lxml 6.1.3 and libxml2 2.14.6). Outputs go outside the clone:

```sh
git clone --branch claude/adoring-turing-3ekxhe https://github.com/gmfjc624d2-dot/trafilatura.git "$HOME/trafilatura-corroboration"
R="$HOME/trafilatura-corroboration/research/public-sphinx-parser-corroboration-20261018-01"
OUT="$HOME/corroboration-replay-$(date -u +%Y%m%dT%H%M%SZ)"; PY=python3.12   # the interpreter where `import lxml` works
cd "$R" && git rev-parse HEAD                     # compare with the reported head
shasum -a 256 -c SHA256SUMS && shasum -a 256 -c PREREGISTERED.sha256
"$PY" -I scripts/verify_wheels.py                 # wheel bytes, RECORD, METADATA, licenses, lock
# disconnect the network from here on
"$PY" -m pip install --no-index --find-links "$R/wheels" --require-hashes --target "$OUT/site" -r "$R/wheels/requirements.lock"
"$PY" -c "import lxml, lxml.etree as e; print(lxml.__version__, e.LIBXML_VERSION)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$OUT/site" "$PY" -W default scripts/replay.py "$OUT/run" --against results/run1-linux-py3.12; echo "exit=$?"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$OUT/site" "$PY" -W default -m unittest discover -s scripts -v
git status --short                                # empty: nothing written into the clone
```

* **Replay exit.** 1 is expected from the two kept check failures, unless the C ElementTree on that
  build skips comment data. The `--against` comparison lets only `environment.python`, `.platform`
  and `.machine` differ, so another lxml/libxml2 version is reported as a difference. Treat that as
  a finding to report, not something to edit.
* **pip.** pip 24.0 skips the externally-managed check for `--target` (source-observed). If a
  macOS pip refuses anyway, install into a venv created from that same interpreter.

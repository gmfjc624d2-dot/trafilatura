"""Corroborate one explicit Sphinx API id with two parsers: structural evidence for triage only.

Usage: python corroborate.py FILE ANCHOR [LOCATOR]    # prints the JSON report for one source/anchor
Both parsers get the complete original bytes. The lxml side runs the pinned anchor_unit.py
(research/public-sphinx-evidence-integrity-20261018-01) unchanged, so its conservative policy
holds: any lxml diagnostic means REVIEW. html5lib 1.1 runs with the stdlib ElementTree builder,
strict=False (strict mode stops at the first error) and namespaceHTMLElements=True. The
anchor_unit.py selection rule is mirrored over both trees through one small node view, and the
mirror is checked against select_unit() on the lxml tree.

STRUCTURE_CORROBORATED means only that two repaired interpretations agree. It is not admission
and gives no consumer permission. The whole-unit byte count does not mean that any caller's
prompt fits, and nothing is truncated. Policy and predictions: fixtures/expectations.json.
"""

import codecs
import hashlib
import json
import platform
import sys
import types
import unicodedata
from pathlib import Path
from urllib.parse import unquote

import html5lib
import lxml
import lxml.html
import six
import webencodings
from html5lib import _utils as html5lib_utils
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
HELPER = "research/public-sphinx-evidence-integrity-20261018-01/scripts/anchor_unit.py"
HELPER_SHA256 = "9c01351705ca8fe475df3925550d015cf69d4cbda324d042e32f0c909ec404e9"
XHTML = "{http://www.w3.org/1999/xhtml}"
ET = html5lib_utils.default_etree  # the ElementTree module html5lib's "etree" builder uses
HTML5LIB_OPTIONS = {"tree": "getTreeBuilder('etree')", "strict": False, "namespaceHTMLElements": True, "debug": False}
HTML5LIB_PARSE_KWARGS = {"override_encoding": None, "transport_encoding": None, "useChardet": False, "scripting": False}
LXML_OPTIONS = (
    "lxml.html.document_fromstring(data, parser=lxml.html.HTMLParser()) with its defaults, as anchor_unit.select_unit()"
)
SHOWN_ATTRS = ("id", "class", "href")
NOT_CLAIMED = [
    "admission or any consumer permission",
    "that the unit is semantically complete or answers any question",
    "that two parsers establish source truth",
    "that the unit's byte count fits any caller's final prompt",
    "source byte positions (no serialization search, no lexical id counts)",
    "equality after any text normalisation",
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_helper():
    "Execute the pinned anchor_unit.py bytes as a module, without writing bytecode into earlier research."
    data = (REPO / HELPER).read_bytes()
    if sha256(data) != HELPER_SHA256:
        raise RuntimeError(f"{HELPER} differs from its pinned sha256")
    module = types.ModuleType("anchor_unit_evidence_integrity")
    module.__file__ = str(REPO / HELPER)
    exec(compile(data, module.__file__, "exec"), module.__dict__)  # the bytes just verified, nothing re-read
    return module


helper = load_helper()


def environment():
    return {
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "lxml": lxml.__version__,
        "libxml2_runtime": ".".join(map(str, etree.LIBXML_VERSION)),
        "libxml2_compiled": ".".join(map(str, etree.LIBXML_COMPILED_VERSION)),
        "html5lib": html5lib.__version__,
        "six": six.__version__,
        "webencodings": webencodings.VERSION,
        "elementtree": ET.__name__,
    }


class Node:
    "One node of either tree: kind element/comment/pi/other, the mapped name, attributes, text and tail."

    __slots__ = ("attrs", "children", "kind", "name", "native", "parent", "tail", "text")

    def __init__(self, native, kind, name, parent):
        self.native, self.kind, self.name, self.parent = native, kind, name, parent
        self.attrs = dict(native.attrib) if kind == "element" else {}
        self.text, self.tail, self.children = native.text, native.tail, []


def lxml_kind(el):
    if el.tag is etree.Comment:  # lxml gives comments and PIs their factory function as tag
        return "comment", None
    if el.tag is etree.ProcessingInstruction:
        return "pi", el.target
    if isinstance(el.tag, str):
        return "element", el.tag  # lxml.html tags carry no namespace
    return "other", repr(el.tag)


def et_kind(el):
    if el.tag is ET.Comment:
        return "comment", None
    if el.tag is ET.ProcessingInstruction:
        return "pi", None
    if isinstance(el.tag, str) and el.tag.startswith(XHTML):
        return "element", el.tag[len(XHTML) :]  # the one explicit mapping: the XHTML namespace to its local name
    if isinstance(el.tag, str) and el.tag.startswith("{"):
        return "element", el.tag  # other namespaces keep the full tag and never match dt/dd/dl/a
    return "other", str(el.tag)


def view(root, kind_of):
    top = Node(root, *kind_of(root), None)
    stack = [top]
    while stack:
        node = stack.pop()
        for child in node.native if node.kind == "element" else ():
            n = Node(child, *kind_of(child), node)
            node.children.append(n)
            stack.append(n)
    return top


def preorder(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def element(n, name):
    return n is not None and n.kind == "element" and n.name == name


def classes(n):
    return set((n.attrs.get("class") or "").split())


def is_signature(n):
    return element(n, "dt") and {"sig", "sig-object"} <= classes(n)


def object_of(dl):
    return next((c for c in dl.children if is_signature(c)), None)


def groups_of(dl):
    groups, current = [], None
    for c in dl.children:
        if element(c, "dt"):
            if current is None or current[1]:
                current = ([], [])
                groups.append(current)
            current[0].append(c)
        elif element(c, "dd"):
            if current is None:
                current = ([], [])
                groups.append(current)
            current[1].append(c)
    return groups


def has_stray_content(dl):
    texts = [dl.text] + [c.tail for c in dl.children]
    return any(t and t.strip() for t in texts) or any(not (element(c, "dt") or element(c, "dd")) for c in dl.children)


def ancestors(n):
    n = n.parent
    while n is not None:
        yield n
        n = n.parent


def nearest_object_dl(n):
    for anc in ancestors(n):
        if element(anc, "dd") and element(anc.parent, "dl") and object_of(anc.parent) is not None:
            return anc.parent
    return None


def is_container(dl):
    return bool(helper.CONTAINER_OBJTYPES & classes(dl))


def text_of(n):
    "The text rule: element text, then each child's text and tail in order; comment/pi data excluded, tails kept."
    if n.kind != "element":
        return ""
    return (n.text or "") + "".join(text_of(c) + (c.tail or "") for c in n.children)


def unit_text(unit):
    last = len(unit) - 1
    return "".join(text_of(e) + ((e.tail or "") if i < last else "") for i, e in enumerate(unit))


def describe(n):
    return None if n is None else {"kind": n.kind, "name": n.name, **{k: n.attrs[k] for k in SHOWN_ATTRS if k in n.attrs}}


def topology(unit):
    out = []
    for top in unit:
        stack = [(top, 0)]
        while stack:
            n, depth = stack.pop()
            out.append([depth, n.kind, n.name, {k: n.attrs[k] for k in SHOWN_ATTRS if k in n.attrs}])
            stack.extend((c, depth + 1) for c in reversed(n.children))
    return out


def select(root, anchor, order_note):
    "The anchor_unit.py rule over one tree: every exact match, the structural reasons and the whole unit."
    elements = [n for n in preorder(root) if n.kind == "element"]
    exact = [(i, n) for i, n in enumerate(elements) if n.attrs.get("id") == anchor]
    ids = {n.attrs["id"] for n in elements if "id" in n.attrs}
    near = sorted(
        i
        for i in ids
        if i != anchor and (unicodedata.normalize("NFC", i) == unicodedata.normalize("NFC", anchor) or i == unquote(anchor))
    )
    out = {
        "exact_matches": [
            {"document_order": i, "element": describe(n), "parent": describe(n.parent), **order_note(n)} for i, n in exact
        ],
        "match_count": len(exact),
        "near_matches": near,
        "rule_reasons": [],
        "unit": None,
    }
    reasons = out["rule_reasons"]
    if not exact:
        reasons.append("ID_NORMALIZATION_MISMATCH" if near else "MISSING_ID")
        return out
    if len(exact) > 1:
        reasons.append("DUPLICATE_ID")  # never a first-match choice
        return out
    dt = exact[0][1]
    if not element(dt, "dt"):
        reasons.append("NOT_A_SIGNATURE")
        return out
    if not is_signature(dt) or not element(dt.parent, "dl"):
        reasons.append("NOT_SPHINX_OBJECT")
        return out
    dl = dt.parent
    groups = groups_of(dl)
    dts, dds = next(g for g in groups if dt in g[0])
    if len(groups) > 1:
        reasons.append("MULTIPLE_GROUPS_IN_OBJECT_DL")
    if has_stray_content(dl):
        reasons.append("STRAY_CONTENT_IN_OBJECT_DL")
    if not dds:
        reasons.append("NO_DESCRIPTION")
    elif all(not d.children and not (d.text or "").strip() for d in dds):
        reasons.append("EMPTY_DESCRIPTION")
    nested = [d for dd in dds for d in preorder(dd) if d is not dd and is_signature(d)]
    enclosing = nearest_object_dl(dl)
    if (nested and not is_container(dl)) or (enclosing is not None and not is_container(enclosing)):
        reasons.append("UNEXPECTED_NESTED_OBJECT")
    unit = [c for c in dl.children if c in dts or c in dds]
    siblings = [c for c in dl.children if c.kind == "element"]
    first, last = siblings.index(unit[0]), siblings.index(unit[-1])
    text = unit_text(unit)
    out["unit"] = {
        "membership": {
            "signature_ids": [d.attrs.get("id") for d in dts],
            "signatures": len(dts),
            "descriptions": len(dds),
            "anchor_position": dts.index(dt) + 1,
            "nested_object_ids": [d.attrs.get("id") for d in nested],
        },
        "boundaries": {
            "dl": describe(dl),
            "dl_parent": describe(dl.parent),
            "dl_children": [[c.kind, c.name] for c in dl.children],
            "unit_element_indexes": [first, last],
            "previous_element": describe(siblings[first - 1]) if first > 0 else None,
            "next_element": describe(siblings[last + 1]) if last + 1 < len(siblings) else None,
            "enclosing_object_id": object_of(enclosing).attrs.get("id") if enclosing is not None else None,
        },
        "topology": topology(unit),
        "links": [{"href": a.attrs.get("href"), "text": text_of(a)} for e in unit for a in preorder(e) if element(a, "a")],
        "text": text,
        "text_utf8_bytes": len(text.encode("utf-8")),
        "text_sha256": sha256(text.encode("utf-8")),
        "_unit_nodes": unit,  # removed before the report is written
    }
    return out


def parse_lxml(data, anchor):
    parser = lxml.html.HTMLParser()
    doc = lxml.html.document_fromstring(data, parser=parser)
    diagnostics = [
        {"line": e.line, "column": e.column, "level": e.level_name, "type": e.type_name, "message": e.message.strip()}
        for e in parser.error_log
    ]
    tree = select(view(doc.getroottree().getroot(), lxml_kind), anchor, lambda n: {"sourceline": n.native.sourceline})
    return {"encoding": doc.getroottree().docinfo.encoding, "diagnostics": diagnostics}, tree


def plain(value):
    return value if isinstance(value, (str, int, bool, type(None))) else repr(value)


def parse_html5lib(data, anchor):
    parser = html5lib.HTMLParser(tree=html5lib.getTreeBuilder("etree"), strict=False, namespaceHTMLElements=True, debug=False)
    root = parser.parse(data, **HTML5LIB_PARSE_KWARGS)
    errors = [
        {"line": pos[0], "col": pos[1], "code": code, "data": {k: plain(v) for k, v in (datavars or {}).items()}}
        for pos, code, datavars in parser.errors
    ]
    certainty = parser.tokenizer.stream.charEncoding[1]
    tree = select(view(root, et_kind), anchor, lambda _n: {})
    return {"encoding": parser.documentEncoding, "encoding_certainty": certainty, "errors": errors, "root": root.tag}, tree


def codec(name):
    try:
        return codecs.lookup(name).name
    except (LookupError, TypeError):
        return None


def compare(lx, h5, lx_tree, h5_tree):
    "Comparison findings (evidence), kept apart from the disposition derived from them."
    findings, agreements = [], []
    if lx["diagnostics"]:
        findings.append({"finding": "LXML_DIAGNOSTICS_PRESENT", "count": len(lx["diagnostics"])})
    if h5["errors"]:
        findings.append({"finding": "HTML5LIB_ERRORS_PRESENT", "count": len(h5["errors"])})
    pair = (codec(lx["encoding"]), codec(h5["encoding"]))
    if pair[0] is None or pair[0] != pair[1]:
        findings.append({"finding": "ENCODING_DISAGREEMENT", "lxml": lx["encoding"], "html5lib": h5["encoding"]})
    else:
        agreements.append("encoding")
    for name, tree in (("lxml", lx_tree), ("html5lib", h5_tree)):
        if tree["match_count"] != 1:
            findings.append(
                {
                    "finding": "ID_NOT_UNIQUE" if tree["match_count"] else "ID_MISSING",
                    "parser": name,
                    "matches": tree["match_count"],
                }
            )
        if tree["rule_reasons"]:
            findings.append({"finding": "STRUCTURAL_REASONS_PRESENT", "parser": name, "reasons": tree["rule_reasons"]})
    if lx_tree["match_count"] != h5_tree["match_count"]:
        findings.append({"finding": "MATCH_COUNT_DIFFERS", "lxml": lx_tree["match_count"], "html5lib": h5_tree["match_count"]})
    if lx_tree["rule_reasons"] != h5_tree["rule_reasons"]:
        findings.append(
            {"finding": "STRUCTURAL_REASONS_DIFFER", "lxml": lx_tree["rule_reasons"], "html5lib": h5_tree["rule_reasons"]}
        )
    a, b = lx_tree["unit"], h5_tree["unit"]
    if (a is None) != (b is None):
        findings.append({"finding": "UNIT_PRESENCE_DIFFERS", "lxml": a is not None, "html5lib": b is not None})
    elif a is not None:
        for aspect in ("membership", "boundaries", "topology", "links", "text"):
            if a[aspect] == b[aspect]:
                agreements.append(aspect)
            else:
                findings.append({"finding": f"{aspect.upper()}_DIFFERS"})
    return findings, agreements


def report(data, anchor, locator):
    "The complete JSON-ready report for one source/anchor."
    found = helper.select_unit(data, anchor, path=locator, origin="public fixture", budget=helper.BUDGET_BYTES)
    lx, lx_tree = parse_lxml(data, anchor)
    h5, h5_tree = parse_html5lib(data, anchor)
    cand = found["candidate"]
    checks = {
        "lxml_parse_diagnostics_equal_helper": lx["diagnostics"] == found["parser"]["diagnostics"],
        "mirror_reasons_equal_helper": lx_tree["rule_reasons"]
        == [r for r in found["reasons"] if r != "PARSER_DIAGNOSTICS_PRESENT"],
        "mirror_membership_equals_helper": (lx_tree["unit"] is None) == (cand is None)
        and (
            cand is None
            or [cand["signature_ids"], cand["descriptions"]]
            == [lx_tree["unit"]["membership"]["signature_ids"], lx_tree["unit"]["membership"]["descriptions"]]
        ),
        "lxml_text_rule_equals_helper_text_content": None
        if cand is None or lx_tree["unit"] is None
        else lx_tree["unit"]["text"] == cand["text_content"],
        "html5lib_text_rule_equals_itertext": None,
    }
    if h5_tree["unit"] is not None:
        nodes = h5_tree["unit"]["_unit_nodes"]
        last = len(nodes) - 1
        itertext = "".join(
            "".join(n.native.itertext()) + ((n.native.tail or "") if i < last else "") for i, n in enumerate(nodes)
        )
        checks["html5lib_text_rule_equals_itertext"] = itertext == h5_tree["unit"]["text"]
    for tree in (lx_tree, h5_tree):
        if tree["unit"] is not None:
            del tree["unit"]["_unit_nodes"]
    findings, agreements = compare(lx, h5, lx_tree, h5_tree)
    failed_checks = [k for k, v in checks.items() if v is False]
    if failed_checks:
        findings.append({"finding": "CONSISTENCY_CHECK_FAILED", "checks": failed_checks})
    corroborated = not findings and lx_tree["unit"] is not None and h5_tree["unit"] is not None
    return {
        "environment": environment(),
        "request_id": "public-sphinx-parser-corroboration-20261018-01",
        "anchor": anchor,
        "source": {
            "locator": locator,
            "bytes": len(data),
            "sha256": sha256(data),
            "parsed_by_both": "the complete original bytes",
        },
        "decoding_policy": "original bytes to both parsers; each chooses its encoding; compared by codecs.lookup(name).name; disagreement is REVIEW; nothing rewritten",
        "parsers": {
            "lxml": {"options": LXML_OPTIONS, "selected_encoding": lx["encoding"], "diagnostics": lx["diagnostics"]},
            "html5lib": {
                "options": HTML5LIB_OPTIONS,
                "parse_kwargs": HTML5LIB_PARSE_KWARGS,
                "returned_root": h5["root"],
                "selected_encoding": h5["encoding"],
                "encoding_certainty": h5["encoding_certainty"],
                "errors": h5["errors"],
            },
        },
        "name_mapping": {
            "html5lib": f"'{XHTML}<local>' -> '<local>'; other namespaces kept whole",
            "lxml": "tags used as they are",
        },
        "existing_helper": {
            "file": HELPER,
            "sha256": HELPER_SHA256,
            "reasons": found["reasons"],
            "status": found["status"],
            "candidate": None
            if cand is None
            else {
                k: cand[k]
                for k in (
                    "signature_ids",
                    "signatures",
                    "descriptions",
                    "first_line",
                    "last_line",
                    "text_sha256",
                    "text_bytes",
                )
            },
        },
        "trees": {"lxml": lx_tree, "html5lib": h5_tree},
        "checks": checks,
        "comparison": {"findings": findings, "agreements": agreements},
        "triage": {
            "disposition": "STRUCTURE_CORROBORATED" if corroborated else "REVIEW",
            "because": [f["finding"] for f in findings] or ["both repaired interpretations agree"],
            "not_claimed": NOT_CLAIMED,
        },
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 3):
        print("usage: corroborate.py FILE ANCHOR [LOCATOR]")
        return 2
    path = Path(argv[0])
    out = report(path.read_bytes(), argv[1], argv[2] if len(argv) == 3 else path.name)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

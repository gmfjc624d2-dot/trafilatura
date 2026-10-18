"""Successor of the corroborator's report(): an independent text oracle and three separate axes.

Usage: python text_policy.py FILE ANCHOR [LOCATOR]    # prints the JSON report for one source/anchor
Needs lxml and the predecessor's three retained wheels on PYTHONPATH (zipimport; REPORT.md).
It runs research/public-sphinx-parser-corroboration-20261018-01/scripts/corroborate.py from its
pinned bytes, and through it the pinned anchor_unit.py. The parses, mirrored rule, text rule and
comparison are theirs, unchanged. The three changes are pre-registered in
fixtures/expectations.json (targeted_changes):

T1  itertext equality is no longer a consistency check, because the C-accelerated ElementTree
    yields comment payloads. Each unit's rule text is checked against oracle_text(), which shares
    no code with the rule. itertext is only observed.
T2  structural_corroboration is the structural axis only. existing_helper is the pinned helper's
    disposition, unchanged. consumer_gate is NOT_GRANTED in every report.
T3  comparison_scope states what the comparison covers. No comparison rule is relaxed.

Implementation choices are in logs/15_design_addendum.md.
"""

import hashlib
import json
import sys
import types
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
REQUEST_ID = "public-sphinx-text-policy-20261018-01"
PREDECESSOR = "research/public-sphinx-parser-corroboration-20261018-01/scripts/corroborate.py"
PREDECESSOR_SHA256 = "4b5e79140f6d883b3972b8451fef40e093520500d880c3a2cc870010303d4b1d"
WHEELS = {
    "html5lib": (
        "research/public-sphinx-parser-corroboration-20261018-01/wheels/html5lib-1.1-py2.py3-none-any.whl",
        "0d78f8fde1c230e99fe37986a60526d7049ed4bf8a9fadbad5f00e22e58e041d",
    ),
    "six": (
        "research/public-sphinx-parser-corroboration-20261018-01/wheels/six-1.17.0-py2.py3-none-any.whl",
        "4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274",
    ),
    "webencodings": (
        "research/public-sphinx-parser-corroboration-20261018-01/wheels/webencodings-0.5.1-py2.py3-none-any.whl",
        "a0af1213f3c2226497a97e2b3aa01a7e4bee4f403f95be16fc9acd2947514a78",
    ),
}
COMPARISON_SCOPE = (
    "compared between the two trees: encoding (codec name); exact id matches (count) and the rule's structural "
    "reasons; for a selected unit: membership (signature ids, signature and description counts, anchor position, "
    "nested object ids), boundaries (dl and its parent as kind/name/id/class, the kinds and names of all dl "
    "children, the unit's element indexes, neighbouring elements, enclosing object id), ordered topology of the "
    "unit (depth, node kind, mapped name and only the id, class and href attributes of each node), links (href "
    "and text of each a), and the exact concatenated unit text. Not compared: any other attribute (title, lang, "
    "style, data-*, ...), comment and PI payloads, where text sits inside the unit (only the concatenation), "
    "anything outside the unit and its dl, the document head, and the full DOM. Parser diagnostics and errors "
    "are not compared with each other; any of either makes REVIEW."
)
ORACLE_METHOD = (
    "structure-only lxml copy of the unit's native nodes: each element as <e> with its text, each other node "
    "(comment, PI, entity) as an empty comment, each with its tail, inside one container; the last unit "
    "element's tail cleared; libxml2 XPath string() of the container"
)
MUTATIONS = {
    "M1": "comment and PI payloads counted as text",
    "M2": "the tail after a comment or PI omitted",
    "M3": "the last unit element's tail appended",
    "M4": "tails between top-level unit elements omitted",
}
ORACLE_CHECKS = ("lxml_text_rule_equals_oracle", "html5lib_text_rule_equals_oracle")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_predecessor():
    "Execute the pinned corroborate.py bytes as a module; it imports html5lib, six and webencodings and the helper."
    data = (REPO / PREDECESSOR).read_bytes()
    if sha256(data) != PREDECESSOR_SHA256:
        raise RuntimeError(f"{PREDECESSOR} differs from its pinned sha256")
    module = types.ModuleType("corroborate_parser_corroboration")
    module.__file__ = str(REPO / PREDECESSOR)
    try:
        exec(compile(data, module.__file__, "exec"), module.__dict__)  # the bytes just verified, no bytecode written
    except ImportError as e:
        raise SystemExit(f"{e}: put the three retained wheels on PYTHONPATH (REPORT.md, Replay)") from e
    return module


co = load_predecessor()
CONSUMER_GATE = {
    "value": "NOT_GRANTED",
    "prohibition": (
        "No consumer may read structural_corroboration.disposition, existing_helper.status (OK_STRUCTURAL_UNIT, "
        "REVIEW or REVIEW_OVER_BUDGET) or any other field of this report as admission, as fitting any prompt, "
        "context or size limit, as semantic sufficiency, or as permission to send the unit or its source to a "
        "model. This report grants nothing."
    ),
    "not_claimed": co.NOT_CLAIMED,
}


def dependencies():
    "For html5lib, six and webencodings: was the module zipimported from the pinned wheel, and that archive's sha256."
    out = {}
    for name, (rel, pin) in WHEELS.items():
        module = sys.modules[name]
        archive = getattr(module.__loader__, "archive", None)  # set by zipimport
        same = archive is not None and Path(archive).resolve() == (REPO / rel).resolve()
        digest = sha256(Path(archive).read_bytes()) if same else None
        out[name] = {
            "version": getattr(module, "__version__", None) or getattr(module, "VERSION", None),
            "wheel": rel,
            "zipimported_from_wheel": same,
            "wheel_sha256": digest,
            "matches_pin": digest == pin,
        }
    return out


def oracle_text(top):
    """The text rule checked independently, for the unit's top-level native nodes in order.

    Returns (text, None), or (None, reason) when lxml refuses a string. It reads the native trees,
    not the predecessor's node view, and calls nothing of the rule (see ORACLE_METHOD).
    """
    container = etree.Element("u")
    stack = [(n, container) for n in reversed(top)]
    try:
        while stack:
            native, parent = stack.pop()
            if isinstance(native.tag, str):
                copy = etree.SubElement(parent, "e")
                copy.text = native.text
                stack.extend((c, copy) for c in reversed(list(native)))
            else:  # comment, PI or entity: no payload, but keep its place for the tail
                copy = etree.Comment("c")
                parent.append(copy)
            copy.tail = native.tail
    except (ValueError, UnicodeError) as e:
        return None, f"{type(e).__name__}: {e}"
    if len(container):
        container[-1].tail = None
    return str(container.xpath("string()")), None


def mutant_text(unit, mutation):
    "The text rule over the node view with one deliberate error (MUTATIONS); None is the correct rule (control)."

    def text(n):
        if n.kind != "element":
            return (n.text or "") if mutation == "M1" else ""
        dropped = mutation == "M2"
        return (n.text or "") + "".join(
            text(c) + ("" if dropped and c.kind != "element" else (c.tail or "")) for c in n.children
        )

    last = len(unit) - 1
    keep = [(i < last and mutation != "M4") or (i == last and mutation == "M3") for i in range(len(unit))]
    return "".join(text(e) + ((e.tail or "") if keep[i] else "") for i, e in enumerate(unit))


def utf8(s):
    return len((s or "").encode("utf-8"))


def text_identity(s):
    return {"text_utf8_bytes": utf8(s), "text_sha256": sha256(s.encode("utf-8"))}


def ledger(unit, rule, oracle, refused):
    "What the text rule includes and excludes in one unit, and the oracle's text identity."
    nodes = [n for top in unit for n in co.preorder(top)]
    other = [n for n in nodes if n.kind != "element"]
    return {
        "nodes": {k: sum(n.kind == k for n in nodes) for k in ("element", "comment", "pi", "other")},
        "excluded_comment_pi_other_payload_utf8_bytes": sum(utf8(n.text) for n in other),
        "kept_comment_pi_other_tails_utf8_bytes": sum(utf8(n.tail) for n in other),
        "included_inter_unit_tails_utf8_bytes": sum(utf8(e.tail) for e in unit[:-1]),
        "excluded_final_tail_utf8_bytes": utf8(unit[-1].tail),
        "rule": text_identity(rule),
        "oracle": {"method": ORACLE_METHOD, **(text_identity(oracle) if oracle is not None else {}), "refused": refused},
    }


def elementtree_c_accelerated():
    pure = getattr(co.ET, "_Element_Py", None)  # CPython keeps the pure-Python class here when _elementtree loads
    return None if pure is None else co.ET.Element is not pure


def itertext_observation(unit, rule):
    "itertext() with the rule's tail handling, for the record only: never a check or a finding."
    last = len(unit) - 1
    text = "".join("".join(n.native.itertext()) + ((n.native.tail or "") if i < last else "") for i, n in enumerate(unit))
    return {
        "equals_rule": text == rule,
        "equals_rule_with_comment_payload": text == mutant_text(unit, "M1"),
        **text_identity(text),
    }


def analyse(data, anchor, locator):
    "The report for one source/anchor, and each tree's unit nodes (None without a unit) for mutation controls."
    found = co.helper.select_unit(data, anchor, path=locator, origin="public fixture", budget=co.helper.BUDGET_BYTES)
    lx, lx_tree = co.parse_lxml(data, anchor)
    h5, h5_tree = co.parse_html5lib(data, anchor)
    trees = {"lxml": lx_tree, "html5lib": h5_tree}
    units = {s: t["unit"].pop("_unit_nodes") if t["unit"] is not None else None for s, t in trees.items()}
    cand = found["candidate"]
    checks = {  # the predecessor's first four checks, unchanged
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
    }
    itertext = {"elementtree_c_accelerated": elementtree_c_accelerated(), "lxml": None, "html5lib": None}
    text_ledger = {"lxml": None, "html5lib": None}
    unavailable = []
    for side, unit in units.items():
        check = f"{side}_text_rule_equals_oracle"
        checks[check] = None
        if unit is None:
            continue
        rule = trees[side]["unit"]["text"]
        oracle, refused = oracle_text([n.native for n in unit])
        if oracle is None:
            unavailable.append(check)
        else:
            checks[check] = oracle == rule
        text_ledger[side] = ledger(unit, rule, oracle, refused)
        itertext[side] = itertext_observation(unit, rule)
    findings, agreements = co.compare(lx, h5, lx_tree, h5_tree)
    failed = [k for k, v in checks.items() if v is False]
    if failed:
        findings.append({"finding": "CONSISTENCY_CHECK_FAILED", "checks": failed})
    if unavailable:
        findings.append({"finding": "CONSISTENCY_CHECK_UNAVAILABLE", "checks": unavailable})
    corroborated = not findings and None not in units.values() and not found["reasons"]
    because = [f["finding"] for f in findings] + (["EXISTING_HELPER_REASONS_PRESENT"] if found["reasons"] else [])
    rep = {
        "environment": co.environment(),
        "request_id": REQUEST_ID,
        "anchor": anchor,
        "source": {
            "locator": locator,
            "bytes": len(data),
            "sha256": sha256(data),
            "parsed_by_both": "the complete original bytes",
        },
        "decoding_policy": "original bytes to both parsers; each chooses its encoding; compared by codecs.lookup(name).name; disagreement is REVIEW; nothing rewritten",
        "parsers": {
            "lxml": {"options": co.LXML_OPTIONS, "selected_encoding": lx["encoding"], "diagnostics": lx["diagnostics"]},
            "html5lib": {
                "options": co.HTML5LIB_OPTIONS,
                "parse_kwargs": co.HTML5LIB_PARSE_KWARGS,
                "returned_root": h5["root"],
                "selected_encoding": h5["encoding"],
                "encoding_certainty": h5["encoding_certainty"],
                "errors": h5["errors"],
            },
        },
        "name_mapping": {
            "html5lib": f"'{co.XHTML}<local>' -> '<local>'; other namespaces kept whole",
            "lxml": "tags used as they are",
        },
        "existing_helper": {
            "file": co.HELPER,
            "sha256": co.HELPER_SHA256,
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
        "trees": trees,
        "checks": checks,
        "comparison": {"findings": findings, "agreements": agreements},
        "observations": {
            "itertext": {"note": "observation only, never a check or a finding", **itertext},
        },
        "text_ledger": text_ledger,
        "comparison_scope": COMPARISON_SCOPE,
        "structural_corroboration": {
            "disposition": "STRUCTURE_CORROBORATED" if corroborated else "REVIEW",
            "because": because or ["both repaired interpretations agree on comparison_scope"],
            "axis": "agreement of two repaired parses on comparison_scope only; existing_helper.status is "
            "reported unchanged beside it and neither changes the other",
        },
        "consumer_gate": CONSUMER_GATE,
    }
    return rep, units


def report(data, anchor, locator):
    "The complete JSON-ready report for one source/anchor."
    return analyse(data, anchor, locator)[0]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 3):
        print("usage: text_policy.py FILE ANCHOR [LOCATOR]")
        return 2
    path = Path(argv[0])
    print(
        json.dumps(report(path.read_bytes(), argv[1], argv[2] if len(argv) == 3 else path.name), indent=2, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

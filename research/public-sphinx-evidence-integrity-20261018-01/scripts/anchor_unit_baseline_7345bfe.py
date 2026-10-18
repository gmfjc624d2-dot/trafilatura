"""Minimal research helper: the dt/dd unit of one explicit Sphinx object anchor (lxml only).

select_unit(html_bytes, anchor, path=..., origin=...) parses the retained bytes with
lxml.html's recovering HTML parser, keeps the parser's error log, and applies the
pre-registered rule (fixtures/expectations.json): exactly one element with this exact id, a dt
that is a Sphinx object signature (class has 'sig' and 'sig-object'); the unit is its run of dt
siblings plus the following run of dd siblings, each element whole. Anything else is a review
reason; the helper never picks among candidates and never truncates.

Three representations are kept apart: the retained file's bytes (identified by sha256), the
parsed DOM serialization of the unit, and its text_content(). A raw byte span is reported only
when the serialization occurs byte for byte exactly once in the retained file. Parser line
numbers are element start lines, never byte offsets.

A structurally complete unit is not evidence that the passage answers any question.
"""

import hashlib
import unicodedata
from urllib.parse import unquote

import lxml
import lxml.html
from lxml import etree

BUDGET_BYTES = 2048
CONTAINER_OBJTYPES = {"class", "exception"}
CONTEXT_TEMPLATE = [
    "query: anchor_id={anchor}",
    "source: {path} sha256={file_sha256} bytes={file_bytes}",
    "origin: {origin}",
    (
        "unit: {kind} signatures={signatures} descriptions={descriptions} start_lines={first_line}-{last_line}"
        " (parser-reported element start lines; not byte offsets)"
    ),
    "representation: {representation} sha256={payload_sha256} bytes={payload_bytes}",
    "-----BEGIN UNIT-----",
    "{payload}",
    "-----END UNIT-----",
]
REPRESENTATIONS = ("dom_serialization", "text_content")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def versions():
    return {
        "lxml": lxml.__version__,
        "libxml2_runtime": ".".join(map(str, etree.LIBXML_VERSION)),
        "libxml2_compiled": ".".join(map(str, etree.LIBXML_COMPILED_VERSION)),
        "parser": "lxml.html.HTMLParser() defaults (recover=True, comments and PIs kept)",
    }


def is_signature(el):
    return el.tag == "dt" and {"sig", "sig-object"} <= set((el.get("class") or "").split())


def object_of(dl):
    "The Sphinx object signature dt directly inside this dl, or None."
    return next((ch for ch in dl if isinstance(ch.tag, str) and is_signature(ch)), None)


def groups_of(dl):
    "HTML name-value groups of a dl: a run of dt children followed by a run of dd children."
    groups, current = [], None
    for ch in dl:
        if ch.tag == "dt":
            if current is None or current[1]:
                current = ([], [])
                groups.append(current)
            current[0].append(ch)
        elif ch.tag == "dd":
            if current is None:
                current = ([], [])
                groups.append(current)
            current[1].append(ch)
    return groups


def has_stray_content(dl):
    texts = [dl.text] + [ch.tail for ch in dl]
    return any(t and t.strip() for t in texts) or any(ch.tag not in ("dt", "dd") for ch in dl)


def nearest_object_dl(el):
    "The dl of the nearest enclosing object description: an ancestor dd whose parent dl holds a signature."
    for anc in el.iterancestors("dd"):
        parent = anc.getparent()
        if parent is not None and parent.tag == "dl" and object_of(parent) is not None:
            return parent
    return None


def is_container(dl):
    return bool(CONTAINER_OBJTYPES & set((dl.get("class") or "").split()))


def serialize(unit):
    last = len(unit) - 1
    dom = "".join(lxml.html.tostring(e, method="html", encoding="unicode", with_tail=i < last) for i, e in enumerate(unit))
    text = "".join(e.text_content() + ((e.tail or "") if i < last else "") for i, e in enumerate(unit))
    return dom, text


def context(anchor, source, candidate, representation, payload):
    raw = payload.encode("utf-8")
    fields = {
        "anchor": anchor,
        "path": source["path"],
        "file_sha256": source["sha256"],
        "file_bytes": source["bytes"],
        "origin": source["origin"],
        "kind": candidate["kind"],
        "signatures": candidate["signatures"],
        "descriptions": candidate["descriptions"],
        "first_line": candidate["first_line"],
        "last_line": candidate["last_line"],
        "representation": representation,
        "payload_sha256": sha256(raw),
        "payload_bytes": len(raw),
        "payload": payload,
    }
    return "\n".join(line.format(**fields) for line in CONTEXT_TEMPLATE) + "\n"


def select_unit(data, anchor, *, path, origin, budget=BUDGET_BYTES):
    source = {"path": path, "origin": origin, "sha256": sha256(data), "bytes": len(data)}
    parser = lxml.html.HTMLParser()
    doc = lxml.html.document_fromstring(data, parser=parser)
    diagnostics = [
        {"line": e.line, "column": e.column, "level": e.level_name, "type": e.type_name, "message": e.message.strip()}
        for e in parser.error_log
    ]
    exact = doc.xpath("//*[@id=$anchor]", anchor=anchor)  # bound variable: the anchor is data, never XPath
    near = sorted(
        {
            i
            for i in doc.xpath("//@id")
            if i != anchor
            and (unicodedata.normalize("NFC", i) == unicodedata.normalize("NFC", anchor) or i == unquote(anchor))
        }
    )
    result = {
        "anchor": anchor,
        "source": source,
        "parser": {**versions(), "encoding": doc.getroottree().docinfo.encoding, "diagnostics": diagnostics},
        "matches": [{"tag": e.tag, "sourceline": e.sourceline, "class": e.get("class")} for e in exact],
        "near_matches": near,
        "reasons": [],
        "candidate": None,
        "contexts": {},
        "status": {},
        "semantically_reviewed": False,
    }
    reasons = result["reasons"]
    candidate = None
    if not exact:
        reasons.append("ID_NORMALIZATION_MISMATCH" if near else "MISSING_ID")
    elif len(exact) > 1:
        reasons.append("DUPLICATE_ID")
    elif exact[0].tag != "dt":
        reasons.append("NOT_A_SIGNATURE")
    elif not is_signature(exact[0]) or exact[0].getparent() is None or exact[0].getparent().tag != "dl":
        reasons.append("NOT_SPHINX_OBJECT")
    else:
        candidate = build_candidate(data, doc, exact[0], reasons, diagnostics)
    result["candidate"] = candidate
    for representation in REPRESENTATIONS:
        if candidate is None:
            result["status"][representation] = "REVIEW"
            continue
        text = context(anchor, source, candidate, representation, candidate[representation])
        size = len(text.encode("utf-8"))
        fits = size <= budget
        status = "REVIEW" if reasons else ("OK_STRUCTURAL_UNIT" if fits else "REVIEW_OVER_BUDGET")
        result["status"][representation] = status
        result["contexts"][representation] = {
            "budget_bytes": budget,
            "context_bytes": size,
            "fits": fits,
            "context_sha256": sha256(text.encode("utf-8")),
            "context": text if status == "OK_STRUCTURAL_UNIT" else None,
        }
    return result


def build_candidate(data, doc, dt, reasons, diagnostics):
    dl = dt.getparent()
    groups = groups_of(dl)
    dts, dds = next(g for g in groups if dt in g[0])
    if len(groups) > 1:
        reasons.append("MULTIPLE_GROUPS_IN_OBJECT_DL")
    if has_stray_content(dl):
        reasons.append("STRAY_CONTENT_IN_OBJECT_DL")
    if not dds:
        reasons.append("NO_DESCRIPTION")
    elif all(len(dd) == 0 and not (dd.text or "").strip() for dd in dds):
        reasons.append("EMPTY_DESCRIPTION")
    nested = [d for dd in dds for d in dd.iter("dt") if is_signature(d)]
    enclosing = nearest_object_dl(dl)
    if (nested and not is_container(dl)) or (enclosing is not None and not is_container(enclosing)):
        reasons.append("UNEXPECTED_NESTED_OBJECT")
    unit = [ch for ch in dl if ch in dts or ch in dds]
    dom, text = serialize(unit)
    lines = [x.sourceline for e in unit for x in e.iter() if x.sourceline]
    first, last = min(lines), max(lines)
    in_unit = [d for d in diagnostics if first <= d["line"] <= last]
    if in_unit:
        reasons.append("PARSER_RECOVERY_IN_UNIT")
    encoding = doc.getroottree().docinfo.encoding or "utf-8"
    try:
        dom_raw = dom.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        dom_raw = None
    occurrences = data.count(dom_raw) if dom_raw else 0
    span = None
    if occurrences == 1:
        start = data.find(dom_raw)
        span = {"byte_start": start, "byte_end": start + len(dom_raw)}
    return {
        "kind": "sphinx-object " + " ".join((dl.get("class") or "").split()),
        "signatures": len(dts),
        "descriptions": len(dds),
        "signature_ids": [d.get("id") for d in dts],
        "anchor_position": dts.index(dt) + 1,
        "first_line": first,
        "last_line": last,
        "nested_object_ids": [d.get("id") for d in nested],
        "diagnostics_in_unit_lines": in_unit,
        "enclosing_object_id": object_of(enclosing).get("id") if enclosing is not None else None,
        "dom_serialization": dom,
        "dom_sha256": sha256(dom.encode("utf-8")),
        "dom_bytes": len(dom.encode("utf-8")),
        "text_content": text,
        "text_sha256": sha256(text.encode("utf-8")),
        "text_bytes": len(text.encode("utf-8")),
        "raw_occurrences_of_serialization": occurrences,
        "raw_byte_span": span,
    }

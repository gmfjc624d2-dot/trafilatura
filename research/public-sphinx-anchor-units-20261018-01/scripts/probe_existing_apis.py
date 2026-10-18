"""Probe what existing lxml.html and Trafilatura APIs give for explicit anchor selection.

Checks the pre-registered hypotheses H1-H3 (fixtures/expectations.json) and records, per
fixture: parser diagnostics, how many elements carry each case anchor in lxml.html and in
trafilatura.load_html(), and what trafilatura.extract() structured XML output keeps of the
anchors and of the expected unit markers. Usage: python probe_existing_apis.py OUTPUT_JSON
"""

import inspect
import json
import sys
from pathlib import Path

import lxml.html
import trafilatura
from lxml import etree
from trafilatura import utils as trafilatura_utils

ROOT = Path(__file__).resolve().parent.parent


def main():
    out_path = Path(sys.argv[1])
    exp = json.loads((ROOT / "fixtures" / "expectations.json").read_text(encoding="utf-8"))
    by_file = {}
    for case in exp["cases"]:
        by_file.setdefault(case["file"], []).append(case)
    files = {}
    for rel, cases in by_file.items():
        data = (ROOT / rel).read_bytes()
        parser = lxml.html.HTMLParser()
        doc = lxml.html.document_fromstring(data, parser=parser)
        t_doc = trafilatura.load_html(data)
        xml = trafilatura.extract(
            data, output_format="xml", include_formatting=True, include_links=True, include_tables=True, include_comments=False
        )
        xml_root = etree.fromstring(xml.encode("utf-8")) if xml else None
        xml_ids = sorted(set(xml_root.xpath("//@id"))) if xml_root is not None else []
        entry = {
            "diagnostics": [
                {"line": e.line, "column": e.column, "type": e.type_name, "message": e.message.strip()}
                for e in parser.error_log
            ],
            "trafilatura_extract_xml_bytes": len(xml.encode("utf-8")) if xml else None,
            "trafilatura_extract_xml_id_attributes": xml_ids,
            "cases": {},
        }
        for case in cases:
            a = case["anchor"]
            entry["cases"][case["id"]] = {
                "anchor": a,
                "lxml_elements_with_id": len(doc.xpath("//*[@id=$a]", a=a)),
                "load_html_elements_with_id": len(t_doc.xpath("//*[@id=$a]", a=a)) if t_doc is not None else None,
                "anchor_in_extract_xml": bool(xml) and a in xml,
                "must_include_in_extract_xml": {m: bool(xml) and m in xml for m in case.get("must_include", [])},
                "must_exclude_in_extract_xml": {m: bool(xml) and m in xml for m in case.get("must_exclude", [])},
            }
        files[rel] = entry

    dup = (ROOT / "fixtures/f4_duplicates.html").read_bytes()
    dup_doc = lxml.html.document_fromstring(dup)
    chosen = dup_doc.get_element_by_id("pkg.dup")
    all_dup = dup_doc.xpath("//*[@id=$a]", a="pkg.dup")
    f1 = lxml.html.document_fromstring((ROOT / "fixtures/f1_functions.html").read_bytes())
    store_dd = f1.xpath("//*[@id=$a]", a="pkg.store")[0].getnext()
    default = lxml.html.tostring(store_dd, encoding="unicode")
    without = lxml.html.tostring(store_dd, encoding="unicode", with_tail=False)
    any_xml_ids = sorted({i for e in files.values() for i in e["trafilatura_extract_xml_id_attributes"]})
    anchors_kept = sorted({c["anchor"] for e in files.values() for c in e["cases"].values() if c["anchor_in_extract_xml"]})
    report = {
        "trafilatura": {"version": trafilatura.__version__, "file": trafilatura.__file__},
        "trafilatura_load_html_parser": repr(trafilatura_utils.HTML_PARSER),
        "trafilatura_load_html_parser_source": next(
            (line.strip() for line in inspect.getsource(trafilatura_utils).splitlines() if line.startswith("HTML_PARSER")),
            None,
        ),
        "H1": {
            "claim": exp["hypotheses"]["H1"],
            "id_attributes_in_any_extract_xml": any_xml_ids,
            "case_anchors_found_as_text_in_extract_xml": anchors_kept,
            "confirmed": not any_xml_ids,
        },
        "H2": {
            "claim": exp["hypotheses"]["H2"],
            "elements_with_id": len(all_dup),
            "get_element_by_id_returned_line": chosen.sourceline,
            "lines_of_all_matches": [e.sourceline for e in all_dup],
            "confirmed": len(all_dup) > 1 and chosen is not None,
        },
        "H3": {
            "claim": exp["hypotheses"]["H3"],
            "default_tostring_has_stray_text": "MARK-STORE-STRAY" in default,
            "with_tail_false_has_stray_text": "MARK-STORE-STRAY" in without,
            "confirmed": "MARK-STORE-STRAY" in default and "MARK-STORE-STRAY" not in without,
        },
        "files": files,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for h in ("H1", "H2", "H3"):
        print(
            h, "confirmed" if report[h]["confirmed"] else "NOT confirmed", {k: v for k, v in report[h].items() if k != "claim"}
        )
    print("trafilatura.load_html parser:", report["trafilatura_load_html_parser_source"])
    for rel, e in files.items():
        print(f"{rel}: {len(e['diagnostics'])} parser diagnostics; extract() xml {e['trafilatura_extract_xml_bytes']} bytes")
        for d in e["diagnostics"]:
            print(f"    line {d['line']} col {d['column']} {d['type']}: {d['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

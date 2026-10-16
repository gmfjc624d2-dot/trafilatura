"""Reproduce how link targets are resolved, at the convert_tags boundary and through extract().

Expected values are fixed by rule before any output is seen:
- without <base href>: urllib.parse.urljoin(full_document_url, href)
- with <base href>: the HTML Standard "document base URL" (first <base> carrying an href
  attribute in tree order, parsed against the document URL; data:/javascript: results or
  an unparsable value fall back to the document URL; with no document URL only an
  absolute base can be used), then urljoin(document_base_url, href)

Usage: python repro_links.py OUTPUT_DIR
Writes OUTPUT_DIR/link_resolution.json and prints a table. Exit code 1 if any case fails.
"""

import json
import platform
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

import courlan
import lxml
from lxml import etree, html

import trafilatura
from trafilatura import extract
from trafilatura.htmlprocessing import convert_tags
from trafilatura.settings import Extractor

DOC_URL = "https://example.org/docs/v1/api.html?view=full"

# (case id, href, kind) -- "defect" = reported to fail on 2.3.1, "control" = reported to pass
NO_BASE_CASES = [
    ("fragment", "#method", "defect"),
    ("sibling", "peer.html", "defect"),
    ("parent", "../overview.html", "defect"),
    ("query-only", "?view=short", "defect"),
    ("protocol-relative-foreign", "//other.example/guide", "defect"),
    ("dot-sibling-dir", "./sub/page.html", "defect"),
    ("sibling-with-fragment", "peer.html#frag", "defect"),
    ("root-relative", "/reference/index.html", "control"),
    ("protocol-relative-same-host", "//example.org/same", "control"),
    ("absolute-https", "https://abs.example/x?y=1#z", "control"),
    ("absolute-http", "http://insecure.example/y", "control"),
    ("mailto", "mailto:docs@example.org", "control"),
]

# documents served over plain HTTP keep HTTP for protocol-relative links
HTTP_DOC_URL = "http://example.org/docs/v1/api.html"


def spec_base(base_hrefs, doc_url):
    "HTML Standard document base URL, written out independently of the code under test."
    if not base_hrefs:
        return doc_url
    href = base_hrefs[0]
    try:
        candidate = urljoin(doc_url or "", href.strip())
    except ValueError:
        return doc_url
    scheme = candidate.split(":", 1)[0].lower() if ":" in candidate else ""
    if not scheme or scheme in ("data", "javascript"):
        return doc_url
    return candidate


def expected_target(href, doc_url, base_hrefs=()):
    base = spec_base(list(base_hrefs), doc_url)
    if not base:
        return href
    return urljoin(base, href)


def doc_for(href, head_extra=""):
    filler = " ".join(["This sentence keeps the paragraph long enough for every extraction mode."] * 3)
    return (
        f"<html><head><title>API reference</title>{head_extra}</head><body><article>"
        f"<h1>API reference</h1><p>{filler}</p>"
        f'<p>See <a href="{html_escape(href)}">the linked section</a> before calling the method. {filler}</p>'
        f"<p>{filler}</p></article></body></html>"
    )


def html_escape(value):
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def via_convert_tags(document, url):
    tree = html.fromstring(document)
    converted = convert_tags(tree, Extractor(links=True), url)
    return [ref.get("target") for ref in converted.iter("ref")]


def via_extract(document, url, **kwargs):
    result = extract(document, url=url, include_links=True, output_format="xml", **kwargs)
    if result is None:
        return None
    return [ref.get("target") for ref in etree.fromstring(result.encode()).iter("ref")]


# <base href> cases: (case id, list of <base> tags in the head, href, document URL)
BASE_CASES = [
    ("base-absolute-other-host", ['<base href="https://cdn.example.net/ref/">'], "peer.html", DOC_URL),
    ("base-host-root", ['<base href="https://example.org/">'], "DE/page.html", DOC_URL),
    ("base-relative-path", ['<base href="/docs/v2/">'], "peer.html", DOC_URL),
    ("base-first-wins", ['<base href="/first/">', '<base href="/second/">'], "peer.html", DOC_URL),
    ("base-target-only-skipped", ['<base target="_blank">', '<base href="/docs/v3/">'], "peer.html", DOC_URL),
    ("base-javascript-ignored", ['<base href="javascript:void(0)">'], "peer.html", DOC_URL),
    ("base-empty-href", ['<base href="">'], "peer.html", DOC_URL),
    ("base-fragment-link", ['<base href="https://cdn.example.net/ref/">'], "#method", DOC_URL),
    ("base-root-relative-link", ['<base href="https://cdn.example.net/ref/">'], "/top.html", DOC_URL),
    ("base-no-doc-url-absolute", ['<base href="https://cdn.example.net/ref/">'], "peer.html", None),
    ("base-no-doc-url-relative", ['<base href="/docs/v2/">'], "peer.html", None),
]


def environment():
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False, cwd=Path(trafilatura.__file__).parent
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "trafilatura"],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(trafilatura.__file__).parent.parent,
        ).stdout.strip()
    except OSError:
        head, dirty = "", ""
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "trafilatura": trafilatura.__version__,
        "trafilatura_file": trafilatura.__file__,
        "git_head": head,
        "source_tree_dirty": bool(dirty),
        "lxml": lxml.__version__,
        "libxml2": ".".join(map(str, etree.LIBXML_VERSION)),
        "courlan": getattr(courlan, "__version__", "unknown"),
    }


def run_case(case_id, kind, href, doc_url, base_tags=(), base_hrefs=()):
    document = doc_for(href, "".join(base_tags))
    expected = expected_target(href, doc_url, base_hrefs)
    observed = {
        "convert_tags": via_convert_tags(document, doc_url),
        "extract_default": via_extract(document, doc_url),
        "extract_fast": via_extract(document, doc_url, fast=True),
        "extract_favor_recall": via_extract(document, doc_url, favor_recall=True),
        "extract_favor_precision": via_extract(document, doc_url, favor_precision=True),
    }
    verdicts = {}
    for path, targets in observed.items():
        if targets is None:
            verdicts[path] = "NO-OUTPUT"
        elif expected in targets:
            verdicts[path] = "PASS"
        else:
            verdicts[path] = "FAIL"
    return {
        "case": case_id,
        "kind": kind,
        "href": href,
        "document_url": doc_url,
        "base_elements": list(base_tags),
        "expected": expected,
        "observed": observed,
        "verdicts": verdicts,
    }


def main():
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [run_case(cid, kind, href, DOC_URL) for cid, href, kind in NO_BASE_CASES]
    results.append(run_case("protocol-relative-http-doc", "control", "//other.example/guide", HTTP_DOC_URL))
    for cid, tags, href, doc_url in BASE_CASES:
        hrefs = [t.split('href="', 1)[1].split('"', 1)[0] for t in tags if 'href="' in t]
        results.append(run_case(cid, "base", href, doc_url, tags, hrefs))

    failures = [r for r in results if any(v != "PASS" for v in r["verdicts"].values())]
    report = {"environment": environment(), "document_url": DOC_URL, "results": results, "failing_cases": len(failures)}
    (out_dir / "link_resolution.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(report["environment"], indent=2))
    print(f"\n{'case':32} {'kind':8} {'expected':58} convert_tags | extract default/fast/recall/precision")
    for r in results:
        obs = r["observed"]["convert_tags"]
        got = obs[0] if obs else None
        v = r["verdicts"]
        line = (
            f"{r['case']:32} {r['kind']:8} {r['expected']:58} {v['convert_tags']:4} | "
            f"{v['extract_default']}/{v['extract_fast']}/{v['extract_favor_recall']}/{v['extract_favor_precision']}"
        )
        print(line)
        if v["convert_tags"] != "PASS":
            print(f"{'':41}convert_tags got: {got}")
        for path in ("extract_default", "extract_fast", "extract_favor_recall", "extract_favor_precision"):
            if v[path] not in ("PASS",) and r["observed"][path] != r["observed"]["convert_tags"]:
                print(f"{'':41}{path} got: {r['observed'][path]}")
    print(f"\nfailing cases: {len(failures)} of {len(results)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

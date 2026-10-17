"""Probe: does a <base> element survive tree_cleaning()? (design question for the fix)

If it can, convert_tags() must not re-read <base> on the cleaned tree while the pipeline also
passes the base URL already resolved from the raw tree: a path-relative base ("sub/") would be
applied twice. Usage: python probe_base_survival.py
"""

from copy import copy
from urllib.parse import urljoin

from trafilatura import load_html
from trafilatura.htmlprocessing import tree_cleaning
from trafilatura.settings import Extractor

DOCS = {
    "base in head": '<html><head><base href="sub/"></head><body><p>x</p></body></html>',
    "base in body": '<html><body><base href="sub/"><p>x</p></body></html>',
    "base in div": '<html><body><div><base href="sub/"><p>x</p></div></body></html>',
}

for name, doc in DOCS.items():
    tree = load_html(doc)
    raw = [b.getparent().tag for b in tree.iter("base")]
    cleaned = tree_cleaning(copy(tree), Extractor(links=True))
    left = [b.get("href") for b in cleaned.iter("base")]
    print(f"{name:13} raw parent: {raw} | after tree_cleaning: {left}")

once = urljoin("https://example.org/docs/", "sub/")
print(f"base applied once:  {once}")
print(f"base applied twice: {urljoin(once, 'sub/')}")

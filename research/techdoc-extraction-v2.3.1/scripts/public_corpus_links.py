"""Check link targets on the public pages of the upstream evaluation corpus (tests/cache).

For every corpus page with a URL in tests/evaldata.json and at least one relative href:
- verify the sha256 of the committed bytes and record provenance,
- run extract(..., url=<evaldata URL>, include_links=True, output_format="xml"),
- compare each output <ref target> with the reference set computed independently from the
  raw page: urljoin(document_base_url, href) for every <a href>, where document_base_url
  follows the HTML Standard (first <base href>, parsed against the page URL; data:/javascript:
  or unparsable values fall back to the page URL).

A target outside the reference set is a mismatch. Nothing is skipped after seeing results.

Usage: python public_corpus_links.py REPO_ROOT OUTPUT_DIR [--variant as-is|naive-ablation]
  as-is           the installed trafilatura source, unmodified
  naive-ablation  ONLY meaningful on the 2.3.1 source: simulates the candidate fix
                  "urljoin(full document URL, href), <base> ignored" by replacing the two
                  helpers convert_tags uses, to measure that design before choosing it
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

import trafilatura
from lxml import etree
from trafilatura import extract, load_html

ABSOLUTE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def spec_base(tree, doc_url):
    for base in tree.iter("base"):
        href = base.get("href")
        if href is None:
            continue
        try:
            candidate = urljoin(doc_url or "", href.strip())
        except ValueError:
            return doc_url
        scheme = candidate.split(":", 1)[0].lower() if ":" in candidate else ""
        if not scheme or scheme in ("data", "javascript"):
            return doc_url
        return candidate
    return doc_url


def reference_targets(tree, doc_url):
    base = spec_base(tree, doc_url)
    refs = set()
    for a in tree.iter("a"):
        href = a.get("href")
        if not href:
            continue
        try:
            refs.add(urljoin(base, href) if base else href)
        except ValueError:
            refs.add(href)
    return base, refs


def git(repo, *args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False, cwd=repo).stdout.strip()


def apply_naive_ablation():
    from trafilatura import htmlprocessing

    if not hasattr(htmlprocessing, "safe_base_url"):
        sys.exit("naive-ablation needs the 2.3.1 htmlprocessing module (safe_base_url import)")

    def join(base, url):
        try:
            return urljoin(base, url)
        except ValueError:
            return ""

    htmlprocessing.safe_base_url = lambda url: url
    htmlprocessing.safe_relative_url = join


def targets(result):
    if result is None:
        return None
    return [ref.get("target") for ref in etree.fromstring(result.encode()).iter("ref") if ref.get("target")]


def main():
    repo, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    variant = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "as-is"
    if variant == "naive-ablation":
        apply_naive_ablation()
    elif variant != "as-is":
        sys.exit(f"unknown variant {variant}")
    out_dir.mkdir(parents=True, exist_ok=True)
    evaldata = json.loads((repo / "tests/evaldata.json").read_text(encoding="utf-8"))
    by_file = {v["file"]: k for k, v in evaldata.items()}
    pages = []
    totals = {"pages": 0, "with_base": 0}
    for mode in ("default", "fast"):
        totals[mode] = {"targets": 0, "mismatches": 0, "pages_with_mismatch": 0}
    for path in sorted((repo / "tests/cache").glob("*.html")):
        url = by_file.get(path.name)
        if not url or not url.startswith("http"):
            continue
        raw = path.read_bytes()
        tree = load_html(raw)
        if tree is None:
            continue
        hrefs = [a.get("href") for a in tree.iter("a") if a.get("href")]
        if not any(not ABSOLUTE.match(h) for h in hrefs):
            continue
        base, refs = reference_targets(tree, url)
        rel = path.relative_to(repo).as_posix()
        added = git(repo, "log", "--diff-filter=A", "--follow", "--format=%H %aI", "--", rel).splitlines()
        page = {
            "file": rel,
            "url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "git_blob": git(repo, "rev-parse", f"HEAD:{rel}"),
            "added_in_commit": added[-1] if added else "",
            "base_hrefs": [b.get("href") for b in tree.iter("base") if b.get("href") is not None],
            "document_base_url": base,
            "relative_hrefs": sum(1 for h in hrefs if not ABSOLUTE.match(h)),
        }
        totals["pages"] += 1
        totals["with_base"] += bool(page["base_hrefs"])
        for mode, kwargs in (("default", {}), ("fast", {"fast": True})):
            got = targets(extract(raw, url=url, include_links=True, output_format="xml", **kwargs))
            mismatches = [t for t in (got or []) if t not in refs]
            page[mode] = {"targets": len(got or []), "mismatches": len(mismatches), "examples": mismatches[:5]}
            totals[mode]["targets"] += len(got or [])
            totals[mode]["mismatches"] += len(mismatches)
            totals[mode]["pages_with_mismatch"] += bool(mismatches)
        pages.append(page)

    # the imported source may live in another checkout than the corpus (e.g. a baseline worktree)
    source = Path(trafilatura.__file__).resolve().parent.parent
    report = {
        "variant": variant,
        "trafilatura": trafilatura.__version__,
        "trafilatura_file": trafilatura.__file__,
        "git_head": git(source, "rev-parse", "HEAD"),
        "source_tree_dirty": bool(git(source, "status", "--porcelain", "--", "trafilatura")),
        "corpus_repo_head": git(repo, "rev-parse", "HEAD"),
        "totals": totals,
        "pages": pages,
    }
    (out_dir / f"public_corpus_links_{variant}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "pages"}, indent=2))
    for page in pages:
        if page["default"]["mismatches"] or page["fast"]["mismatches"]:
            print(
                f"{page['file']}: base={page['base_hrefs']} default {page['default']['mismatches']}/{page['default']['targets']}"
                f" fast {page['fast']['mismatches']}/{page['fast']['targets']} e.g. {page['default']['examples'][:2]}"
            )
    return 1 if totals["default"]["mismatches"] or totals["fast"]["mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())

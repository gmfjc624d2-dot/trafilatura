"""POST-HOC analyses, written after the results were seen. They never change a verdict.

  python posthoc_analysis.py matrix RESULTS_DIR FIXTURE_DIR
      classifies every remaining FAIL of matrix_outputs.jsonl:
      - statements failing only because txt/markdown interleave "[text](url)" link markup
        (R2 re-checked on the output with link markup reduced to its text)
      - code/emphasis marking failing only with output_format="markdown" and an explicit
        include_formatting=False (settings.py: "an explicit formatting=False is honored")
      - text dropped by main-content selection, with a check that trafilatura.html2txt()
        and trafilatura.baseline() still contain it (how a caller can detect the loss)
  python posthoc_analysis.py corpus REPO_ROOT
      recomputes the public-corpus comparison for the imported trafilatura and labels every
      strict mismatch: "equivalent-form" (same URL once scheme/host case, an empty path and
      an empty trailing ? or # are normalised) or "different-resource"
Exit code 0; the printed report and its JSON are the result.
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import trafilatura
from lxml import etree
from trafilatura import baseline, extract, html2txt, load_html

ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
MD_LINK = re.compile(r"\[([^\]]*)\]\((?:<[^>]*>|[^)\s]*)\)")


def tokens(text):
    return re.findall(r"\w+", text)


def contains(seq, sub):
    return bool(sub) and any(seq[i : i + len(sub)] == sub for i in range(len(seq) - len(sub) + 1))


def link_target(output, fmt, anchor):
    "The target the output gives to the link with this anchor text, None if the link is absent."
    if not output:
        return None
    if fmt == "xml":
        for ref in etree.fromstring(output.encode("utf-8")).iter("ref"):
            if "".join(ref.itertext()).strip() == anchor:
                return ref.get("target")
        return None
    match = re.search(r"\[" + re.escape(anchor) + r"\]\(<?([^)>\s]*)>?\)", output)
    return match.group(1) if match else None


def matrix(results_dir, fixture_dir):
    expectations = json.loads((fixture_dir / "expectations.json").read_text(encoding="utf-8"))
    reqs = {(n, r["id"]): r for n, f in expectations["fixtures"].items() for r in f["requirements"]}
    classes = {}
    examples = {}
    for line in (results_dir / "matrix_outputs.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        for rid, v in rec["verdicts"].items():
            if v["verdict"] != "FAIL":
                continue
            req = reqs[(rec["fixture"], rid)]
            out = rec["output"] or ""
            fmt, formatting = rec["output_format"], rec["include_formatting"]
            delinked = ESCAPE.sub(r"\1", MD_LINK.sub(r"\1", out))
            if req["type"] == "statement" and fmt != "xml" and contains(tokens(delinked), tokens(req["text"])):
                cls = "link-markup-interleaving"
            elif req["type"] in ("code_marked", "emphasis_marked") and fmt == "markdown" and formatting is False:
                cls = "explicit-include_formatting=False-on-markdown"
            elif req["type"] == "link" and (got := link_target(out, fmt, req["anchor"])) is not None:
                cls = f"wrong-link-target (got {got})"
            else:
                data = (fixture_dir / rec["fixture"]).read_bytes()
                probe = req.get("text") or req.get("block") or req.get("anchor") or ""
                probe_tokens = tokens(probe)
                in_html2txt = contains(tokens(html2txt(data)), probe_tokens)
                in_baseline = contains(tokens(baseline(data)[1]), probe_tokens)
                cls = f"dropped-by-content-selection (html2txt has it: {in_html2txt}, baseline has it: {in_baseline})"
            key = f"{rec['fixture']}::{rid}"
            classes.setdefault(key, {}).setdefault(cls, 0)
            classes[key][cls] += 1
            examples.setdefault(
                key, f"{rec['mode']} L{int(rec['include_links'])} T{int(rec['include_tables'])} F{int(formatting)} {fmt}"
            )
    report = {"posthoc": True, "results_dir": str(results_dir), "classes": classes, "first_failing_config": examples}
    out_file = results_dir / "posthoc_matrix_classification.json"
    out_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    total = 0
    for key, cls in classes.items():
        for name, count in cls.items():
            total += count
            print(f"{key:58} {count:3}  {name}   e.g. {examples[key]}")
    print(f"classified FAIL verdicts: {total}")


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
        return doc_url if not scheme or scheme in ("data", "javascript") else candidate
    return doc_url


def normalise(url):
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    path = parts.path or ("/" if parts.netloc else "")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, parts.fragment))


def corpus(repo):
    evaldata = json.loads((repo / "tests/evaldata.json").read_text(encoding="utf-8"))
    by_file = {v["file"]: k for k, v in evaldata.items()}
    counts = {"default": {}, "fast": {}}
    listed = []
    for path in sorted((repo / "tests/cache").glob("*.html")):
        url = by_file.get(path.name)
        if not url or not url.startswith("http"):
            continue
        raw = path.read_bytes()
        tree = load_html(raw)
        if tree is None:
            continue
        base = spec_base(tree, url)
        refs = set()
        for a in tree.iter("a"):
            href = a.get("href")
            if href:
                try:
                    refs.add(urljoin(base, href))
                except ValueError:
                    refs.add(href)
        normalised = {normalise(r) for r in refs}
        for mode, kwargs in (("default", {}), ("fast", {"fast": True})):
            result = extract(raw, url=url, include_links=True, output_format="xml", **kwargs)
            if result is None:
                continue
            for ref in etree.fromstring(result.encode()).iter("ref"):
                target = ref.get("target")
                if not target or target in refs:
                    continue
                cls = "equivalent-form" if normalise(target) in normalised else "different-resource"
                counts[mode][cls] = counts[mode].get(cls, 0) + 1
                listed.append({"file": path.name, "mode": mode, "target": target, "class": cls})
    head = Path(trafilatura.__file__).resolve().parent.parent
    report = {
        "posthoc": True,
        "trafilatura_file": trafilatura.__file__,
        "source": str(head),
        "counts": counts,
        "mismatches": listed,
    }
    print(json.dumps({k: v for k, v in report.items() if k != "mismatches"}, indent=2))
    for item in listed:
        if item["class"] == "different-resource":
            print(f"different-resource {item['mode']:7} {item['file']}: {item['target']}")
    return report


def main():
    if sys.argv[1] == "matrix":
        matrix(Path(sys.argv[2]), Path(sys.argv[3]))
    elif sys.argv[1] == "corpus":
        report = corpus(Path(sys.argv[2]))
        if len(sys.argv) > 3:
            Path(sys.argv[3]).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

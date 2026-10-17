"""Provenance of the upstream public pages reused from tests/cache (no network access).

Same page selection as public_corpus_links.py: corpus pages with an http(s) URL in
tests/evaldata.json and at least one relative href. Needs a full (non-shallow) clone for the
first-add commit, which is the closest available bound on the retrieval date: upstream does
not record when a page was fetched.

Usage: python public_provenance.py REPO_ROOT OUTPUT_JSON [BASELINE_REF]
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from lxml import html

ABSOLUTE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def git(repo, *args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False, cwd=repo).stdout.strip()


def main():
    repo, out = Path(sys.argv[1]), Path(sys.argv[2])
    baseline = sys.argv[3] if len(sys.argv) > 3 else "e2f85c965662c7df26b73290ef175b2c2a5fdca6"
    if git(repo, "rev-parse", "--is-shallow-repository") != "false":
        sys.exit("shallow clone: run `git fetch --unshallow` first, first-add commits would be wrong")
    evaldata = json.loads((repo / "tests/evaldata.json").read_text(encoding="utf-8"))
    by_file = {v["file"]: (k, v) for k, v in evaldata.items()}
    pages = []
    for path in sorted((repo / "tests/cache").glob("*.html")):
        url, entry = by_file.get(path.name, (None, {}))
        if not url or not url.startswith("http"):
            continue
        raw = path.read_bytes()
        try:
            tree = html.fromstring(raw)
        except Exception:
            continue
        if not any(not ABSOLUTE.match(a.get("href")) for a in tree.iter("a") if a.get("href")):
            continue
        rel = path.relative_to(repo).as_posix()
        added = git(repo, "log", "--diff-filter=A", "--follow", "--format=%H %aI", "--", rel).splitlines()
        pages.append(
            {
                "file": rel,
                "url": url,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "git_blob_at_head": git(repo, "rev-parse", f"HEAD:{rel}"),
                "unchanged_since_baseline": git(repo, "rev-parse", f"{baseline}:{rel}")
                == git(repo, "rev-parse", f"HEAD:{rel}"),
                "first_added_upstream": added[-1] if added else "",
                "last_changed_upstream": git(repo, "log", "-1", "--format=%H %aI", baseline, "--", rel),
                "page_declared_license_in_evaldata": entry.get("license", ""),
            }
        )
    report = {
        "source": "https://github.com/adbar/trafilatura, tests/cache/ and tests/evaldata.json at v2.3.1",
        "baseline_commit": baseline,
        "retrieval_date": "not recorded upstream; first_added_upstream is the commit that added the file "
        "(an upper bound on the retrieval date)",
        "license": "third-party web pages archived in the upstream test corpus; the project's Apache-2.0 "
        "license covers the code, not these pages, and upstream declares no license for them. "
        "page_declared_license_in_evaldata is the page's own license metadata where upstream annotated "
        "one. Used read-only, bytes unchanged; nothing was downloaded.",
        "evaldata_json": {
            "sha256": hashlib.sha256((repo / "tests/evaldata.json").read_bytes()).hexdigest(),
            "git_blob_at_head": git(repo, "rev-parse", "HEAD:tests/evaldata.json"),
        },
        "pages": pages,
    }
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    changed = [p["file"] for p in pages if not p["unchanged_since_baseline"]]
    print(f"pages: {len(pages)}, changed since baseline: {changed or 'none'}")
    for p in pages:
        if p["file"].rsplit("/", 1)[-1].startswith(("simplyscience", "en.wikipedia", "bmjv", "docs.docker", "netbits")):
            print(f"{p['file']} {p['url']} sha256={p['sha256']} first added {p['first_added_upstream']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

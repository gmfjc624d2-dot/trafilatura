"""Write the synthetic Sphinx-like HTML fixtures and the byte regions of their expected units.

  python build_fixtures.py build   # writes fixtures/*.html and fixtures/regions.json
  python build_fixtures.py check   # rebuilds in memory, compares bytes (exit 1 if different)

The pages are assembled from strings carrying sentinels ⟦name⟧ ... ⟦/name⟧.
The sentinels are removed and the UTF-8 byte offsets [start, end) of each named region are
recorded. A region marks the raw bytes of the dt...dd run the author intends as the unit; it is
an expectation written before any selection code exists, not a parser result.
Python 3.12 standard library only.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
SENTINEL = re.compile("⟦(/?)([^⟧]+)⟧")


def sig(anchor, name, params, prename="pkg.", kind=""):
    "A Sphinx >= 4 style signature dt; anchor None gives a dt without id (later signatures)."
    ident = f' id="{anchor}"' if anchor else ""
    link = f'<a class="headerlink" href="#{anchor}" title="Link to this definition">¶</a>' if anchor else ""
    prefix = f'<em class="property"><span class="pre">{kind}</span><span class="w"> </span></em>' if kind else ""
    args = ", ".join(f'<em class="sig-param"><span class="n"><span class="pre">{p}</span></span></em>' for p in params)
    return (
        f'<dt class="sig sig-object py"{ident}>\n{prefix}<span class="sig-prename descclassname"><span class="pre">{prename}</span>'
        f'</span><span class="sig-name descname"><span class="pre">{name}</span></span><span class="sig-paren">(</span>{args}'
        f'<span class="sig-paren">)</span>{link}</dt>\n'
    )


def page(title, body, head_extra=""):
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{title}</title>\n{head_extra}</head>\n<body>\n"
        '<div class="body" role="main">\n<section id="module-pkg">\n<h1>pkg</h1>\n'
        "<p>Module introduction. MARK-PAGE-INTRO</p>\n"
        f"{body}"
        "<p>Closing paragraph of the page. MARK-PAGE-TAIL</p>\n</section>\n</div>\n</body>\n</html>\n"
    )


FETCH_DD = """<dd><p>Fetch <em>url</em> and return the body. MARK-FETCH-DESC</p>
<div class="admonition note">
<p class="admonition-title">Note</p>
<p>The connection is reused between calls. MARK-FETCH-NOTE</p>
</div>
<div class="admonition warning">
<p class="admonition-title">Warning</p>
<p>Never pass untrusted URLs without validation. MARK-FETCH-WARNING</p>
</div>
<dl class="field-list simple">
<dt class="field-odd">Parameters<span class="colon">:</span></dt>
<dd class="field-odd"><ul class="simple">
<li><p><strong>url</strong> – the address to fetch. MARK-FETCH-PARAM</p></li>
<li><p><strong>timeout</strong> – seconds, must be positive.</p></li>
</ul>
</dd>
</dl>
<div class="highlight-python notranslate"><div class="highlight"><pre><span></span>def fetch(url, timeout=30):
    if timeout &lt;= 0:
        raise ValueError("timeout")  # MARK-FETCH-CODE
    return get(url) &amp; checks
</pre></div>
</div>
<div class="versionchanged">
<p><span class="versionmodified changed">Changed in version 2.0: </span>MARK-FETCH-VERSION added <em>timeout</em>.</p>
</div>
</dd>"""


def f1_functions():
    body = (
        '<span id="fetch-label"></span><dl class="py function">\n'
        "⟦unit:pkg.fetch⟧" + sig("pkg.fetch", "fetch", ["url", "timeout=30"]) + FETCH_DD + "⟦/unit:pkg.fetch⟧" + "\n</dl>\n"
        '<dl class="py function">\n'
        + sig("pkg.store", "store", ["key", "value"])
        + "<dd><p>Store a value. MARK-STORE-DESC</p>\n</dd>MARK-STORE-STRAY text inside the object dl\n</dl>\n"
        '<dl class="glossary simple">\n<dt id="term-proxy">proxy</dt><dd><p>An intermediary server. MARK-GLOSSARY-PROXY</p>\n'
        "</dd>\n</dl>\n"
    )
    return page("pkg functions", body)


def f2_signatures():
    body = (
        '<dl class="py function">\n'
        "⟦unit:pkg.span⟧"
        + sig("pkg.span", "span", ["stop"])
        + sig(None, "span", ["start", "stop", "step=1"])
        + "<dd><p>Return a span; both signatures share this description. MARK-SPAN-SHARED</p>\n</dd>"
        + "⟦/unit:pkg.span⟧"
        + "\n</dl>\n"
        '<dl class="py function">\n'
        + "⟦unit:pkg.get⟧"
        + sig("pkg.get", "get", ["key"])
        + sig("pkg.fetch_one", "fetch_one", ["key"])
        + "<dd><p>Return one value for <em>key</em>. MARK-GET-SHARED</p>\n</dd>"
        + "⟦/unit:pkg.get⟧"
        + "\n</dl>\n"
        '<dl class="py function">\n' + sig("pkg.empty_doc", "empty_doc", []) + "<dd></dd>\n</dl>\n"
        '<dl class="py function">\n' + sig("pkg.no_dd", "no_dd", []) + "</dl>\n"
        '<dl class="py function">\n'
        + sig("pkg.twin_a", "twin_a", [])
        + "<dd><p>MARK-TWIN-A</p>\n</dd>\n"
        + sig("pkg.twin_b", "twin_b", [])
        + "<dd><p>MARK-TWIN-B</p>\n</dd>\n</dl>\n"
    )
    return page("pkg signatures", body)


def f3_classes():
    big = "\n".join(
        f"<p>Paragraph {n} of the large class description, long enough to matter for the budget. MARK-BIG-{n:02d}</p>"
        for n in range(1, 23)
    )
    body = (
        '<dl class="py class">\n'
        "⟦unit:pkg.Client⟧"
        + sig("pkg.Client", "Client", ["base_url"], kind="class")
        + "<dd><p>HTTP client for one base URL. MARK-CLIENT-DESC</p>\n"
        '<dl class="py method">\n'
        + "⟦unit:pkg.Client.open⟧"
        + sig("pkg.Client.open", "open", ["path"], prename="")
        + '<dd><p>Open <em>path</em> relative to the base URL. MARK-OPEN-DESC</p>\n<div class="admonition note">\n'
        '<p class="admonition-title">Note</p>\n<p>Not thread-safe. MARK-OPEN-NOTE</p>\n</div>\n</dd>'
        + "⟦/unit:pkg.Client.open⟧"
        + "\n</dl>\n"
        '<dl class="py attribute">\n'
        + sig("pkg.Client.timeout", "timeout", [], prename="")
        + "<dd><p>Timeout in seconds. MARK-TIMEOUT-DESC</p>\n</dd>\n</dl>\n"
        "<p>Closing remarks for the class. MARK-CLIENT-TAIL</p>\n</dd>" + "⟦/unit:pkg.Client⟧" + "\n</dl>\n"
        '<dl class="py class">\n' + sig("pkg.BigClient", "BigClient", [], kind="class") + f"<dd>{big}\n</dd>\n</dl>\n"
        '<dl class="py function">\n'
        + sig("pkg.helper", "helper", [])
        + '<dd><p>Helper. MARK-HELPER-DESC</p>\n<dl class="py function">\n'
        + sig("pkg.helper.inner", "inner", [], prename="pkg.helper.")
        + "<dd><p>Inner function. MARK-INNER-DESC</p>\n</dd>\n</dl>\n</dd>\n</dl>\n"
    )
    return page("pkg classes", body)


def f4_duplicates():
    body = (
        '<dl class="py function">\n'
        + sig("pkg.dup", "dup", ["a"])
        + "<dd><p>First description. MARK-DUP-A</p>\n</dd>\n</dl>\n"
        '<dl class="py function">\n'
        + sig("pkg.dup", "dup", ["a", "b"])
        + "<dd><p>Second description. MARK-DUP-B</p>\n</dd>\n</dl>\n"
    )
    return page("pkg duplicates", body)


def f5_unicode():
    body = (
        '<dl class="py function">\n'
        "⟦unit:pkg.naïve⟧"
        + sig("pkg.naïve", "naïve", ["texte"])
        + "<dd><p>Unicode description MARK-UNICODE-DESC: 接続は再試行されません。 🔒 café (NFD) and&nbsp;a no-break space.</p>\n</dd>"
        + "⟦/unit:pkg.naïve⟧"
        + "\n</dl>\n"
    )
    return page("pkg unicode", body)


def f6_malformed():
    "Unclosed dt/dd/p, misnested inline tags, raw & and <, stray end tags, invalid UTF-8 bytes."
    body = (
        '<dl class="py function">\n'
        '<dt class="sig sig-object py" id="pkg.broken">broken()\n'
        "<dd><p>Starts here MARK-BROKEN-DESC & continues < unescaped.\n"
        '<div class="admonition note"><p class="admonition-title">Note</p><p>Misnested <b><i>MARK-BROKEN-NOTE</b></i></div>\n'
        '<dl class="py function">\n'
        '<dt class="sig sig-object py" id="pkg.after">after()\n'
        "<dd><p>MARK-AFTER-DESC\n"
        "</dl></dl></span>\n"
        '<dl class="py function">\n'
        + sig("pkg.badbytes", "badbytes", [])
        + "<dd><p>Invalid UTF-8 follows: \udcff\udcfe MARK-BADBYTES-DESC</p>\n</dd>\n</dl>\n"
    )
    return page("pkg malformed", body)


FIXTURE_BUILDERS = {
    "f1_functions.html": f1_functions,
    "f2_signatures.html": f2_signatures,
    "f3_classes.html": f3_classes,
    "f4_duplicates.html": f4_duplicates,
    "f5_unicode.html": f5_unicode,
    "f6_malformed.html": f6_malformed,
}


def render(text):
    "Remove sentinels; return bytes and {region: [start, end)} in UTF-8 byte offsets."
    out, regions, opened, pos = bytearray(), {}, {}, 0
    for m in SENTINEL.finditer(text):
        out += text[pos : m.start()].encode("utf-8", "surrogateescape")
        closing, name = m.groups()
        if closing:
            regions[name] = [opened.pop(name), len(out)]
        else:
            opened[name] = len(out)
        pos = m.end()
    out += text[pos:].encode("utf-8", "surrogateescape")
    assert not opened, opened
    return bytes(out), regions


def build():
    files, regions = {}, {}
    for name, builder in FIXTURE_BUILDERS.items():
        data, found = render(builder())
        files[FIXTURES / name] = data
        for region, span in found.items():
            regions[region] = {
                "file": f"fixtures/{name}",
                "byte_start": span[0],
                "byte_end": span[1],
                "sha256": hashlib.sha256(data[span[0] : span[1]]).hexdigest(),
            }
    meta = {
        "regions_note": "raw byte ranges [byte_start, byte_end) of the dt...dd run each fixture author intends as the unit;"
        " recorded from sentinels before any selection code existed",
        "files": {f"fixtures/{p.name}": {"bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()} for p, d in files.items()},
        "regions": regions,
    }
    files[FIXTURES / "regions.json"] = (json.dumps(meta, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return files


def main():
    files = build()
    if sys.argv[1] == "build":
        FIXTURES.mkdir(exist_ok=True)
        for path, data in files.items():
            path.write_bytes(data)
            print(f"wrote {path.relative_to(ROOT).as_posix()} {len(data)} bytes sha256={hashlib.sha256(data).hexdigest()}")
        return 0
    differ = [p.relative_to(ROOT).as_posix() for p, d in files.items() if not p.exists() or p.read_bytes() != d]
    print("check: " + ("identical" if not differ else f"DIFFERS: {differ}"))
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())

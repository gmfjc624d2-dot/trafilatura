"""Build the retained UTF-8 plain-text fixtures and their passage index (Python 3.12 stdlib).

  python build_fixtures.py extract CPYTHON_CHECKOUT   # once, needs the pinned CPython 3.12 file
  python build_fixtures.py build                      # offline: render + index from retained files
  python build_fixtures.py check                      # offline: rebuild in memory, compare bytes

`extract` copies the exact source lines of each excerpt (and CPython's LICENSE) out of a
checkout of python/cpython at PINNED_COMMIT and verifies their hashes. `build` renders the
retained excerpts to plain text with the rules in render_rst(), writes the synthetic fixture,
and indexes every passage by exact UTF-8 byte offsets [start, end) into the fixture files.
Offsets are into these plain-text files only, never into reST or HTML.
"""

import hashlib
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source"
FIXTURES = ROOT / "fixtures"

PINNED_COMMIT = "58ed60b7415e218ce3d608302e39b5e55bfb0e88"  # python/cpython branch 3.12, 2026-10-01
RST_PATH = "Doc/library/urllib.request.rst"
RST_BLOB = "09a8c0edc5ef7b58f5547d2f4584f13d451f90da"
RST_SHA256 = "55e3d9c4988694d529b6856af5ce7b691233821b7f1bf563d4d3dd265b3b7d5f"
LICENSE_SHA256 = "3b2f81fe21d181c499c59a256c8e1968455d6689d269aa85373bfb6af41da3bf"
PAGE_URL = "https://docs.python.org/3.12/library/urllib.request.html"

# (passage id, first line, last line, kind) -- 1-based inclusive line numbers in RST_PATH
EXCERPTS = [
    ("D01", 26, 30, "warning"),
    ("D02", 37, 37, "function"),
    ("D03", 39, 40, "para"),
    ("D04", 49, 52, "para"),
    ("D05", 54, 56, "para"),
    ("D06", 186, 186, "function"),
    ("D07", 188, 194, "para"),
    ("D08", 198, 204, "note"),
    ("D09", 319, 319, "class"),
    ("D10", 321, 327, "para"),
    ("D11", 329, 329, "para"),
    ("D12", 331, 334, "para"),
    ("D13", 338, 339, "note"),
    ("D14", 443, 443, "class"),
    ("D15", 445, 446, "para"),
    ("D16", 448, 449, "versionchanged"),
    ("D17", 670, 670, "method"),
    ("D18", 672, 679, "para"),
    ("D19", 1163, 1163, "method"),
    ("D20", 1165, 1165, "para"),
    ("D21", 1453, 1453, "class"),
    ("D22", 1455, 1455, "deprecated"),
    ("D23", 1467, 1470, "para"),
]

DOCS_FIXTURE = "urllib_request_3.12_excerpts.txt"
SYNTH_FIXTURE = "synthetic_cache_client.txt"

ROLE = re.compile(r":(\w+):`(~?)([^`]+)`")
LITERAL = re.compile(r"``(.+?)``")
EMPHASIS = re.compile(r"\*([^*\s][^*]*?)\*")
DIRECTIVE = re.compile(r"^\s*\.\. (\w+)::\s*(.*)$")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def render_inline(text):
    "Roles, ``literals`` and *emphasis* to plain text, the way the HTML page displays them."
    parts = LITERAL.split(text)  # odd items are literal contents, kept verbatim
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(part)
            continue

        def role(m):
            name, tilde, target = m.groups()
            shown = target.rsplit(".", 1)[-1] if tilde else target
            if name in ("func", "meth") and not shown.endswith(")"):
                shown += "()"
            return shown

        out.append(EMPHASIS.sub(r"\1", ROLE.sub(role, part)))
    return "".join(out)


def render_rst(lines, kind):
    "Render one excerpt (its raw source lines) to a single plain-text passage."
    head = DIRECTIVE.match(lines[0])
    if kind in ("function", "class", "method"):
        signature = head.group(2)
        prefix = {"function": "urllib.request.", "class": "class urllib.request.", "method": ""}[kind]
        return prefix + signature
    if kind == "deprecated":
        return f"Deprecated since version {head.group(2)}."
    body = lines
    label = {"warning": "Warning: ", "note": "Note: ", "para": ""}.get(kind)
    if kind == "versionchanged":
        label, body = f"Changed in version {head.group(2)}: ", lines[1:]
    text = " ".join(line.strip() for line in body if line.strip())
    return label + re.sub(r"\s+", " ", render_inline(text)).strip()


def synthetic_passages():
    "Hand-authored synthetic passages; generated so that NFD, duplicates and sizes are exact."
    greek = [chr(c) for c in range(0x3B1, 0x3CA) if c != 0x3C2]  # α..ω without final sigma: 24
    # 84 entries: S13 fits the 2048-byte budget alone, but not together with S14 (checked by check_oracle.py)
    quota_entries = [f"tenant-{g}{n} → {10 + (i * 7 + n) % 40} MiB" for n in (1, 2, 3, 4) for i, g in enumerate(greek)]
    return {
        "S01": "Example cache client – configuration notes for version 2 (“stable”).",
        "S02": "The check_hostname option enables TLS hostname verification; it is enabled by default "
        "and must not be disabled in production.",
        "S03": "Before rotating certificates, operators check hostname records in the internal DNS zone.",
        "S04": "The response cache is shared between threads of one process.",
        "S05": "The response cache is not shared between processes; each worker keeps its own copy.",
        "S06": "Retries apply only to idempotent requests (GET, HEAD and OPTIONS).",
        "S07": "Retries apply only to idempotent requests (GET, HEAD and OPTIONS).",
        "S08": "The timeout applies to the connection attempt.",
        "S09": "It does not apply to reading the response body, which can block indefinitely.",
        "S10": "Zeitüberschreitung: Die Verbindung wird nach 30 Sekunden abgebrochen, "
        "außer wenn retry_on_timeout gesetzt ist.",
        "S11": "タイムアウトは接続試行にのみ適用されます。読み取りには適用されません。",
        "S12": "Le résumé de configuration est stocké dans cache.toml (forme NFD).",
        "S13": "Quota table per tenant: " + "; ".join(quota_entries[:84]) + ".",
        "S14": "The limits above are suspended for tenants in read-only mode.",
        "S15": "Pool sizing: " + "接続プールの大きさはワーカー数の二倍を推奨します。" * 28,
        "S16": "🔒 Security note: the client never logs the proxy password; it is redacted as ••••.",
    }


def fixture_text(passages):
    "One passage per line, passages separated by one blank line, final newline."
    return "\n\n".join(passages) + "\n"


def index(fixture_name, ids, text, sources=None):
    data = text.encode("utf-8")
    entries, pos = [], 0
    for pid, passage in zip(ids, text.rstrip("\n").split("\n\n"), strict=True):
        raw = passage.encode("utf-8")
        start = data.index(raw, pos)
        end = start + len(raw)
        assert start == pos, (pid, start, pos)
        entry = {
            "id": pid,
            "fixture": f"fixtures/{fixture_name}",
            "byte_start": start,
            "byte_end": end,
            "bytes": len(raw),
            "chars": len(passage),
            "sha256": sha256(raw),
            "is_nfc": unicodedata.is_normalized("NFC", passage),
        }
        if sources:
            entry["source"] = sources[pid]
        entries.append(entry)
        pos = end + 2  # the "\n\n" separator, not part of any passage
    return entries


def extract(cpython):
    rst = (cpython / RST_PATH).read_bytes()
    if sha256(rst) != RST_SHA256:
        sys.exit(f"{RST_PATH}: sha256 {sha256(rst)} is not the pinned {RST_SHA256}")
    lines = rst.decode("utf-8").splitlines(keepends=True)
    excerpts = []
    for pid, first, last, kind in EXCERPTS:
        raw = "".join(lines[first - 1 : last])
        excerpts.append(
            {
                "id": pid,
                "line_start": first,
                "line_end": last,
                "kind": kind,
                "raw": raw,
                "raw_sha256": sha256(raw.encode("utf-8")),
            }
        )
    record = {
        "repository": "https://github.com/python/cpython",
        "commit": PINNED_COMMIT,
        "path": RST_PATH,
        "git_blob": RST_BLOB,
        "file_sha256": RST_SHA256,
        "file_bytes": len(rst),
        "rendered_page": PAGE_URL,
        "excerpts": excerpts,
    }
    SOURCE.mkdir(exist_ok=True)
    out = SOURCE / "urllib.request.rst.excerpts.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    license_file = cpython / "LICENSE"
    if sha256(license_file.read_bytes()) != LICENSE_SHA256:
        sys.exit("LICENSE: not the pinned file")
    shutil.copyfile(license_file, SOURCE / "LICENSE-PSF-cpython-3.12")
    print(f"extracted {len(excerpts)} excerpts from {RST_PATH} at {PINNED_COMMIT}")


def build_outputs():
    record = json.loads((SOURCE / "urllib.request.rst.excerpts.json").read_text(encoding="utf-8"))
    sources, docs_ids, docs_passages = {}, [], []
    for ex in record["excerpts"]:
        if sha256(ex["raw"].encode("utf-8")) != ex["raw_sha256"]:
            sys.exit(f"{ex['id']}: retained source excerpt does not match its hash")
        passage = render_rst(ex["raw"].splitlines(), ex["kind"])
        docs_ids.append(ex["id"])
        docs_passages.append(passage)
        sources[ex["id"]] = {"lines": [ex["line_start"], ex["line_end"]], "kind": ex["kind"], "raw_sha256": ex["raw_sha256"]}
    synth = synthetic_passages()
    docs_text, synth_text = fixture_text(docs_passages), fixture_text(synth.values())
    passages = {
        "offsets": "UTF-8 byte offsets [byte_start, byte_end) into the plain-text fixture files; not reST, not HTML",
        "separator": "passages are single lines separated by one blank line (b'\\n\\n'), which no passage includes",
        "fixtures": {
            "docs": {
                "file": f"fixtures/{DOCS_FIXTURE}",
                "sha256": sha256(docs_text.encode("utf-8")),
                "bytes": len(docs_text.encode("utf-8")),
                "source": f"{record['repository']} {record['commit']} {record['path']}",
            },
            "synthetic": {
                "file": f"fixtures/{SYNTH_FIXTURE}",
                "sha256": sha256(synth_text.encode("utf-8")),
                "bytes": len(synth_text.encode("utf-8")),
                "source": "synthetic, generated by scripts/build_fixtures.py",
            },
        },
        "passages": index(DOCS_FIXTURE, docs_ids, docs_text, sources) + index(SYNTH_FIXTURE, list(synth), synth_text),
    }
    return {
        FIXTURES / DOCS_FIXTURE: docs_text.encode("utf-8"),
        FIXTURES / SYNTH_FIXTURE: synth_text.encode("utf-8"),
        FIXTURES / "passages.json": (json.dumps(passages, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
    }


def main():
    mode = sys.argv[1]
    if mode == "extract":
        extract(Path(sys.argv[2]))
        return 0
    outputs = build_outputs()
    if mode == "build":
        FIXTURES.mkdir(exist_ok=True)
        for path, data in outputs.items():
            path.write_bytes(data)
            print(f"wrote {path.relative_to(ROOT).as_posix()} {len(data)} bytes sha256={sha256(data)}")
        return 0
    differ = [p.relative_to(ROOT).as_posix() for p, d in outputs.items() if not p.exists() or p.read_bytes() != d]
    print("check: " + ("identical" if not differ else f"DIFFERS: {differ}"))
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())

"""Run the pre-registered extraction matrix over the synthetic fixtures.

Implements rules R1-R12 of fixtures/expectations.json verbatim. Every raw output is kept.

Usage: python mode_matrix.py FIXTURE_DIR OUTPUT_DIR
Writes OUTPUT_DIR/matrix_outputs.jsonl (one record per configuration, with the raw output)
and OUTPUT_DIR/matrix_summary.json; prints a summary. Exit code 1 if any loss (R11).
"""

import hashlib
import itertools
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

import courlan
import lxml
import trafilatura
from lxml import etree
from trafilatura import extract

ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
LIST_LINE = re.compile(r"^(\s*)[-*+]\s")
PIPE = re.compile(r"(?<!\\)\|")


def tokens(text):
    return re.findall(r"\w+", text)


def contains(seq, sub):
    return bool(sub) and any(seq[i : i + len(sub)] == sub for i in range(len(seq) - len(sub) + 1))


class View:
    "R1: the views of one output."

    def __init__(self, output, fmt):
        self.fmt = fmt
        self.raw = output or ""
        self.root = None
        if output is None:
            self.plain = self.flat = ""
        elif fmt == "xml":
            self.root = etree.fromstring(output.encode("utf-8"))
            self.plain = " ".join(self.root.itertext())
            self.flat = "".join(self.root.itertext())
        else:
            self.plain = ESCAPE.sub(r"\1", output)
            self.flat = output


def check_statement(v, req):
    return contains(tokens(v.plain), tokens(req["text"]))


def check_code_chars(v, req):
    return req["code"] in (v.flat if v.root is not None else v.raw)


def check_code_marked(v, req):
    if v.root is None:
        return f"`{req['code']}`" in v.raw
    return any(
        "".join(el.itertext()) == req["code"]
        for el in v.root.iter()
        if el.tag == "code" or (el.tag == "hi" and el.get("rend") == "#t")
    )


def check_code_block(v, req):
    return req["block"] in (v.flat if v.root is not None else v.raw)


def code_block_marked(v, req):
    "INFO part of R5."
    if v.root is None:
        return bool(re.search(r"```[^\n]*\n" + re.escape(req["block"]), v.raw))
    return any(req["block"] in "".join(el.itertext()) for el in v.root.iter("code"))


def check_list_nesting(v, req):
    parent, item = tokens(req["parent"]), tokens(req["item"])
    if v.root is not None:
        for el in v.root.iter("item"):
            if not contains(tokens(" ".join(el.itertext())), item):
                continue
            if any(contains(tokens(" ".join(a.itertext())), parent) for a in el.iterancestors("item")):
                return True
        return False
    lines = v.raw.splitlines()
    for i, l1 in enumerate(lines):
        m1 = LIST_LINE.match(l1)
        if not m1 or not contains(tokens(ESCAPE.sub(r"\1", l1)), parent):
            continue
        for l2 in lines[i + 1 :]:
            m2 = LIST_LINE.match(l2)
            if m2 and contains(tokens(ESCAPE.sub(r"\1", l2)), item) and len(m2.group(1)) > len(m1.group(1)):
                return True
    return False


def check_emphasis(v, req):
    if v.root is None:
        return any(f"{m}{req['word']}{m}" in v.raw for m in req["markdown"])
    return any(el.get("rend") in req["rend"] and "".join(el.itertext()) == req["word"] for el in v.root.iter("hi"))


def md_cells(line):
    line = line.strip()
    line = line.removeprefix("|")
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells = []
    for cell in PIPE.split(line):
        cell = ESCAPE.sub(r"\1", cell.strip())
        if len(cell) >= 2 and cell.startswith("`") and cell.endswith("`"):
            cell = cell[1:-1]
        cells.append(cell)
    return cells


def check_table_row(v, req):
    if v.root is not None:
        for row in v.root.iter("row"):
            cells = [re.sub(r"\s+", " ", " ".join(c.itertext())).strip() for c in row.iterchildren("cell")]
            if cells == req["cells"]:
                return True
        return False
    return any(md_cells(line) == req["cells"] for line in v.raw.splitlines() if "|" in line)


def check_link(v, req):
    if v.root is not None:
        return any(
            ref.get("target") == req["target"] and "".join(ref.itertext()).strip() == req["anchor"]
            for ref in v.root.iter("ref")
        )
    return f"[{req['anchor']}]({req['target']})" in v.raw or f"[{req['anchor']}](<{req['target']}>)" in v.raw


CHECKS = {
    "statement": check_statement,
    "code_chars": check_code_chars,
    "code_marked": check_code_marked,
    "code_block": check_code_block,
    "list_nesting": check_list_nesting,
    "emphasis_marked": check_emphasis,
    "table_row": check_table_row,
    "link": check_link,
}


def gate_state(gate, fmt, links, tables, formatting):
    "Returns 'required', 'excluded' or 'info'."
    if gate == "always":
        return "required"
    if gate == "links":
        return "required" if links else "excluded"
    if gate == "tables":
        return "required" if tables else "excluded"
    if gate == "formatting":
        return "required" if (formatting or fmt == "markdown") else "excluded"
    if gate == "structure":
        return "required" if fmt in ("markdown", "xml") else "info"
    raise ValueError(gate)


def verify_hashes(fixture_dir):
    for line in (fixture_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        actual = hashlib.sha256((fixture_dir / name.strip()).read_bytes()).hexdigest()
        if actual != digest:
            sys.exit(f"hash mismatch for {name}: {actual} != {digest}")


def environment():
    root = Path(trafilatura.__file__).parent.parent

    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True, check=False, cwd=root).stdout.strip()

    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "trafilatura": trafilatura.__version__,
        "git_head": git("rev-parse", "HEAD"),
        "source_tree_dirty": bool(git("status", "--porcelain", "--", "trafilatura")),
        "lxml": lxml.__version__,
        "libxml2": ".".join(map(str, etree.LIBXML_VERSION)),
        "courlan": getattr(courlan, "__version__", "unknown"),
    }


def main():
    fixture_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    verify_hashes(fixture_dir)
    expectations = json.loads((fixture_dir / "expectations.json").read_text(encoding="utf-8"))
    matrix = expectations["matrix"]
    out_dir.mkdir(parents=True, exist_ok=True)
    losses = []
    per_req = {}
    records = 0
    with (out_dir / "matrix_outputs.jsonl").open("w", encoding="utf-8", newline="\n") as jsonl:
        for name, fixture in expectations["fixtures"].items():
            data = (fixture_dir / name).read_bytes()
            for mode, links, tables, formatting, fmt in itertools.product(
                matrix["modes"],
                matrix["include_links"],
                matrix["include_tables"],
                matrix["include_formatting"],
                matrix["output_formats"],
            ):
                kwargs = dict(matrix["modes"][mode])
                output = extract(
                    data,
                    url=fixture["url"],
                    output_format=fmt,
                    include_links=links,
                    include_tables=tables,
                    include_formatting=formatting,
                    **kwargs,
                )
                view = View(output, fmt)
                verdicts = {}
                for req in fixture["requirements"]:
                    state = gate_state(req["gate"], fmt, links, tables, formatting)
                    observed = output is not None and CHECKS[req["type"]](view, req)
                    if state == "required":
                        verdict = "PASS" if observed else "FAIL"
                    elif state == "excluded":
                        verdict = "EXCLUDED_BY_OPTION"
                    else:
                        verdict = "INFO"
                    verdicts[req["id"]] = {"verdict": verdict, "observed": observed}
                    if req["type"] == "code_block":
                        verdicts[req["id"]]["marked_as_code_info"] = output is not None and code_block_marked(view, req)
                    config = f"{mode} L{int(links)} T{int(tables)} F{int(formatting)} {fmt}"
                    stats = per_req.setdefault(
                        f"{name}::{req['id']}", {"PASS": 0, "FAIL": 0, "EXCLUDED_BY_OPTION": 0, "INFO": 0}
                    )
                    stats[verdict] += 1
                    if verdict == "FAIL":
                        losses.append({"fixture": name, "requirement": req["id"], "type": req["type"], "config": config})
                boilerplate = [b for b in fixture.get("boilerplate", []) if b in view.plain]
                record = {
                    "fixture": name,
                    "mode": mode,
                    "include_links": links,
                    "include_tables": tables,
                    "include_formatting": formatting,
                    "output_format": fmt,
                    "call": {
                        "url": fixture["url"],
                        "output_format": fmt,
                        "include_links": links,
                        "include_tables": tables,
                        "include_formatting": formatting,
                        **kwargs,
                    },
                    "output_is_none": output is None,
                    "output_chars": len(output or ""),
                    "boilerplate_found_info": boilerplate,
                    "verdicts": verdicts,
                    "output": output,
                }
                jsonl.write(json.dumps(record, ensure_ascii=False) + "\n")
                records += 1

    by_config = {}
    for loss in losses:
        by_config[loss["config"]] = by_config.get(loss["config"], 0) + 1
    summary = {
        "environment": environment(),
        "expectations_sha256": hashlib.sha256((fixture_dir / "expectations.json").read_bytes()).hexdigest(),
        "configurations": records,
        "losses_total": len(losses),
        "losses_by_requirement": {k: v for k, v in per_req.items() if v["FAIL"]},
        "requirements": per_req,
        "losses": losses,
    }
    (out_dir / "matrix_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary["environment"], indent=2))
    print(f"configurations: {records}, losses: {len(losses)}")
    print(f"\n{'requirement':58} PASS FAIL EXCL INFO")
    for key, stats in per_req.items():
        flag = "  <-- loss" if stats["FAIL"] else ""
        print(f"{key:58} {stats['PASS']:4} {stats['FAIL']:4} {stats['EXCLUDED_BY_OPTION']:4} {stats['INFO']:4}{flag}")
    return 1 if losses else 0


if __name__ == "__main__":
    sys.exit(main())

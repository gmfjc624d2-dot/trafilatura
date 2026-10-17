"""Run every research step against the trafilatura that `python` imports, with logs.

Usage: python run_all.py LABEL [--ablation]
  LABEL       results go to results/LABEL/, logs to logs/LABEL_<step>.log
  --ablation  also run the naive-fix ablation (only meaningful on the 2.3.1 source)

Each log starts with the exact command and ends with "exit=<code>". The exit code of this
driver is 0; read the step exit codes in the logs (1 = losses/failures found, by design).
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
REPO = RESEARCH.parent.parent


def step(label, name, args):
    log = RESEARCH / "logs" / f"{label}_{name}.log"
    cmd = [sys.executable, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    shown = " ".join(Path(a).relative_to(REPO).as_posix() if a.startswith(str(REPO)) else a for a in args)
    log.write_text(f"$ python {shown}\n{proc.stdout}{proc.stderr}exit={proc.returncode}\n", encoding="utf-8")
    print(f"{name}: exit={proc.returncode} -> {log.relative_to(REPO).as_posix()}")


def main():
    label = sys.argv[1]
    out = RESEARCH / "results" / label
    fixtures = RESEARCH / "fixtures"
    step(label, "check_expectations", [str(HERE / "check_expectations.py"), str(fixtures)])
    step(label, "repro_links", [str(HERE / "repro_links.py"), str(out)])
    step(label, "public_corpus_links_as-is", [str(HERE / "public_corpus_links.py"), str(REPO), str(out)])
    if "--ablation" in sys.argv:
        step(
            label,
            "public_corpus_links_naive-ablation",
            [str(HERE / "public_corpus_links.py"), str(REPO), str(out), "--variant", "naive-ablation"],
        )
    step(label, "mode_matrix", [str(HERE / "mode_matrix.py"), str(fixtures), str(out)])
    return 0


if __name__ == "__main__":
    sys.exit(main())

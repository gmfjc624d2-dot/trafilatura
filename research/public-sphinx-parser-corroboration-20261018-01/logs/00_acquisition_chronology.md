# Acquisition chronology (as it happened, gaps kept)

All times are UTC on 2026-10-18 (container clock, file modification times of the scratch copies).
Scratch directories stay in the session scratchpad. They are not committed and were not deleted:
`<scratch>/acq-html5lib` (the first acquisition) and `<scratch>/acq2` (a second, logged download).

1. **03:25:39** First registry fetch into `acq-html5lib/registry/`: the PyPI JSON for html5lib 1.1,
   six 1.17.0 and webencodings 0.5.1, plus the project-level records of all three. I read the
   results in the terminal: html5lib 1.1 is the latest release (wheel uploaded 2020-06-22,
   Requires-Dist `six (>=1.9)`, `webencodings`); six 1.17.0 is the latest (2024-12-04); webencodings
   shows **0.6.1** as its latest.
2. **03:25:51** The webencodings 0.6.0 and 0.6.1 records were fetched after that observation: both
   were uploaded 2026-08-15, Requires-Python >=3.10, with different project URLs.
3. **03:26:07** The three wheels were downloaded into `acq-html5lib/downloads/`. Each file's
   sha256 and size matched the registry digest (`sha256sum -c`: OK ×3).
4. Then the wheel contents were inspected as data, without installing or importing. Result: zip
   integrity OK and every RECORD hash and size matching (html5lib 38, six 5, webencodings 10
   hashed entries), no native members. The html5lib and six dist-info carry LICENSE files, but
   **webencodings 0.5.1 has no license file**, only `License: BSD`.
5. **03:26:32** The webencodings 0.5.1 sdist (sha256 OK) has no LICENSE file either. Its
   `__init__.py` says ":license: BSD, see LICENSE for details."
6. **03:26:47** The LICENSE was fetched from the project repository at tag v0.5.1 (HTTP 200,
   1490 bytes); `LICENSE.txt` and `LICENSE.rst` were 404. `git ls-remote` showed v0.5.1 as a
   lightweight tag on commit `fa2cb5d75ab41e63ace691bc0825d3432ba7d694`.
7. The html5lib 1.1 sources from the wheel were read (encoding order, `override_encoding`,
   `useChardet`, errors, the etree builder) to state the policy and predictions.
8. **Gap:** steps 1-7 were not written to a log file at the time. Their terminal output exists only
   in the session transcript and is summarised here, not reproduced.
9. **03:28:01** I then re-ran the acquisition as one logged command into `acq2`
   (`logs/01_acquisition.log`). This **repeated the downloads**; it was not needed. Every registry
   record, all three wheels and the LICENSE are byte-identical to the first acquisition (checked
   afterwards with `cmp`, no new fetch). The wheels in `wheels/` were copied from `acq2` and are
   byte-identical to the first download.
10. After the request not to repeat downloads or verification just for a cleaner log, nothing was
    fetched again. `scripts/verify_wheels.py` exists for replay and recovery, not as a new
    acquisition.

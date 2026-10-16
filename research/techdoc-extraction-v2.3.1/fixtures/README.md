# Synthetic technical-documentation fixtures

All files in this directory are **synthetic**: written from scratch for this research on
2026-10-16, without copying any third-party page. They use only reserved example domains
(RFC 2606 / RFC 6761: `example.org`, `example.com`, `example.net`), and are contributed under
the repository's Apache-2.0 license. No network access is needed to use them.

| file | property under test | document URL passed as `url=` |
|---|---|---|
| `f1_prerequisite_short_intro.html` | central prerequisite in a short introductory paragraph | `https://docs.example.org/sdk/v2/reference/connect.html` |
| `f2_inline_code.html` | inline code expressions and an indented code block | `https://docs.example.org/sdk/v2/reference/client.html` |
| `f3_nested_list_negation.html` | nested list with negations | `https://docs.example.org/sdk/v2/platforms.html` |
| `f4_typed_mapping_table.html` | typed mapping table (incl. a `str \| None` union cell) | `https://docs.example.org/sdk/v2/reference/options.html` |
| `f5_reference_links.html` | relative and absolute reference URLs | `https://docs.example.org/sdk/v2/reference/client.html?lang=en` |
| `f6_malformed.html` | malformed HTML | `https://docs.example.org/sdk/v3/migration/notes.html` |
| `f7_base_element.html` | `<base href>` semantics | `https://docs.example.org/sdk/v2/reference/client.html` |
| `f8_combined_reference_page.html` | all of the above on one page, heavier boilerplate | `https://docs.example.org/sdk/v2/reference/publish.html?tab=python` |

`expectations.json` is the **pre-registered** list of required elements, the gate (option)
under which each is required, and the exact checking rules (R1-R12). It was committed, with
`SHA256SUMS`, before any extraction was run on the fixtures. `scripts/check_expectations.py`
validates the expectations against the fixture sources only (it does not run trafilatura);
`logs/check_expectations.log` records the two corrections it prompted before the commit:
`f6_malformed.html` originally had an unclosed `<title>` (RCDATA: browsers and libxml2 swallow
the whole body into the title, so no body requirement could be fair), and the checker itself
glued adjacent `<li>` texts together.

Verify the bytes with `sha256sum -c SHA256SUMS` (Linux), `shasum -a 256 -c SHA256SUMS` (macOS)
or the Python one-liner in `../PORTABLE_TEST_RECIPE.md` (any OS).

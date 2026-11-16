#!/usr/bin/env python3
"""Mechanical checks for a spec review report.

A review report is read by someone who will act on it, so a broken quote, a dangling
`SPEC-nn` pointer or a table that claims nine findings and holds eight is a defect in the
report, not a cosmetic problem. This script checks the mechanics that a human read misses.

Usage
    python3 verify-report.py <report.md> <source.md> [--intent <intent.md>]

    report.md   reviews/spec-YYYY-MM-DD.issues-Iteration_<n>.md
    source.md   the spec under review (spec.md / spec_example.md)
    --intent    optional intent.md; quotes sourced from it are accepted too

Exit code 0 when every check passes, 1 otherwise. Every failure prints the line number and
the offending text, so it can be fixed without re-reading the report.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SPEC_FAMILY = "**What the document says**"
REQUIRED_BLOCKS = [
    "**What the document says**",
    "**Context**",
    "**In one sentence**",
    "**Question to the author**",
    "**Close by:**",
]


def norm(text: str) -> str:
    text = text.replace("**", "").replace("`", "").replace("\u2014", "-").replace("\u2019", "'")
    return re.sub(r"\s+", " ", text).strip().lower()


def fragments(line: str):
    """Split a blockquote line into quotable fragments, dropping section/line markers."""
    body = line.lstrip(">").strip()
    body = re.sub(r"\((?:§[^)]*|l\.[^)]*)\)", " ", body)
    body = re.sub(r"\([^)]*l\.[^)]*\)", " ", body)
    body = re.sub(r"\([^()]{1,60}\)\s*$", "", body).strip()  # trailing citation, e.g. (FR-04)
    body = body.replace('"', "").strip()
    body = re.sub(r"^-\s+", "", body)
    return [f.strip().strip("*").strip() for f in re.split(r"(?<=[.;:])\s+|\.\.\.", body)]


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    report = Path(argv[1])
    source = Path(argv[2])
    intent = Path(argv[4]) if len(argv) > 4 and argv[3] == "--intent" else None

    text = report.read_text()
    sources = []
    if source.exists():
        sources.append(norm(source.read_text()))
    else:
        # A MISSING/UNCHANGED run reports the absence of the file: there is nothing to quote.
        print(f"NOTE source {source.name} not found - quote checks skipped")
    if intent and intent.exists():
        sources.append(norm(intent.read_text()))
    lines = text.split("\n")
    failures = 0

    def fail(msg):
        nonlocal failures
        failures += 1
        print(f"FAIL {msg}")

    spec_family = SPEC_FAMILY in text
    id_re = re.compile(r"^### ([A-Z]{2,5})-(\d+)\b")
    prefixes = {m.group(1) for m in (id_re.match(l) for l in lines) if m}

    # 1. quote integrity -----------------------------------------------------
    short_run = re.search(r"\*\*State:\*\*\s*(MISSING|UNCHANGED)", text)
    if short_run:
        print(f"NOTE state {short_run.group(1)} - quote checks skipped (nothing was reviewed)")
    inline_re = re.compile(r"^\s*[-*]?\s*\*\*(?:Document says|What the document says):\*\*\s*(.+)$")
    current = None
    for i, line in enumerate(lines, 1):
        m = id_re.match(line)
        if m:
            current = f"{m.group(1)}-{m.group(2)}"
        inline = inline_re.match(line)
        if inline:
            frags = re.findall(r'"([^"]{20,})"', inline.group(1))
        elif line.startswith(">"):
            frags = fragments(line)
        else:
            continue
        if not sources or short_run:
            break
        for frag in frags:
            if len(frag) < 30:
                continue
            needle = norm(frag)
            if not any(needle in s for s in sources):
                fail(f"l.{i} {current}: quote not found in the source - \"{frag[:90]}\"")

    # 2. dangling references -------------------------------------------------
    pref = sorted(prefixes)[0] if len(prefixes) == 1 else "SPEC"
    headings = set(re.findall(rf"^### ({pref}-\d+)\b", text, re.M))
    cited = set(re.findall(rf"\b{pref}-\d{{2}}\b", text))
    if short_run:
        # A blocking-only run cites the previous report's findings on purpose: those headings live
        # in iteration n-1, not here.
        if cited - headings:
            print("NOTE short report cites findings of an earlier iteration - dangling refs skipped")
    else:
        for ref in sorted(cited - headings):
            fail(f"reference to {ref} has no finding heading")

    # 3. numbering -----------------------------------------------------------
    ids = re.findall(rf"^### ({pref}-\d+)\b", text, re.M)
    expected = [f"{pref}-{n:02d}" for n in range(1, len(ids) + 1)]
    if ids != expected:
        missing = sorted(set(expected) - set(ids))
        fail(f"finding ids are not contiguous: {len(ids)} findings, missing {missing or 'none'}")

    # 3b. file name and iteration -------------------------------------------
    pattern = (
        r"^intent-\d{4}-\d{2}-\d{2}\.findings-Iteration_(\d+)\.md$"
        if pref == "INT"
        else r"^spec-\d{4}-\d{2}-\d{2}\.issues-Iteration_(\d+)\.md$"
    )
    m_name = re.match(pattern, report.name)
    if not m_name:
        fail(f"file name {report.name!r} does not match {pattern}")
    else:
        n_name = int(m_name.group(1))
        it = re.search(r"\*\*Iteration:\*\*\s*(\d+)", text)
        if it and int(it.group(1)) != n_name:
            fail(f"file name says iteration {n_name}, header says iteration {it.group(1)}")

    # 4. required blocks -----------------------------------------------------
    chunks = re.split(rf"^### {pref}-", text, flags=re.M)[1:]
    for chunk in chunks:
        ident = f"{pref}-" + chunk.split(" ", 1)[0]
        if spec_family:
            for block in REQUIRED_BLOCKS:
                if block not in chunk:
                    fail(f"{ident}: missing block {block}")
        if "Severity:** Blocking" in chunk:
            if not re.search(r"Question", chunk):
                fail(f"{ident}: Blocking finding with no question to the author")
            if spec_family:
                options = len(set(re.findall(r"^\s*[-*]\s+\*\*([A-C])[.)]\s", chunk, re.M)))
                if options < 3:
                    fail(f"{ident}: Blocking with {options} ready-to-paste options (need 3)")

    # 5. declared counts -----------------------------------------------------
    sev = r"^\s*(?:- )?\*\*Severity:\*\*\s*{}"
    blocking = len(re.findall(sev.format("Blocking"), text, re.M))
    important = len(re.findall(sev.format("Important"), text, re.M))
    minor = len(re.findall(sev.format("Minor"), text, re.M))
    flat = text.replace("**", "").replace("`", "")
    declared = re.search(
        r"(\d+)\W{0,3}Blocking\W{1,3}(\d+)\W{0,3}Important\W{1,3}(\d+)\W{0,3}Minor", flat
    ) or re.search(
        r"Blocking\W{1,3}(\d+)\W{1,3}Important\W{1,3}(\d+)\W{1,3}Minor\W{1,3}(\d+)", flat
    )
    if declared:
        got = (blocking, important, minor)
        want = tuple(int(x) for x in declared.groups())
        if got != want:
            fail(f"verdict says {want[0]}/{want[1]}/{want[2]}, findings are {got[0]}/{got[1]}/{got[2]}")
    else:
        fail("no 'N Blocking / N Important / N Minor' verdict line found")

    questions = len(re.findall(r"^\s*(?:- )?\*\*Question", text, re.M))
    if questions < blocking:
        fail(f"{questions} question blocks for {blocking} Blocking findings")
    defaults = len(re.findall(r"^\*\*If nobody decides\*\*", text, re.M))
    if spec_family and defaults < blocking:
        fail(f"{defaults} defaults for {blocking} Blocking findings")

    # 6. tables --------------------------------------------------------------
    for i in range(1, len(lines)):
        row, prev = lines[i], lines[i - 1]
        if row.startswith("|") and row.rstrip().endswith("|") and prev.startswith("|"):
            if row.count("|") != prev.count("|"):
                fail(f"l.{i + 1}: table row has {row.count('|')} pipes, previous row has {prev.count('|')}")

    # 7. assertion inventory -------------------------------------------------
    rows = len(re.findall(r"^\| \d+ \| AC-\d", text, re.M))
    claimed = re.search(r"(\d+)\s*assertions?", text)
    if rows and claimed and int(claimed.group(1)) != rows:
        fail(f"assertion inventory has {rows} rows, text claims {claimed.group(1)} assertions")
    if rows and "NOT TESTABLE" not in text:
        fail("assertion inventory has no NOT TESTABLE row - probe results are missing")

    print(f"\n{len(ids)} findings ({blocking}/{important}/{minor}), {rows} assertion rows, {failures} failures")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

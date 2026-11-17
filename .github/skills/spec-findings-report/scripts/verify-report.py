#!/usr/bin/env python3
"""Mechanical checks for a review report (intent or spec kit).

A review report is read by someone who will act on it, so a broken quote, a dangling
`INT-nn` pointer or a table that claims nine findings and holds eight is a defect in the
report, not a cosmetic problem. This script checks the mechanics that a human read misses.

Usage
    python3 verify-report.py <report.md> <source.md> [--intent <intent.md>] [--input <file>]...

    report.md   reviews/intent-YYYY-MM-DD.findings-Iteration_<n>.md   (or the spec equivalent)
    source.md   the document under review (the archive the resolver produced)
    --intent    optional intent.md; quotes sourced from it are accepted too
    --input     an evidence file the review used; repeatable. Quotes sourced from it are
                accepted, and the report must list the file by name

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
REGISTER_HEAD = re.compile(r"^##+[^\n]*(?:answer register|inputs and answers)[^\n]*$", re.I | re.M)
SOURCE_CELL = re.compile(r"([\w./\\-]+\.(?:md|markdown|txt|csv))\s*\(l\.(\d+)\)")
EFFECTS = ("confirmed", "not a defect", "still open", "n/a")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".heic"}


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


def section_after(text: str, match) -> str:
    """The block that follows a heading match, up to the next level-2 heading."""
    start = match.end()
    nxt = re.search(r"^##\s", text[start:], re.M)
    return text[start : start + nxt.start()] if nxt else text[start:]


def main(argv):
    positional, intent, inputs = [], None, []
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in ("--intent", "--input"):
            if i + 1 >= len(argv):
                print(f"FAIL {arg} needs a value")
                return 2
            if arg == "--intent":
                intent = Path(argv[i + 1])
            else:
                inputs.append(Path(argv[i + 1]))
            i += 2
            continue
        if arg in ("-h", "--help"):
            print(__doc__)
            return 0
        positional.append(arg)
        i += 1
    if len(positional) < 2:
        print(__doc__)
        return 2
    report, source = Path(positional[0]), Path(positional[1])

    text = report.read_text()
    sources = []          # normalized text of every document a quote may come from
    pool = {}             # basename -> line count, for the answer register check
    if source.exists():
        sources.append(norm(source.read_text()))
        pool[source.name] = len(source.read_text().splitlines())
    else:
        # A MISSING/UNCHANGED run reports the absence of the file: there is nothing to quote.
        print(f"NOTE source {source.name} not found - quote checks skipped")
    if intent and intent.exists():
        sources.append(norm(intent.read_text()))
        pool[intent.name] = len(intent.read_text().splitlines())
    unnamed = []
    for path in inputs:
        if not path.exists():
            print(f"NOTE input {path.name} not found - ignored")
            continue
        # An input the review was given is an input the review must account for by name, even when
        # what it did was settle nothing. Silence about a file is how evidence disappears.
        if path.name not in text:
            unnamed.append(path.name)
        if path.suffix.lower() in IMAGE_SUFFIXES:
            # A screenshot carries no quotable line: it may be named, never cited as a source.
            print(f"NOTE input {path.name} is an image - nameable, not quotable")
            pool[path.name] = 0
            continue
        body = path.read_text(errors="replace")
        sources.append(norm(body))
        pool[path.name] = len(body.splitlines())
    lines = text.split("\n")
    failures = 0

    def fail(msg):
        nonlocal failures
        failures += 1
        print(f"FAIL {msg}")

    for name in unnamed:
        fail(f"input {name} was given to the review and the report never names it")

    spec_family = SPEC_FAMILY in text
    id_re = re.compile(r"^### ([A-Z]{2,5})-(\d+)\b")
    prefixes = {m.group(1) for m in (id_re.match(l) for l in lines) if m}

    register = REGISTER_HEAD.search(text)
    register_block = (section_after(text, register) or "") if register else ""
    citable = text.replace(register_block, "") if register_block else text

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
    # The delta section names findings that were closed earlier and have no heading here.
    delta = re.search(r"^#{1,3} .*Delta", text, re.M)
    delta_block = (section_after(text, delta) or "") if delta else ""
    # ... and the register records the ids it settled. Both may name an id with no heading here;
    # anywhere else in the report an unknown id is a reference the reader cannot follow.
    allowed = headings | set(re.findall(rf"\b{pref}-\d{{2}}\b", (register_block + "\n" + delta_block)))
    cited = set(re.findall(rf"\b{pref}-\d{{2}}\b", text))
    if short_run:
        # A blocking-only run cites the previous report's findings on purpose: those headings live
        # in iteration n-1, not here.
        if cited - headings:
            print("NOTE short report cites findings of an earlier iteration - dangling refs skipped")
    else:
        for ref in sorted(cited - allowed):
            fail(f"reference to {ref} has no finding heading and no register or delta row")

    # 3. numbering -----------------------------------------------------------
    # A finding keeps the number it was opened with, across iterations: renumbering makes the delta
    # unreachable and lets a closed question come back with a new name. So contiguity is required
    # from the first iteration only; later iterations carry gaps where findings were closed.
    ids = re.findall(rf"^### ({pref}-\d+)\b", text, re.M)
    m_iter = re.search(r"\*\*Iteration:\*\*\s*(\d+)", text)
    iteration = int(m_iter.group(1)) if m_iter else 1
    if len(set(ids)) != len(ids):
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        fail(f"finding ids repeat: {repeated}")
    order = sorted(ids, key=lambda s: int(s.split("-")[1]))
    if ids != order:
        fail("finding ids are not in ascending order")
    if iteration == 1:
        expected = [f"{pref}-{n:02d}" for n in range(1, len(ids) + 1)]
        if ids != expected:
            missing = sorted(set(expected) - set(ids))
            fail(f"finding ids are not contiguous: {len(ids)} findings, missing {missing or 'none'}")
    elif ids:
        print(f"NOTE iteration {iteration} - ids keep their number; gaps are findings closed earlier")

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

    # 8. evidence inputs declared -------------------------------------------
    for path in inputs:
        if path.exists() and path.name not in text:
            fail(f"input {path.name} was passed to the review but the report never names it")

    # 9. answer register -----------------------------------------------------
    if register:
        data_rows = 0
        for i, line in enumerate(register_block.split("\n"), 1):
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 5 or re.fullmatch(r"[-: ]+", cells[0] or "-") or "source" in cells[-2].lower():
                continue
            data_rows += 1
            ident = re.search(rf"\b({pref}-\d{{2}})\b", cells[0])
            if not ident:
                fail(f"answer register row {data_rows}: first cell is not a {pref}-nn id - {line[:70]}")
            effect = cells[-1].lower()
            if not any(word in effect for word in EFFECTS):
                fail(f"answer register row {data_rows}: effect {cells[-1][:40]!r} is not one of {EFFECTS}")
            # An unanswered question has no source: `-` is legal only for `still open`.
            if "still open" in effect and re.fullmatch(r"[-\u2014\s]*(none|n/a)?", cells[-2], re.I):
                continue
            cite = SOURCE_CELL.search(cells[-2])
            if not cite:
                fail(f"answer register row {data_rows}: source {cells[-2][:40]!r} is not 'file (l.N)'")
                continue
            # The report may cite `reviews/<report>_answers.md` while --input got an absolute path:
            # compare on the basename, which is what the pool is keyed by.
            name, line_no = Path(cite.group(1)).name, int(cite.group(2))
            if name not in pool:
                fail(f"answer register row {data_rows}: source {name} was not given to the review")
            elif line_no > pool[name]:
                fail(
                    f"answer register row {data_rows}: {name} has {pool[name]} lines, "
                    f"the register cites l.{line_no}"
                )
        if not data_rows:
            if "|" in register_block:
                fail("answer register section is empty - an input was read but no answer was recorded")
            else:
                print("NOTE answer register has no table - the review ran without evidence answers")

    print(
        f"\n{len(ids)} findings ({blocking}/{important}/{minor}), {rows} assertion rows, "
        f"{len(inputs)} inputs, {failures} failures"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

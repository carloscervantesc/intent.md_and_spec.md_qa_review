#!/usr/bin/env python3
"""Build the evidence manifest for an intent review.

A review of `intent.md` often arrives with extra material: an earlier report of ours that the
author annotated between the lines, a filled-in answer sheet, an example of the report shape they
want. This script reads those files and turns them into one JSON object the agent can act on, so
the reviewer never has to guess which comment belongs to which question.

Usage
    python3 intent-inputs.py [--root DIR] [--doc intent.md] [--with-previous]
                             [--no-scan] [--scan-dir DIR] [--input PATH]...
                             [--comment "B01 <statement>"]... [--author NAME] [--date YYYY-MM-DD]

    --root       workspace root (default: current directory)
    --doc        the reviewed document, relative to --root (default: intent.md)
    --input      a file the user named; any number, in any order
    --with-previous  also read the newest report in reviews/
    --scan-dir   an extra folder to read as well (repeatable by calling the flag again)
    --no-scan    read only what --input names
    --comment    one statement from the requester deciding a finding: "<id> <text>". The id may be
                 INT-01, int1, I-1 or B01 (the block it belongs to) - it is normalised to INT-nn.
                 Recorded in reviews/intent-comments-YYYY-MM-DD.md and read as a signed answer.
    --author     who signs the statement (default: the account running the script, marked "(chat)")
    --date       the day that signs it (default: today)

Canonical evidence, picked up without being named, when the default scan is on:

    report.csv                  additional technical data (a CSV without answer columns is read as
                                reference data, not as answers)
    reviews/<report>_answers.md  an earlier report with the answers written between the lines
    reviews/intent-comments-*.md  statements typed by the requester with --comment

The JSON object has these keys:

    doc                {"path", "present", "bytes", "lines", "resolved_from_archive"}
                       intent.md first; when the resolver already archived it, the newest
                       intent-YYYY-MM-DD-<n>.md, named in resolved_from_archive
    inputs[]           {"path", "type", "bytes", "lines", "sha256", "used", "reason"}
    excluded[]         files that were refused, with the reason (answer keys, binaries)
    missing[]          files the user named that do not exist -> blocking review input
    annotations[]      answers written inside a previous review: {"finding_id", "line", "answer",
                       "author", "date", "source", "syntax"}
    answers[]          annotations + CSV rows, merged, one entry per answer, each with
                       "signed": true only when it carries both an author and a date
    conflicts[]        same finding answered twice, by different signers, with different text
    orphans[]          annotations that name no finding (free commentary)
    unattributed[]     answers with no author and no date: read them, never let them decide
    injection_suspects[]  lines in an input that try to give the reviewer orders
    previous_reviews[] paths of earlier reports of this document found in reviews/
    manual_statements[]  statements of this run and of the comments file: {"finding_id", "statement",
                       "author", "date", "recorded", "in_baseline", ...}
    comments_file      the reviews/intent-comments-YYYY-MM-DD.md the statements were written to

Exit code 0 whenever the manifest could be built (including when files are missing: read
`missing` and `blocking`), 2 only for a usage error.

Annotation syntax, applied to a previous report the author annotated (single line each):

    <!-- answer: the export is nightly, not real time -->
    <!-- answer by Product on 2026-11-16: nightly batch, 02:00 UTC -->
    <!-- INT-07 answer: nightly batch -->
    > **Answer:** nightly batch, 02:00 UTC

A bare `<!-- answer: ... -->` attaches to the nearest `### INT-nn` heading above it. An annotation
that carries its own `INT-nn` wins over the heading. Anything else is an orphan: commentary the
reviewer may read but must not attribute to a question.

A manual statement is one line of `reviews/intent-comments-YYYY-MM-DD.md`:

    - **INT-01** | approval not required | ccervantes (chat) | 2026-11-17

Left to right: the finding it decides, the statement itself, who said it, and when. A statement may
contain a pipe - the signature is always the last two fields. The file is an input of its own, so a
statement recorded today is still read on the next run, and it is what the report cites as its
source. Statements carry an author and a date by construction, which is what makes them able to
close a finding; `--comment` with no id is refused and reported in `manual_statements`.

CSV sheets are read when they have an id column (`finding_id`, `question_id`, `id`, `issue`) and an
answer column (`answer`, `comment`, `response`, `resolution`, `reply`, `comentario`, `respuesta`);
`author`/`by` and `date`/`fecha` are used when present.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".csv", ".json", ".yaml", ".yml"}
PREVIOUS_RE = re.compile(
    r"^(?:intent|spec)-\d{4}-\d{2}-\d{2}\.(?:findings|issues)-Iteration_\d+\.md$"
)
# The author answers a report by copying it next to itself with this suffix and writing between the
# lines: reviews/<report>_answers.md. That file is the review's evidence, not a new report.
ANNOTATED_RE = re.compile(
    r"^(?:intent|spec)-\d{4}-\d{2}-\d{2}\.(?:findings|issues)-Iteration_\d+_answers\.md$"
)
# A statement typed in the chat is written here, one line per statement, and cited by the report.
MANUAL_FILE_RE = re.compile(r"^intent-comments-\d{4}-\d{2}-\d{2}\.md$")
MANUAL_LINE = re.compile(r"^-\s+\*\*(?P<id>INT-\d+)\*\*\s*\|(?P<rest>.*)$")
# INT-1, int1, I-1 and B01 (the block a finding sits in) are the same finding: people type the block.
STATEMENT_ID = re.compile(r"\b(?:int|b)[-_ ]?(\d{1,3})\b", re.I)
COMMENT_PREAMBLE = (
    "# Manual statements for intent.md\n\n"
    "Typed by the requester with `--comment`: one line per statement, "
    "`- **INT-nn** | statement | author | date`.\n\n"
)
REPORT_SHAPE = re.compile(r"^(?:###\s+(?:INT|SPEC)-\d+|##\s*\d*\.?\s*(?:Verdict|Veredicto)|\*\*Verdict:\*\*)", re.M)
FINDING_HEAD = re.compile(r"^###\s+((?:INT|SPEC)-\d+)\b")
SECTION_HEAD = re.compile(r"^##\s")
ANNOTATION = re.compile(
    r"<!--\s*(?:(?P<id>(?:INT|SPEC)-\d+)\s+)?(?:answer|respuesta)\b"
    r"(?:\s+(?:by|por)\s+(?P<author>[^,;:<>]+?))?"
    r"(?:\s+(?:on|el)\s+(?P<date>\d{4}-\d{2}-\d{2}))?"
    r"\s*[:\-]\s*(?P<text>.*?)\s*-->",
    re.I,
)
VISIBLE = re.compile(
    r"^\s*>\s*\*\*(?:answer|respuesta)(?:\s*\((?P<meta>[^)]*)\))?\s*:?\*\*\s*:?\s*(?P<text>.+)$",
    re.I,
)
INJECTION = re.compile(
    r"ignore (?:all |any )?(?:previous|prior|above)|you are now|system prompt|"
    r"do not report|no findings|mark (?:this|it) (?:as )?pass|disregard your|"
    r"ignora (?:las|tus) (?:reglas|instrucciones)|no reportes|marca(?:rlo)? como pass",
    re.I,
)
ID_COLUMNS = ("finding_id", "question_id", "issue_id", "issue", "id", "int")
ANSWER_COLUMNS = ("answer", "comment", "response", "resolution", "reply", "comentario", "respuesta")
AUTHOR_COLUMNS = ("author", "by", "who", "reviewer", "autor")
DATE_COLUMNS = ("date", "fecha", "when", "timestamp")


def read_text(path: Path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:12]


def classify(path: Path, text: str):
    """Return (type, used, reason)."""
    name = path.name
    if name.upper().startswith("RUBRIC"):
        return "answer-key", False, "answer key (RUBRIC_*): never given to a reviewer"
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return "binary", False, f"{path.suffix or 'no'} suffix: not a text file a reviewer can quote"
    head = "\n".join(text.splitlines()[:40]).lower()
    if "answer key" in head or "clave de respuestas" in head:
        return "answer-key", False, "says it is an answer key: never given to a reviewer"
    if ANNOTATED_RE.match(name):
        return "annotated-review", True, "earlier report with the answers written between the lines"
    if PREVIOUS_RE.match(name):
        return "previous-review", True, "earlier report of this review"
    if MANUAL_FILE_RE.match(name):
        return "manual-statements", True, "statements typed by the requester, signed and dated"
    if REPORT_SHAPE.search(text):
        return "report-example", True, "example of the report shape"
    if path.suffix.lower() == ".csv":
        return "answers-csv", True, "answer sheet"
    return "notes", True, "supporting notes"


def parse_csv(path: Path, text: str):
    """Return (answers, reason). answers = [{"finding_id", "answer", "author", "date", "line"}]."""
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return [], "empty file"
    header = [c.strip().lower() for c in rows[0]]
    id_col = next((header.index(c) for c in ID_COLUMNS if c in header), None)
    ans_col = next((header.index(c) for c in ANSWER_COLUMNS if c in header), None)
    author_col = date_col = None
    headerless = False
    if id_col is None or ans_col is None:
        # A sheet without a header is common: assume id, answer[, author[, date]].
        looks_positional = sum(
            1 for row in rows if row and re.match(r"^\s*(?:INT|SPEC)-\d+\b", row[0], re.I)
        )
        if looks_positional * 2 < len(rows):
            return [], "no id column and answer column, and the rows are not id-first"
        headerless = True
        id_col, ans_col = 0, 1
    if headerless:
        author_col, date_col = 2, 3
    else:
        author_col = next((header.index(c) for c in AUTHOR_COLUMNS if c in header), None)
        date_col = next((header.index(c) for c in DATE_COLUMNS if c in header), None)

    def cell(row, i):
        return row[i].strip() if i is not None and i < len(row) else ""

    answers = []
    for offset, row in enumerate(rows if headerless else rows[1:], start=1 if headerless else 2):
        fid = re.search(r"\b((?:INT|SPEC)-\d+)\b", cell(row, id_col).upper())
        body = cell(row, ans_col)
        if not fid or not body:
            continue
        answers.append(
            {
                "finding_id": fid.group(1),
                "answer": body,
                "author": cell(row, author_col) or None,
                "date": cell(row, date_col) or None,
                "line": offset,
            }
        )
    how = "headerless id,answer[,author[,date]]" if headerless else "with header"
    return answers, f"{len(answers)} answer rows ({how})"


def logical_lines(text: str):
    """Yield (line_number, line), joining an HTML comment that spans lines into one entry.

    An answer is often longer than the comment the author started, and a wrapped comment is still one
    answer: read it as one line, remember where it started, and never lose the rest of it.
    """
    pending, start = None, 0
    for i, line in enumerate(text.splitlines(), 1):
        if pending is not None:
            pending.append(line)
            if "-->" in line:
                yield start, " ".join(pending)
                pending = None
            continue
        if "<!--" in line and "-->" not in line:
            pending, start = [line], i
            continue
        yield i, line
    if pending is not None:
        yield start, " ".join(pending)


def parse_annotations(path: Path, text: str):
    """Return (annotations, orphans)."""
    annotations, orphans = [], []
    current = None
    for i, line in logical_lines(text):
        head = FINDING_HEAD.match(line)
        if head:
            current = head.group(1)
            continue
        if SECTION_HEAD.match(line):
            current = None
        m = ANNOTATION.search(line)
        meta, gd = None, {}
        if m:
            body = m.group("text")
            gd = m.groupdict()
        else:
            m = VISIBLE.match(line)
            if not m:
                continue
            body = m.group("text")
            meta = m.group("meta")
            gd = m.groupdict()
        author, date = gd.get("author"), gd.get("date")
        if meta:
            got = re.search(r"([A-Za-z0-9 ._-]{2,40}),\s*(\d{4}-\d{2}-\d{2})", meta)
            if got:
                author, date = author or got.group(1).strip(), date or got.group(2)
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue
        if not (author and date):
            # "…, Finance, 2026-11-16": the author signs the comment at its end.
            tail = re.search(r"(?:^|[.,;:]\s*)([A-Z][\w.'-]*(?: [A-Z][\w.'-]*)?),\s*(\d{4}-\d{2}-\d{2})\s*$", body)
            if tail:
                author = author or tail.group(1)
                date = date or tail.group(2)
                cut = body[: tail.start()]
                separator = body[tail.start(): tail.start() + 1]  # the regex consumes the punctuation
                if separator in ".,;:":
                    cut += separator
                body = cut.strip() or body
        record = {
            "finding_id": gd.get("id") or current,
            "line": i,
            "answer": body,
            "author": author.strip() if author else None,
            "date": date,
            "source": path.name,
            "syntax": "html-comment" if ANNOTATION.search(line) else "blockquote",
        }
        (annotations if record["finding_id"] else orphans).append(record)
    return annotations, orphans


# A report does not only find defects: each finding asks its question and names who must close it.
# Reading those questions back is what lets this cycle say which ones the answers actually close.
# Two forms exist and both are read: `**Question to the author**` on its own line (what the template
# asks for) and `**Question to the author:** the question` (the older one-line field, colon inside the
# bold markers). Missing the second form silently drops every question of an older report.
QUESTION_FIELD = re.compile(r"^\*\*Question to the author:?\*\*\s*:?\s*(?P<inline>.*)$")
FIELD_LINE = re.compile(r"^\*\*[A-Za-z][^*]*\*\*")
CLOSE_FIELD = re.compile(r"^\*\*Close by:?\*\*\s*(.+)$")
SEVERITY_FIELD = re.compile(r"\*\*Severity:\*\*\s*([A-Za-z]+)")
RULE_LINE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
HEADING = re.compile(r"^#{1,6}\s")
LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
STOPWORDS = frozenset(
    """
    a an and are as at be been before by can could did do does for from has have how if in into is it
    its may must no not of on or should so than that the their them then there these they this those to
    was were what when where which who why will with within without would you your question answer
    author date close decide decided value number
    """.split()
)


def distinctive(text: str) -> set:
    """The words that make two sentences talk about the same thing."""
    words = re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS and not w.isdigit()}


def parse_manual(path: Path, text: str):
    """Read `- **INT-nn** | statement | author | date` lines back into answers."""
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        found = MANUAL_LINE.match(line.strip())
        if not found:
            continue
        parts = [part.strip() for part in found.group("rest").split("|")]
        if len(parts) < 3:
            continue
        # The statement itself may contain a pipe: the signature is the last two fields.
        statement = " | ".join(parts[:-2]).strip()
        author, when = parts[-2], parts[-1]
        if not statement:
            continue
        out.append(
            {
                "finding_id": found.group("id"),
                "line": number,
                "answer": statement,
                "author": author or None,
                "date": when if re.fullmatch(r"\d{4}-\d{2}-\d{2}", when) else None,
                "source": path.name,
                "syntax": "manual",
            }
        )
    return out


def split_statement(raw: str):
    """`B01 approval no required` -> ("INT-01", "approval no required")."""
    found = STATEMENT_ID.search(raw)
    if not found:
        return None, raw.strip()
    finding_id = f"INT-{int(found.group(1)):02d}"
    statement = (raw[: found.start()] + raw[found.end() :]).strip(" \t:-,;")
    return finding_id, statement


def parse_open_questions(path: Path, text: str):
    """Return the questions a report left open: [{finding_id, question, line, severity, close_by}]."""
    found, closes = [], {}
    current, severity, collecting, block, start = None, None, False, [], 0
    lines = logical_lines(text)

    def flush():
        if current and block:
            found.append((current, start, list(block), severity))

    for i, line in lines:
        # A report may write the fields in a list, and a bullet between the bold markers and the text
        # hides the field from every pattern below: strip the marker before matching, never after.
        bare = LIST_MARKER.sub("", line, count=1)
        if ANNOTATION.search(line) or VISIBLE.match(line):
            # An answer written inside the question block is not part of the question.
            collecting = False
            continue
        head = FINDING_HEAD.match(bare)
        if head:
            flush()
            current, severity, collecting, block = head.group(1), None, False, []
            continue
        if SECTION_HEAD.match(line):
            flush()
            current, collecting, block = None, False, []
            continue
        close = CLOSE_FIELD.match(bare)
        if close:
            if current:
                closes[current] = close.group(1).strip()
            collecting = False
            continue
        if current and severity is None:
            sev = SEVERITY_FIELD.search(line)
            if sev:
                severity = sev.group(1)
        asked = QUESTION_FIELD.match(bare)
        if asked:
            collecting, start, block = True, i, []
            if asked.group("inline").strip():
                block.append(asked.group("inline").strip())
            continue
        if collecting:
            if FIELD_LINE.match(bare) or RULE_LINE.match(bare) or HEADING.match(bare):
                collecting = False
                continue
            if line.strip():
                block.append(line.strip())
    flush()
    return [
        {
            "finding_id": fid,
            "line": line,
            "severity": sev,
            "question": re.sub(r"\s+", " ", " ".join(lines)).strip(),
            "close_by": closes.get(fid),
        }
        for fid, line, lines, sev in found
        if " ".join(lines).strip()
    ]


def subject_match(text: str, questions):
    """Return (finding_id, score) when exactly one question is the one this comment answers.

    An answer written outside a finding block carries no id, so the only link left is the subject.
    The script proposes and the reviewer confirms: two questions that fit equally well means the
    comment is not attributed at all, never attributed to the first one that matched.
    """
    if not questions:
        return None
    asked = distinctive(text)
    if len(asked) < 2:
        return None
    scored = sorted(
        ((len(asked & distinctive(q["question"])), q["finding_id"]) for q in questions), reverse=True
    )
    best, fid = scored[0]
    if best < 2 or (len(scored) > 1 and scored[1][0] == best):
        return None
    return fid, best


HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def outline(text: str) -> list[dict]:
    """Every heading with the line range it owns. The map a reader needs before it reads."""
    lines = text.splitlines()
    marks: list[tuple[int, int, str]] = []
    fenced = False
    for n, line in enumerate(lines, 1):
        bare = line.lstrip()
        if bare.startswith("```") or bare.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = HEADING.match(line)
        if m:
            marks.append((n, len(m.group(1)), m.group(2).strip()))
    out: list[dict] = []
    for k, (n, level, title) in enumerate(marks):
        end = marks[k + 1][0] - 1 if k + 1 < len(marks) else len(lines)
        out.append({"line": n, "to": end, "level": level, "title": title})
    return out


def read_plan(sections: list[dict], total: int = 0, budget: int = 150) -> list[dict]:
    """Windows of at most `budget` lines: neighbour sections are merged, a long one is cut."""
    plan: list[dict] = []
    if not sections:
        sections = [{"line": 1, "to": total, "title": "(no headings)"}] if total else []
    cur_start = cur_end = None
    cur_title = ""
    for sec in sections:
        start, end = sec["line"], sec["to"]
        while start <= end:
            chunk_end = min(end, start + budget - 1)
            if cur_start is None:
                cur_start, cur_end, cur_title = start, chunk_end, sec["title"]
            elif chunk_end - cur_start + 1 <= budget:
                cur_end = chunk_end
            else:
                plan.append({"lines": f"{cur_start}-{cur_end}", "title": cur_title})
                cur_start, cur_end, cur_title = start, chunk_end, sec["title"]
            start = chunk_end + 1
    if cur_start is not None:
        plan.append({"lines": f"{cur_start}-{cur_end}", "title": cur_title})
    return plan


def main(argv):
    root = Path.cwd()
    doc_rel = "intent.md"
    scan_dirs: list[str] = []
    scan = True
    outline_only = False
    window = None
    with_previous = False
    given: list[str] = []
    comments: list[str] = []
    author = f"{os.environ.get('USER') or 'requester'} (chat)"
    day = date.today().isoformat()
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in ("--root", "--doc", "--scan-dir", "--input", "--window", "--comment", "--author", "--date"):
            if i + 1 >= len(argv):
                print(f"FAIL {arg} needs a value", file=sys.stderr)
                return 2
            value = argv[i + 1]
            if arg == "--root":
                root = Path(value).expanduser()
            elif arg == "--doc":
                doc_rel = value
            elif arg == "--scan-dir":
                scan_dirs.append(value)
            elif arg == "--comment":
                # A shell drops the quotes the user typed: `--comment B01 approval not required`
                # arrives as five arguments. Keep the plain words, stop at the next flag or path.
                while (
                    i + 2 < len(argv)
                    and not argv[i + 2].startswith("-")
                    and "." not in argv[i + 2]
                    and "/" not in argv[i + 2]
                ):
                    value += " " + argv[i + 2]
                    i += 1
                comments.append(value)
            elif arg == "--author":
                author = value
            elif arg == "--date":
                day = value
            elif arg == "--window":
                window = value
            else:
                given.append(value)
            i += 2
            continue
        if arg == "--no-scan":
            scan = False
            i += 1
            continue
        if arg == "--with-previous":
            with_previous = True
            i += 1
            continue
        if arg == "--outline":
            outline_only = True
            i += 1
            continue
        if arg in ("-h", "--help"):
            print(__doc__)
            return 0
        given.append(arg)
        i += 1

    def resolve(value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (root / path)

    def add(paths):
        for p in paths:
            if p.is_file() and all(p.resolve() != c.resolve() for c in candidates):
                candidates.append(p)

    candidates = [resolve(p) for p in given]

    # A statement typed in the chat is evidence too. Record it before anything is read, then let the
    # normal path pick it up: the file is the citation, the citation is what closes a finding.
    manual_path = None
    manual_notes: list[dict] = []
    if comments:
        reviews_dir = root / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        manual_path = reviews_dir / f"intent-comments-{day}.md"
        existing = read_text(manual_path) or ""
        body = existing if existing else COMMENT_PREAMBLE
        added = []
        for raw in comments:
            finding_id, statement = split_statement(raw)
            if not finding_id or not statement:
                manual_notes.append(
                    {
                        "finding_id": None,
                        "statement": raw.strip(),
                        "author": author,
                        "date": day,
                        "source": None,
                        "line": None,
                        "recorded": False,
                        "reason": 'a statement needs an id and a text: --comment "B01 <what decides it>"',
                    }
                )
                continue
            line = f"- **{finding_id}** | {statement} | {author} | {day}"
            if line not in body and line not in added:
                added.append(line)
        if added:
            manual_path.write_text(body.rstrip("\n") + "\n\n" + "\n".join(added) + "\n", encoding="utf-8")
        if manual_path.is_file():
            candidates.append(manual_path)

    if scan:
        # Canonical evidence first, so a run that names nothing still reads what the author left:
        # additional technical data at report.csv, annotated reports next to the report they answer.
        add([root / "report.csv"])
        reviews = root / "reviews"
        if reviews.is_dir():
            add(sorted(p for p in reviews.rglob("*") if p.is_file() and ANNOTATED_RE.match(p.name)))
            # Statements typed in an earlier cycle stay on the record: a decision, once written down
            # and signed, is not re-asked every iteration.
            add(sorted(p for p in reviews.glob("intent-comments-*.md") if p.is_file()))
        for scan_dir in scan_dirs:
            directory = (root / scan_dir) if not Path(scan_dir).is_absolute() else Path(scan_dir)
            if directory.is_dir():
                add(sorted(p for p in directory.rglob("*") if p.is_file()))

    doc = root / doc_rel
    resolved_from = None
    if not (doc.is_file() and doc.stat().st_size > 0):
        # Step 0 of the agent archives intent.md and removes it, so the reviewed copy is the newest
        # archive. Reading it here keeps the manifest usable after the resolver has run.
        archives = [
            p for p in root.glob("*.md")
            if re.fullmatch(r"intent-\d{4}-\d{2}-\d{2}-\d+\.md", p.name) and p.stat().st_size > 0
        ]
        if archives:
            def age(p: Path):
                m = re.search(r"intent-(\d{4}-\d{2}-\d{2})-(\d+)\.md$", p.name)
                assert m is not None
                return (m.group(1), int(m.group(2)))

            doc = max(archives, key=age)
            resolved_from = doc.name
    manifest = {
        "doc": {
            "path": doc_rel if resolved_from is None else doc.name,
            "present": doc.is_file() and doc.stat().st_size > 0,
            "bytes": doc.stat().st_size if doc.is_file() else 0,
            "lines": len(doc.read_text(errors="replace").splitlines()) if doc.is_file() else 0,
            "resolved_from_archive": resolved_from,
        },
        "inputs": [],
        "excluded": [],
        "missing": [],
        "annotations": [],
        "answers": [],
        "conflicts": [],
        "orphans": [],
        "unattributed": [],
        "injection_suspects": [],
        "previous_reviews": [],
        "manual_statements": [],
        "comments_file": None,
        "baseline": None,
        "open_questions": [],
        "answer_summary": {},
        "blocking": False,
    }

    baseline = None
    reviews = root / "reviews"
    if reviews.is_dir():
        def iteration_of(path: Path) -> int:
            found = re.search(r"Iteration_(\d+)", path.name)
            return int(found.group(1)) if found else 0

        # Two reports are never a baseline: an annotated report is an input of its own (its name also
        # matches the report pattern), and the report of the iteration under review already exists when
        # a previous run was abandoned - a delta against itself would close every finding.
        current = 0
        match = re.search(r"-(\d+)\.md$", doc.name)
        if resolved_from is not None and match:
            current = int(match.group(1))
        found_reviews = sorted(
            p for p in reviews.glob("intent-*.findings-Iteration_*.md")
            if not p.name.endswith("_answers.md") and (current == 0 or iteration_of(p) < current)
        )
        manifest["previous_reviews"] = sorted(p.name for p in found_reviews)
        if found_reviews:
            # The report the answers came from: the newest one before the iteration under review.
            baseline = max(found_reviews, key=iteration_of)
            manifest["baseline"] = baseline.name
        if with_previous and found_reviews:
            # The newest report is where annotated answers are most likely to arrive.
            newest = max(found_reviews, key=iteration_of)
            if all(newest.resolve() != c.resolve() for c in candidates):
                candidates.append(newest)

    seen: dict[str, str] = {}
    for path in candidates:
        if not path.exists():
            manifest["missing"].append(str(path))
            continue
        text = read_text(path)
        if text is None:
            manifest["missing"].append(str(path))
            continue
        fingerprint = digest(text)
        if fingerprint in seen:
            manifest["inputs"].append(
                {
                    "path": str(path),
                    "type": "duplicate",
                    "bytes": len(text.encode("utf-8", "replace")),
                    "lines": len(text.splitlines()),
                    "sha256": fingerprint,
                    "used": False,
                    "reason": f"same content as {seen[fingerprint]}",
                }
            )
            continue
        seen[fingerprint] = path.name
        kind, used, reason = classify(path, text)
        entry = {
            "path": str(path),
            "type": kind,
            "bytes": len(text.encode("utf-8", "replace")),
            "lines": len(text.splitlines()),
            "sha256": digest(text),
            "used": used,
            "reason": reason,
        }
        manifest["inputs"].append(entry)
        if not used:
            manifest["excluded"].append({"path": str(path), "reason": reason})
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if INJECTION.search(line):
                manifest["injection_suspects"].append(
                    {"path": path.name, "line": number, "text": line.strip()[:160]}
                )
        if kind == "manual-statements":
            rows = parse_manual(path, text)
            entry["reason"] = f"{len(rows)} statement(s) typed by the requester"
            manifest["answers"] += rows
        elif kind == "answers-csv":
            rows, why = parse_csv(path, text)
            if rows:
                entry["reason"] = why
                for row in rows:
                    manifest["answers"].append({**row, "source": path.name, "syntax": "csv"})
            else:
                # A CSV that answers nothing is additional technical data: read, quotable, and part
                # of the analysis, but it cannot withdraw a finding on its own.
                entry["type"] = "data"
                entry["reason"] = f"reference data, no answer rows ({why})"
        else:
            annotations, orphans = parse_annotations(path, text)
            manifest["annotations"] += annotations
            manifest["answers"] += annotations
            manifest["orphans"] += orphans

    by_id: dict[str, list] = {}
    for answer in manifest["answers"]:
        by_id.setdefault(answer["finding_id"], []).append(answer)
    for fid, group in sorted(by_id.items()):
        # Only a signed answer may settle a question: no author and no date means commentary.
        signed = [a for a in group if a.get("author") or a.get("date")]
        for answer in group:
            answer["signed"] = bool(answer.get("author") and answer.get("date"))
            if not (answer.get("author") or answer.get("date")):
                manifest["unattributed"].append(answer)
        distinct = {re.sub(r"\W+", " ", a["answer"].lower()).strip() for a in signed}
        if len(distinct) > 1:
            unique, texts = [], set()
            for a in signed:
                key = re.sub(r"\W+", " ", a["answer"].lower()).strip()
                if key in texts:
                    continue
                texts.add(key)
                unique.append({"answer": a["answer"], "source": a["source"], "line": a["line"]})
            manifest["conflicts"].append({"finding_id": fid, "answers": unique})

    # What the previous cycle asked, and what these files actually answer: every open question of
    # the baseline report is paired with the answers found for it, by id or by subject.
    source = baseline
    if source is None:
        annotated = [i["path"] for i in manifest["inputs"] if i["type"] == "annotated-review"]
        source = Path(annotated[0]) if annotated else None
    text_of_source = read_text(source) if source is not None else None
    questions = (
        parse_open_questions(source, text_of_source)  # type: ignore[arg-type]
        if source is not None and text_of_source
        else []
    )
    buckets = {q["finding_id"]: [] for q in questions}

    for answer in manifest["answers"]:
        fid = answer.get("finding_id")
        if fid in buckets:
            # A statement typed in the chat names its finding outright: no subject guesswork.
            kind = "manual" if answer.get("syntax") == "manual" else "id"
            buckets[fid].append({**answer, "matched_by": kind})
    for orphan in manifest["orphans"]:
        got = subject_match(orphan["answer"], questions)
        if got:
            fid, score = got
            orphan["subject_match"] = {"finding_id": fid, "score": score}
            buckets[fid].append({**orphan, "matched_by": "subject", "score": score})

    summary = {"questions": len(questions), "answered": 0, "unattributed": 0, "still_open": 0}
    for question in questions:
        candidates = buckets[question["finding_id"]]
        signed = [a for a in candidates if a.get("author") and a.get("date")]
        question["answers"] = [
            {
                "answer": a["answer"],
                "author": a.get("author"),
                "date": a.get("date"),
                "source": a.get("source"),
                "line": a.get("line"),
                "matched_by": a["matched_by"],
                "signed": bool(a.get("author") and a.get("date")),
            }
            for a in candidates
        ]
        if signed:
            question["status"] = "answered"
            question["answered_by"] = {"source": signed[0]["source"], "line": signed[0]["line"]}
        elif candidates:
            question["status"] = "unattributed"
        else:
            question["status"] = "still_open"
        summary[question["status"]] += 1

    manifest["open_questions"] = questions
    manifest["answer_summary"] = summary

    if manual_path is not None and manual_path.is_file():
        try:
            manifest["comments_file"] = str(manual_path.relative_to(root))
        except ValueError:
            manifest["comments_file"] = str(manual_path)
        wanted = {q["finding_id"] for q in questions}
        recorded = parse_manual(manual_path, read_text(manual_path) or "")
        for entry_out in recorded:
            entry_out["recorded"] = True
            # One shape for both origins: a recorded line and a refused statement carry `statement`.
            entry_out["statement"] = entry_out["answer"]
            # A statement may also decide a finding this cycle opened: absent from the baseline is
            # not an error, it only means the id is new.
            entry_out["in_baseline"] = entry_out["finding_id"] in wanted
        manifest["manual_statements"] = recorded + manual_notes

    manifest["blocking"] = bool(manifest["missing"])
    if window is not None:
        # One window is one tool result of at most ~10 KB. This is the only safe way to read a long
        # document in a chat that has a request-size ceiling.
        text = read_text(doc) if doc.is_file() else ""
        lines = text.splitlines()
        plan = read_plan(outline(text), len(lines))
        try:
            n = int(window)
        except ValueError:
            n = 0
        if not plan or not (1 <= n <= len(plan)):
            print(f"FAIL --window {window} but the document has {len(plan)} windows", file=sys.stderr)
            return 2
        a, b = (int(x) for x in plan[n - 1]["lines"].split("-"))
        body = "\n".join(f"{i}\t{lines[i - 1]}" for i in range(a, min(b, len(lines)) + 1))
        print(json.dumps({"doc": manifest["doc"], "window": n, "of": len(plan),
                          "lines": plan[n - 1]["lines"], "title": plan[n - 1]["title"],
                          "text": body}, indent=2, ensure_ascii=False))
        return 0
    if outline_only:
        # A 600-line document read whole is one tool result of forty kilobytes, and the next model
        # request is the one that never answers. The map costs two and buys the window.
        text = read_text(doc) if doc.is_file() else ""
        sections = outline(text)
        print(json.dumps({"doc": manifest["doc"], "outline": sections,
                          "read_plan": read_plan(sections, len(text.splitlines())), "how": "read_file startLine/endLine per window"},
                         indent=2, ensure_ascii=False))
        return 0
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

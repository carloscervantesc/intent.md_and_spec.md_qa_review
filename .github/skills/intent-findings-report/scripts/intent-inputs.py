#!/usr/bin/env python3
"""Build the evidence manifest for an intent review.

A review of `intent.md` often arrives with extra material: an earlier report of ours that the
author annotated between the lines, a filled-in answer sheet, an example of the report shape they
want. This script reads those files and turns them into one JSON object the agent can act on, so
the reviewer never has to guess which comment belongs to which question.

Usage
    python3 intent-inputs.py [--root DIR] [--doc intent.md] [--with-previous]
                             [--no-scan] [--scan-dir DIR] [--input PATH]...

    --root       workspace root (default: current directory)
    --doc        the reviewed document, relative to --root (default: intent.md)
    --input      a file the user named; any number, in any order
    --with-previous  also read the newest report in reviews/
    --scan-dir   an extra folder to read as well (repeatable by calling the flag again)
    --no-scan    read only what --input names

Canonical evidence, picked up without being named, when the default scan is on:

    report.csv                  additional technical data (a CSV without answer columns is read as
                                reference data, not as answers)
    reviews/<report>_answers.md  an earlier report with the answers written between the lines

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

CSV sheets are read when they have an id column (`finding_id`, `question_id`, `id`, `issue`) and an
answer column (`answer`, `comment`, `response`, `resolution`, `reply`, `comentario`, `respuesta`);
`author`/`by` and `date`/`fecha` are used when present.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
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


def parse_annotations(path: Path, text: str):
    """Return (annotations, orphans)."""
    annotations, orphans = [], []
    current = None
    for i, line in enumerate(text.splitlines(), 1):
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


def main(argv):
    root = Path.cwd()
    doc_rel = "intent.md"
    scan_dirs: list[str] = []
    scan = True
    with_previous = False
    given: list[str] = []
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in ("--root", "--doc", "--scan-dir", "--input"):
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
    if scan:
        # Canonical evidence first, so a run that names nothing still reads what the author left:
        # additional technical data at report.csv, annotated reports next to the report they answer.
        add([root / "report.csv"])
        reviews = root / "reviews"
        if reviews.is_dir():
            add(sorted(p for p in reviews.rglob("*") if p.is_file() and ANNOTATED_RE.match(p.name)))
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
        "blocking": False,
    }

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
        if kind == "answers-csv":
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

    manifest["blocking"] = bool(manifest["missing"])
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

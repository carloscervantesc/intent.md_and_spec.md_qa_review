#!/usr/bin/env python3
"""Resolve the iteration of the intent under review, and archive the file that was reviewed.

The intent being reviewed always lives at `intent.md` in the workspace root. Every reviewed
version is archived next to it as `intent-YYYY-MM-DD-<n>.md`, so the iteration number is a
property of the file, not of the report: iteration `n` is exactly `intent-YYYY-MM-DD-n.md`, and
the report for it is `reviews/intent-YYYY-MM-DD.findings-Iteration_<n>.md`.

Three states, and only one of them allows a review:

    MISSING      no intent.md                          -> blocking, nothing to review
    INTERRUPTED  intent.md is missing because the last run archived it and never wrote that
                 archive's report (the client dropped the answer mid-review)
                                                     -> review that archive, nothing renamed
    UNCHANGED  intent.md is byte-identical (modulo trailing whitespace) to the last archive
                                                       -> blocking, the author changed nothing
    NEW        intent.md differs from the last archive -> archived as iteration n, review starts
    AMEND      intent.md is missing because the run that reviewed it finished, archived it and wrote
               its report, and a `--comment` now has to decide findings in that report
                                                     -> `review: false`; the report named in `report`
                                                        already exists and is edited **in place**.
                                                        Nothing is reviewed again, nothing is copied
                                                        or renamed, no number is spent. `amend: true`
                                                        and `amend_statements` list the statements the
                                                        report does not cite yet

`--force` turns `UNCHANGED` into a `NEW` run: the identical file is archived as the next iteration
and reviewed again in full. It is an explicit human decision, never a default, because a second
review of identical text produces an identical report - `--force` buys a fresh report on purpose
(a re-read after a checklist change, a second reviewer, a documented re-confirmation), not progress.
It cannot invent a file: `MISSING` stays blocking even with `--force`.

`AMEND` is the whole point of `reviews/.last-processed.json`: a `--comment` is a manual correction
of a review *result*, so it lands in the review file - never in `intent.md`, which by then does not
exist. The record says which document this workspace processed last and which report scored it. Only
reports that exist can be amended: a finished run whose report is missing is `INTERRUPTED`, and an
archived document with nothing owed is plain `MISSING`.

Usage
    python3 intent-iteration.py [--root DIR] [--date YYYY-MM-DD] [--dry-run] [--force] [--last]

Output: one JSON object on stdout, including `report` - the exact path the report must be written
to. Exit 0 for the three states, 2 for a usage error, so the agent can branch on
`"review": true|false` instead of on an exit code.

The number is never reused: it is one more than every iteration already visible in the workspace
(archives `intent-*.md` and reports `reviews/intent-*.findings-Iteration_*.md`). An existing report
is therefore never overwritten, not even when the resolver is pointed at the wrong directory.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

INTENT = "intent.md"
ARCHIVE_RE = re.compile(r"^intent-(\d{4}-\d{2}-\d{2})-(\d+)\.md$")
REPORT_RE = re.compile(r"^intent-(\d{4}-\d{2}-\d{2})\.findings-Iteration_(\d+)\.md$")
# The last document this workspace processed: derived state, and the only memory of which archive
# to amend once the working file no longer exists.
RECORD = ".last-processed.json"


def canon(path: Path) -> str:
    """Content as compared for 'the author changed something': trailing whitespace and the
    number of blank lines at the end do not count as a change."""
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    return "\n".join(line.rstrip() for line in text.splitlines()).strip("\n")


def sha256_of(path: Path) -> str:
    """Content hash of a file, so the record can be checked against the archive it names."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_record(reviews: Path):
    """The last processed document, or None. A missing or corrupt record is not an error: every
    caller falls back to the newest archive."""
    try:
        return json.loads((reviews / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


COMMENT_LINE_RE = re.compile(
    r"^\s*-\s*\*\*(?P<ident>[^*|]+?)\*\*\s*\|\s*(?P<statement>.+?)\s*\|\s*"
    r"(?P<who>[^|]+?)\s*\|\s*(?P<day>\d{4}-\d{2}-\d{2})\s*$"
)
CITED_RE = re.compile(
    r"(?:spec|intent)-comments-[0-9]{4}-[0-9]{2}-[0-9]{2}\.md\s*\(l\.(\d+)\)"
)


def pending_statements(report: Path) -> list:
    """Manual statements sitting next to a report that the report does not cite yet.

    A --comment is a correction of the review *result*, so the review file is where it lands: this
    is what tells an AMEND apart from a MISSING - there is a report, and it owes an answer.
    """
    if not report.exists():
        return []
    body = report.read_text(encoding="utf-8", errors="replace")
    cited = {int(n) for n in CITED_RE.findall(body)}
    # A statement counts as applied when the report quotes it, not only when it names the exact line:
    # the same sentence answered twice, or a statement whose line moved because the file grew, must not
    # reopen an amend that already happened.
    said = " ".join(body.split()).lower()
    out = []
    for path in sorted(report.parent.glob("*comments-*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            found = COMMENT_LINE_RE.match(line)
            if not found:
                continue
            quote = " ".join(found.group("statement").split()).lower()
            if number in cited or (len(quote) >= 20 and quote in said):
                continue
            out.append({
                "file": str(path),
                "line": number,
                "ident": found.group("ident").strip(),
                "statement": found.group("statement").strip(),
                "author": found.group("who").strip(),
                "date": found.group("day"),
            })
    return out


def relative(path, root: Path) -> str:
    """Paths in the record are relative to the workspace when they live inside it."""
    p = Path(path)
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def remember(result: dict, reviews: Path, root: Path, dry_run: bool) -> None:
    """Record the document this run processed, so a later --comment can still be applied to it."""
    if dry_run or not result.get("review") or not result.get("archive"):
        return
    archive = Path(result["archive"])
    if not archive.exists():
        return
    record = {
        "schema": 1,
        "doc": archive.name,
        "date": result.get("date"),
        "iteration": result.get("iteration"),
        "archive": relative(archive, root),
        "report": relative(result["report"], root) if result.get("report") else None,
        "sha256": sha256_of(archive),
        "state": result.get("state"),
        "amend": bool(result.get("amend")),
        "updated": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    result["last_processed"] = record
    reviews.mkdir(parents=True, exist_ok=True)
    (reviews / RECORD).write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--root", default=".", help="workspace root (default: current directory)")
    ap.add_argument("--date", default=None, help="archive date, YYYY-MM-DD (default: today, local)")
    ap.add_argument("--dry-run", action="store_true", help="report what would happen, rename nothing")
    ap.add_argument(
        "--force",
        action="store_true",
        help="review an unchanged intent.md anyway: archive it as the next iteration and run the "
        "full review instead of reporting UNCHANGED",
    )
    ap.add_argument(
        "--complete",
        action="store_true",
        help="mark the record complete once the report of this iteration is on disk: without it a "
        "review whose report was written still reads as INTERRUPTED in --last",
    )
    ap.add_argument(
        "--last",
        action="store_true",
        help="print the record of the last processed document and exit",
    )
    args = ap.parse_args(argv[1:])

    root = Path(args.root).resolve()
    day = args.date or dt.date.today().strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        print(f"--date must be YYYY-MM-DD, got {day!r}", file=sys.stderr)
        return 2

    archives = []
    for p in root.glob("intent-*.md"):
        m = ARCHIVE_RE.match(p.name)
        if m:
            archives.append((int(m.group(2)), m.group(1), p))
    archives.sort()
    last_n, last_date, last_path = archives[-1] if archives else (0, None, None)

    reports = []
    reviews = root / "reviews"
    if reviews.is_dir():
        for p in reviews.glob("intent-*.md"):
            m = REPORT_RE.match(p.name)
            if m:
                reports.append(int(m.group(2)))
    # A report is a deliverable: never hand out a number that is already taken by one.
    next_n = max([last_n] + reports) + 1

    if args.complete:
        record = read_record(reviews)
        if not record:
            print(json.dumps({"completed": False, "reason": "no record to complete",
                              "path": str(reviews / RECORD)}, indent=2))
            return 1
        report = record.get("report")
        target = (root / report) if report else None
        if not target or not target.exists() or target.stat().st_size == 0:
            print(json.dumps({"completed": False,
                              "reason": "the report the record names is not on disk",
                              "report": report}, indent=2))
            return 1
        record["state"] = "DONE"
        record["report_lines"] = len(
            target.read_text(encoding="utf-8", errors="replace").splitlines()
        )
        record["report_sha256"] = sha256_of(target)
        record["updated"] = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        (reviews / RECORD).write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps({"completed": True, "record": record}, indent=2, ensure_ascii=False))
        return 0

    if args.last:
        print(json.dumps(
            {"record": read_record(reviews), "path": str(reviews / RECORD)},
            indent=2, ensure_ascii=False,
        ))
        return 0

    result = {
        "root": str(root),
        "date": day,
        "intent": str(root / INTENT),
        "intent_exists": False,
        "last_archive": str(last_path) if last_path else None,
        "last_iteration": last_n,
        "last_report_iteration": max(reports) if reports else 0,
        "iteration": next_n,
        "report": str(root / "reviews" / f"intent-{day}.findings-Iteration_{next_n}.md"),
        "archive": None,
        "review": False,
        "force": bool(args.force),
        "forced": False,
        "state": None,
        "reason": None,
        "amend": False,
        "amend_statements": [],
        "document": None,
        "last_processed": read_record(reviews),
    }

    def resume_or_block(reason: str) -> None:
        """The document is gone; was it gone *after* being archived? Then finish that review."""
        pending = reviews / f"intent-{last_date}.findings-Iteration_{last_n}.md"
        if last_path and last_date and not pending.exists():
            result.update(
                iteration=last_n,
                report=str(pending),
                archive=str(last_path),
                review=True,
                state="INTERRUPTED",
                reason=(
                    f"{INTENT} was archived as {last_path.name} and its report "
                    f"{pending.name} was never written: the previous run stopped after the rename. "
                    f"Review that archive as iteration {last_n}; do not rename anything again"
                ),
            )
            return
        record = read_record(reviews)
        # AMEND: the run before this one archived the document *and* wrote its report, so there is
        # nothing left to review. A --comment is a manual correction of that report, and the report is
        # the file it has to change - not a new copy of the document, not a new iteration, not a
        # restored intent.md. Only worth reporting when the report owes an answer to a statement it
        # does not cite yet; otherwise the run is simply MISSING.
        #
        # The report is found through the record first, and through the newest archive + the report
        # that belongs to it second, because workspaces reviewed before the record existed have no
        # .last-processed.json.
        amended = None
        if record and record.get("archive") and record.get("report"):
            where = root / record["report"]
            amended = (where, record["archive"], int(record.get("iteration") or 1)) if where.exists() else None
        if amended is None and last_path is not None and last_date:
            where = reviews / f"intent-{last_date}.findings-Iteration_{last_n}.md"
            if where.exists():
                amended = (where, last_path.name, last_n)
        if amended is not None:
            where, archive_name, it_no = amended
            # The number that matters is the report's own: inside a chain it counts from 1, while the
            # record stores the archive number the chain started at.
            named = re.search(r"Iteration_(\d+)", where.name)
            if named:
                it_no = int(named.group(1))
            owed = pending_statements(where)
            if owed:
                result.update(
                    iteration=it_no,
                    report=str(where),
                    archive=str(root / archive_name),
                    document=str(root / archive_name),
                    review=False,
                    state="AMEND",
                    amend=True,
                    amend_statements=owed,
                    reason=(
                        f"{INTENT} was already reviewed as {archive_name} and its report "
                        f"{where.name} exists: {len(owed)} manual statement(s) are not applied to it. "
                        f"Edit that report in place - the block's coverage row, the finding the "
                        f"statement decides, and an amend entry citing the line. Do not review the "
                        f"document again, do not copy or rename anything, do not spend a number"
                    ),
                )
                return
        way_out = ""
        if record and record.get("archive"):
            way_out = (
                f" -- the last processed document is {record['archive']} (state {record.get('state')}, "
                f"iteration {record.get('iteration')}): it was reviewed and archived, so there is no "
                f"submission to score; a --comment about it amends that report instead"
            )
        elif last_path is not None:
            way_out = (
                f" -- the last processed document is {last_path.name}; a --comment about it belongs in "
                f"its report, not in a restored {INTENT}"
            )
        result.update(state="MISSING", reason=reason + way_out)

    src = root / INTENT

    if not src.exists():
        resume_or_block(
            f"no {INTENT} at the workspace root; nothing to review"
            + (" (--force cannot review a file that is not there)" if args.force else "")
        )
    elif not src.read_text(encoding="utf-8", errors="replace").strip():
        resume_or_block(
            f"{INTENT} exists but is empty"
            + (" (--force cannot review an empty file)" if args.force else "")
        )
    else:
        result["intent_exists"] = src.name == INTENT
        result["document"] = str(src)
        same = bool(last_path) and canon(src) == canon(last_path)
        if same and not args.force:
            result.update(
                state="UNCHANGED",
                reason=(
                    f"{INTENT} is identical to the last archive "
                    f"{last_path.name} (iteration {last_n}); the author changed nothing"
                ),
            )
        else:
            n = next_n
            archive = root / f"intent-{day}-{n}.md"
            if same:
                reason = (
                    f"{INTENT} is identical to {last_path.name} (iteration {last_n}) and was "
                    f"archived as {archive.name} because --force was requested"
                )
            else:
                reason = (
                    f"{INTENT} differs from "
                    + (last_path.name if last_path else "nothing archived yet")
                    + f"; archived as {archive.name}"
                )
            result.update(
                state="NEW",
                iteration=n,
                report=str(root / "reviews" / f"intent-{day}.findings-Iteration_{n}.md"),
                archive=str(archive),
                review=True,
                forced=bool(same),
                reason=reason,
            )
            if not args.dry_run:
                os.replace(src, archive)
                result["renamed"] = True

    remember(result, reviews, root, args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

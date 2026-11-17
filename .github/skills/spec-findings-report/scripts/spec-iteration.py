#!/usr/bin/env python3
"""Resolve the iteration of the spec under review, and archive the file that was reviewed.

The spec being reviewed always lives at `spec.md` in the workspace root. Every reviewed version is
archived next to it as `spec-YYYY-MM-DD-<n>.md`, so the iteration number is a property of the file,
not of the report: iteration `n` is exactly `spec-YYYY-MM-DD-n.md`, and the report for it is
`reviews/spec-YYYY-MM-DD.issues-Iteration_<n>.md`.

Five states, and two of them allow a review:

    MISSING      no spec.md                            -> blocking, nothing to review
    UNCHANGED    spec.md is byte-identical (modulo trailing whitespace) to the last archive
                                                       -> blocking, the author changed nothing
    NEW          spec.md differs from the last archive -> archived as iteration n, review starts
    INTERRUPTED  spec.md is missing because the last run archived it and never wrote that
                 archive's report (the client dropped the answer mid-review)
                                                       -> review that archive as its iteration;
                                                          nothing is renamed, no number is spent
    AMEND        spec.md is missing because the run that reviewed it finished, archived it and
                 wrote its report, and a `--comment` now has to decide findings in that report
                                                       -> `review: false`; the report named in
                                                          `report` already exists and is edited
                                                          **in place**. Nothing is reviewed
                                                          again, nothing is copied or renamed,
                                                          no number is spent. `amend: true` and
                                                          `amend_statements` list the statements
                                                          the report does not cite yet

`AMEND` is the whole point of `reviews/.last-processed.json`: a `--comment` is a manual correction of
a review *result*, so it lands in the review file - never in `spec.md`, which by then does not exist.
The record says which document the workspace processed last and which report scored it. Only reports
that exist can be amended: a finished run whose report is missing is `INTERRUPTED`, and an archived
document with nothing owed is plain `MISSING`.

`--force` turns `UNCHANGED` into a `NEW` run: the identical file is archived as the next iteration and
reviewed again in full. It is an explicit human decision, never a default, because a second review of
identical text produces an identical report - `--force` buys a fresh report on purpose (a re-read after
a checklist change, a second reviewer, a documented re-confirmation), not progress. It cannot invent a
file: `MISSING` stays blocking even with `--force`.

`--new` starts a **new chain**: the `spec.md` on disk is a document about something else, not the next
draft of the one under review, so it becomes iteration 1 of its own line of work and nothing from the
previous line is read - no delta, no inherited questions, no comparison against the last archive (an
identical file is still a new chain, on purpose). Its reports live in `reviews/chain-<n>/`, where `<n>`
is the archive number the chain started at, so two chains can both have an `Iteration_1` without one
overwriting the other; the filename format inside the folder does not change. The chain in progress is
always the newest folder, and the flat `reviews/` is the first chain: work moves forward in time, it
does not jump back to an old line.

The record is written by every run that processed a document (`reviews/.last-processed.json`: the
document, its date and iteration, its archive, its report and the content hash). `--last` prints it,
which is the cheapest way to answer "what did this workspace review last?" without reading a folder.

Usage
    python3 spec-iteration.py [--root DIR] [--date YYYY-MM-DD] [--dry-run] [--force] [--new] [--last]

Output: one JSON object on stdout, including `report` - the exact path the report must be written
to. Exit 0 for every state, 2 for a usage error, so the agent can branch on
`"review": true|false` instead of on an exit code.

The number is never reused: it is one more than every iteration already visible in the workspace
(archives `spec-*.md` and reports `reviews/spec-*.issues-Iteration_*.md`, plus the reports written
under the older `reviews/spec-YYYY-MM-DD-N.issues.md` name). An existing report is therefore never
overwritten, not even when the resolver is pointed at the wrong directory.
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

SPEC = "spec.md"
ARCHIVE_RE = re.compile(r"^spec-(\d{4}-\d{2}-\d{2})-(\d+)\.md$")
REPORT_RE = re.compile(r"^spec-(\d{4}-\d{2}-\d{2})\.issues-Iteration_(\d+)\.md$")
CHAIN_RE = re.compile(r"^chain-(\d+)$")
LEGACY_REPORT_RE = re.compile(r"^spec-\d{4}-\d{2}-\d{2}-(\d+)\.issues\.md$")
# The last document this workspace processed. Derived state: it can always be rebuilt from the
# archives, but it is the only thing that remembers *which* archive the operator meant when the
# prompt no longer names a live document.
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
    """The last processed document, or None. A corrupt or missing record is not an error: it is
    derived state, and every path that reads it falls back to the newest archive."""
    try:
        return json.loads((reviews / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


COMMENT_LINE_RE = re.compile(
    r"^\s*-\s*\*\*(?P<ident>[^*|]+?)\*\*\s*\|\s*(?P<statement>.+?)\s*\|\s*"
    r"(?P<who>[^|]+?)\s*\|\s*(?P<day>\d{4}-\d{2}-\d{2})\s*$"
)
CITED_RE = re.compile(r"spec-comments-[0-9]{4}-[0-9]{2}-[0-9]{2}\.md\s*\(l\.(\d+)\)")


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
    for path in sorted(report.parent.glob("spec-comments-*.md")):
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
    """Paths in the record are relative to the workspace when they live inside it, because the
    record outlives the directory it was written in (a copied workspace, a moved clone)."""
    p = Path(path)
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def remember(result: dict, reviews: Path, root: Path, dry_run: bool) -> None:
    """Record the document this run processed, so a later --comment can still be applied to it.

    Written for every run that hands a document to the reviewer, including `INTERRUPTED` (whose
    archive is the document). A blocked run records nothing: nothing was processed."""
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
        "chain": result.get("chain"),
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
        help="review an unchanged spec.md anyway: archive it as the next iteration and run the "
        "full review instead of reporting UNCHANGED",
    )
    ap.add_argument(
        "--new",
        action="store_true",
        help="start a new chain: this spec.md is a new piece of work, so it is archived as "
        "iteration 1 of reviews/chain-<n>/ and nothing from the previous chain is read",
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
    for p in root.glob("spec-*.md"):
        m = ARCHIVE_RE.match(p.name)
        if m:
            archives.append((int(m.group(2)), m.group(1), p))
    archives.sort()
    last_n, last_date, last_path = archives[-1] if archives else (0, None, None)

    reports = []
    reviews = root / "reviews"
    if reviews.is_dir():
        for p in reviews.glob("spec-*.md"):
            m = REPORT_RE.match(p.name)
            if m:
                reports.append(int(m.group(2)))
                continue
            m = LEGACY_REPORT_RE.match(p.name)
            if m:
                reports.append(int(m.group(1)))
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

    # Chains: `reviews/chain-<n>/` holds the reports of a line of work that started at archive n.
    # The flat `reviews/` is the first chain, so an existing workspace keeps its history untouched.
    chains = []
    if reviews.is_dir():
        for p in reviews.iterdir():
            m = CHAIN_RE.match(p.name)
            if m and p.is_dir():
                chains.append(int(m.group(1)))
        chains.sort()
    active = max(chains) if chains else 0  # 0 = the flat chain, iteration == archive number

    # Where the next iteration goes, and which iteration it is *within its chain*.
    if args.new:
        chain, chain_dir, iteration = next_n, reviews / f"chain-{next_n}", 1
    elif active:
        chain, chain_dir = active, reviews / f"chain-{active}"
        iteration = next_n - chain + 1
    else:
        chain, chain_dir, iteration = 0, None, next_n
    target_dir = chain_dir or reviews
    # The last archive of *this* chain. A chain that has none yet (only possible right after --new,
    # which never compares) falls back to nothing, so no file is compared across chains.
    last_of_chain = last_path if (last_n >= chain or chain == 0) else None
    # The report the delta is read against: the newest one already written in this chain, below the
    # iteration about to start. A hint for the reviewer, never a number it has to trust.
    previous_report = None
    if chain_dir is not None and iteration > 1 and chain_dir.is_dir():
        earlier = [
            (int(m.group(2)), p)
            for p in chain_dir.glob("spec-*.issues-Iteration_*.md")
            if (m := REPORT_RE.match(p.name)) and int(m.group(2)) < iteration
        ]
        if earlier:
            previous_report = max(earlier, key=lambda pair: pair[0])[1]

    # A run can die between the rename and the report: the archive exists, its report never does.
    # Every place that report could live, newest chain last.
    def expected_reports(n: int, day_s: str):
        out = [(reviews, 0, n, reviews / f"spec-{day_s}.issues-Iteration_{n}.md")]
        for c in chains:
            if n >= c:
                out.append(
                    (reviews / f"chain-{c}", c, n - c + 1,
                     reviews / f"chain-{c}" / f"spec-{day_s}.issues-Iteration_{n - c + 1}.md")
                )
        return out

    src = root / SPEC
    live = src.exists() and bool(src.read_text(encoding="utf-8", errors="replace").strip())

    result = {
        "root": str(root),
        "date": day,
        "spec": str(src),
        "spec_exists": False,
        "last_archive": str(last_path) if last_path else None,
        "last_iteration": last_n,
        "last_report_iteration": max(reports) if reports else 0,
        "chain": chain,
        "chain_dir": str(chain_dir) if chain_dir else None,
        "chains": chains,
        "new_chain": bool(args.new),
        "previous_report": str(previous_report) if previous_report else None,
        "iteration": iteration,
        "report": str(target_dir / f"spec-{day}.issues-Iteration_{iteration}.md"),
        "archive": None,
        "review": False,
        "force": bool(args.force),
        "forced": False,
        "state": None,
        "reason": None,
        "amend": False,
        "amend_statements": [],
        "document": str(src),
        "last_processed": read_record(reviews),
    }

    def resume_or_block(reason: str) -> None:
        """The document is gone; was it gone *after* being archived? Then finish that review."""
        wanted = expected_reports(last_n, last_date) if last_path and last_date else []
        if wanted and not any(entry[3].exists() for entry in wanted):
            where, ch, it, path = wanted[-1]
            result.update(
                chain=ch,
                chain_dir=str(where) if ch else None,
                iteration=it,
                report=str(path),
                archive=str(last_path),
                review=True,
                state="INTERRUPTED",
                reason=(
                    f"{SPEC} was archived as {last_path.name} and its report "
                    f"{path.name} was never written: the previous run stopped after the rename. "
                    f"Review that archive as iteration {it}; do not rename anything again"
                ),
            )
            return
        record = read_record(reviews)
        # AMEND: the run before this one archived the document *and* wrote its report, so there is
        # nothing left to review. A --comment is a manual correction of that report, and the report is
        # the file it has to change - not a new copy of the document, not a new iteration, not a
        # restored spec.md. Only worth reporting when the report owes an answer to a statement it does
        # not cite yet; otherwise the run is simply MISSING.
        #
        # The report is found through the record first (it survives a date change and names the
        # document exactly), and through the newest archive + the report that belongs to it second,
        # because workspaces reviewed before the record existed have no .last-processed.json.
        amended = None
        if record and record.get("archive") and record.get("report"):
            where = root / record["report"]
            amended = (where, record["archive"], int(record.get("iteration") or 1)) if where.exists() else None
        if amended is None:
            wanted = expected_reports(last_n, last_date) if last_path and last_date else []
            hit = next((entry for entry in wanted if entry[3].exists()), None)
            if hit is not None and last_path is not None:
                amended = (hit[3], last_path.name, hit[2])
        if amended is not None:
            where, archive_name, it_no = amended
            # The number that matters is the report's own: inside a chain it counts from 1, while the
            # record stores the archive number the chain started at.
            named = re.search(r"Iteration_(\d+)", where.name)
            if named:
                it_no = int(named.group(1))
            owed = pending_statements(where)
            if owed:
                ch = 0
                parent = where.parent.name
                if parent.startswith("chain-") and parent[6:].isdigit():
                    ch = int(parent[6:])
                result.update(
                    chain=ch,
                    chain_dir=str(where.parent) if ch else None,
                    iteration=it_no,
                    report=str(where),
                    archive=str(root / archive_name),
                    document=str(root / archive_name),
                    review=False,
                    state="AMEND",
                    amend=True,
                    amend_statements=owed,
                    reason=(
                        f"{SPEC} was already reviewed as {archive_name} and its report "
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
            # No record yet (the first run of this workspace predates it): the newest archive is what
            # an amendment would target anyway, and saying so stops the operator from restoring a file.
            way_out = (
                f" -- the last processed document is {last_path.name}; a --comment about it belongs in "
                f"its report, not in a restored {SPEC}"
            )
        result.update(
            chain=0,
            chain_dir=None,
            new_chain=bool(args.new),
            iteration=next_n,
            report=str(reviews / f"spec-{day}.issues-Iteration_{next_n}.md"),
            state="MISSING",
            reason=reason + way_out,
        )

    if not src.exists():
        resume_or_block(
            f"no {SPEC} at the workspace root; nothing to review"
            + (" (--force cannot review a file that is not there)" if args.force else "")
        )
    elif not src.read_text(encoding="utf-8", errors="replace").strip():
        resume_or_block(
            f"{SPEC} exists but is empty"
            + (" (--force cannot review an empty file)" if args.force else "")
        )
    else:
        result["spec_exists"] = src.name == SPEC
        result["document"] = str(src)
        same = bool(last_of_chain) and canon(src) == canon(last_of_chain)
        if same and not args.force and not args.new:
            result.update(
                state="UNCHANGED",
                reason=(
                    f"{SPEC} is identical to the last archive "
                    f"{last_path.name} (iteration {last_n}); the author changed nothing"
                ),
            )
        else:
            n = next_n
            archive = root / f"spec-{day}-{n}.md"
            if args.new:
                reason = (
                    f"--new: {SPEC} starts chain {chain} as its iteration 1 and is archived as "
                    f"{archive.name}; nothing from the previous chain is read"
                )
            elif same:
                reason = (
                    f"{SPEC} is identical to {last_path.name} (iteration {last_n}) and was "
                    f"archived as {archive.name} because --force was requested"
                )
            else:
                reason = (
                    f"{SPEC} differs from "
                    + (last_of_chain.name if last_of_chain else "nothing archived yet")
                    + f"; archived as {archive.name}"
                )
            result.update(
                state="NEW",
                iteration=n if chain_dir is None else iteration,
                report=str(target_dir / f"spec-{day}.issues-Iteration_"
                          f"{n if chain_dir is None else iteration}.md"),
                archive=str(archive),
                review=True,
                forced=bool(same and not args.new),
                reason=reason,
            )
            if not args.dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
                os.replace(src, archive)
                result["renamed"] = True

    remember(result, reviews, root, args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

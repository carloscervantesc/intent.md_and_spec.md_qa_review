#!/usr/bin/env python3
"""Resolve the iteration of the spec under review, and archive the file that was reviewed.

The spec being reviewed always lives at `spec.md` in the workspace root. Every reviewed version is
archived next to it as `spec-YYYY-MM-DD-<n>.md`, so the iteration number is a property of the file,
not of the report: iteration `n` is exactly `spec-YYYY-MM-DD-n.md`, and the report for it is
`reviews/spec-YYYY-MM-DD.issues-Iteration_<n>.md`.

Three states, and only one of them allows a review:

    MISSING    no spec.md                            -> blocking, nothing to review
    UNCHANGED  spec.md is byte-identical (modulo trailing whitespace) to the last archive
                                                     -> blocking, the author changed nothing
    NEW        spec.md differs from the last archive -> archived as iteration n, review starts

`--force` turns `UNCHANGED` into a `NEW` run: the identical file is archived as the next iteration and
reviewed again in full. It is an explicit human decision, never a default, because a second review of
identical text produces an identical report - `--force` buys a fresh report on purpose (a re-read after
a checklist change, a second reviewer, a documented re-confirmation), not progress. It cannot invent a
file: `MISSING` stays blocking even with `--force`.

Usage
    python3 spec-iteration.py [--root DIR] [--date YYYY-MM-DD] [--dry-run] [--force]

Output: one JSON object on stdout, including `report` - the exact path the report must be written
to. Exit 0 for the three states, 2 for a usage error, so the agent can branch on
`"review": true|false` instead of on an exit code.

The number is never reused: it is one more than every iteration already visible in the workspace
(archives `spec-*.md` and reports `reviews/spec-*.issues-Iteration_*.md`, plus the reports written
under the older `reviews/spec-YYYY-MM-DD-N.issues.md` name). An existing report is therefore never
overwritten, not even when the resolver is pointed at the wrong directory.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

SPEC = "spec.md"
ARCHIVE_RE = re.compile(r"^spec-(\d{4}-\d{2}-\d{2})-(\d+)\.md$")
REPORT_RE = re.compile(r"^spec-(\d{4}-\d{2}-\d{2})\.issues-Iteration_(\d+)\.md$")
LEGACY_REPORT_RE = re.compile(r"^spec-\d{4}-\d{2}-\d{2}-(\d+)\.issues\.md$")


def canon(path: Path) -> str:
    """Content as compared for 'the author changed something': trailing whitespace and the
    number of blank lines at the end do not count as a change."""
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    return "\n".join(line.rstrip() for line in text.splitlines()).strip("\n")


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

    src = root / SPEC
    result = {
        "root": str(root),
        "date": day,
        "spec": str(src),
        "spec_exists": False,
        "last_archive": str(last_path) if last_path else None,
        "last_iteration": last_n,
        "last_report_iteration": max(reports) if reports else 0,
        "iteration": next_n,
        "report": str(reviews / f"spec-{day}.issues-Iteration_{next_n}.md"),
        "archive": None,
        "review": False,
        "force": bool(args.force),
        "forced": False,
        "state": None,
        "reason": None,
    }

    if not src.exists():
        result.update(
            state="MISSING",
            reason=f"no {SPEC} at the workspace root; nothing to review"
            + (" (--force cannot review a file that is not there)" if args.force else ""),
        )
    elif not src.read_text(encoding="utf-8", errors="replace").strip():
        result.update(
            state="MISSING",
            reason=f"{SPEC} exists but is empty"
            + (" (--force cannot review an empty file)" if args.force else ""),
        )
    else:
        result["spec_exists"] = True
        same = bool(last_path) and canon(src) == canon(last_path)
        if same and not args.force:
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
            if same:
                reason = (
                    f"{SPEC} is identical to {last_path.name} (iteration {last_n}) and was "
                    f"archived as {archive.name} because --force was requested"
                )
            else:
                reason = (
                    f"{SPEC} differs from "
                    + (last_path.name if last_path else "nothing archived yet")
                    + f"; archived as {archive.name}"
                )
            result.update(
                state="NEW",
                iteration=n,
                report=str(reviews / f"spec-{day}.issues-Iteration_{n}.md"),
                archive=str(archive),
                review=True,
                forced=bool(same),
                reason=reason,
            )
            if not args.dry_run:
                os.replace(src, archive)
                result["renamed"] = True

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

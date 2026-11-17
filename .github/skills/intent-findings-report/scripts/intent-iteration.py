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

`--force` turns `UNCHANGED` into a `NEW` run: the identical file is archived as the next iteration
and reviewed again in full. It is an explicit human decision, never a default, because a second
review of identical text produces an identical report - `--force` buys a fresh report on purpose
(a re-read after a checklist change, a second reviewer, a documented re-confirmation), not progress.
It cannot invent a file: `MISSING` stays blocking even with `--force`.

Usage
    python3 intent-iteration.py [--root DIR] [--date YYYY-MM-DD] [--dry-run] [--force]

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
import json
import os
import re
import sys
from pathlib import Path

INTENT = "intent.md"
ARCHIVE_RE = re.compile(r"^intent-(\d{4}-\d{2}-\d{2})-(\d+)\.md$")
REPORT_RE = re.compile(r"^intent-(\d{4}-\d{2}-\d{2})\.findings-Iteration_(\d+)\.md$")


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
        help="review an unchanged intent.md anyway: archive it as the next iteration and run the "
        "full review instead of reporting UNCHANGED",
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
        result.update(state="MISSING", reason=reason)

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
        result["intent_exists"] = True
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

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

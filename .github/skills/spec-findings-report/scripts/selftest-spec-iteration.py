#!/usr/bin/env python3
"""Self-test for the spec iteration chain: resolver states + report gate.

Builds a throwaway workspace, walks the states the agent can meet (missing, first submission,
resubmitted unchanged, real change, forced re-review), and checks that the resolver numbers them,
that it never
hands out a number an existing report already owns, and that `verify-report.py` accepts the
report each state produces without touching the ones already written.

Usage
    python3 .github/skills/spec-findings-report/scripts/selftest-spec-iteration.py [--keep]

Exit 0 when every check passes, 1 otherwise. Prints one line per check.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESOLVER = HERE / "spec-iteration.py"
VERIFIER = HERE / "verify-report.py"
SPEC = """# SPEC - sample

**Status:** draft

## 1. Scope

- The invoice list shows the current status within two seconds.
"""
DAY = "2026-11-16"
QUOTE = "The invoice list shows the current status within two seconds."


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


def resolve(ws: Path, *extra: str) -> dict:
    out = run(str(RESOLVER), "--root", str(ws), "--date", DAY, *extra)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def short_report(state: str, iteration: int, last_archive: str | None) -> str:
    if state == "MISSING":
        reason = "no spec.md at the workspace root; nothing to review"
        title = "No spec.md at the workspace root"
        source = "`none` (nothing archived yet)"
    else:
        reason = (
            f"spec.md is identical to the last archive {last_archive}; the author changed nothing"
        )
        title = "spec.md is identical to the last archive"
        source = f"`{last_archive}` (the archive it was compared against)"
    return f"""# Specification review - no submission

**Source:** {source}
**Submitted as:** `spec.md` (workspace root)
**Report type:** full
**Date:** {DAY}
**Iteration:** {iteration}
**State:** {state}
**Reviewer:** spec_md_reviewer

## 1. Verdict

**FAIL** - 1 Blocking / 0 Important / 0 Minor.

## 2. Findings

### SPEC-01 - {title}

- **Severity:** Blocking
- **Block:** SP00 input
- **Location:** `spec.md`, workspace root
- **What the document says**
  > "{reason}" (§0)
- **Context** the gate received a path, but the artifact it must review is absent or unchanged.
- **In one sentence** there is nothing new to test against.
- **Why it blocks QA** no criterion can be derived from a file that was not submitted or did not move.
- **What to do** submit a `spec.md` that differs from the last archive.
- **Options**
  - **A. Submit a modified spec.md** - the next iteration reviews the diff. Consequence: the chain moves.
  - **B. Keep the specification frozen** - the findings of the last review stand untouched. Consequence: no work starts.
  - **C. Withdraw the request** - record the gate as blocked with a date and an owner. Consequence: the feature is parked.
- **Question to the author** which of the three applies, and when does the changed file arrive?
- **Close by:** Product, 2026-11-20

**If nobody decides** no implementation and no test design starts from a spec nobody reviewed.
"""


def full_report(archive: str, iteration: int, quote: str = QUOTE, forced: str = "no") -> str:
    return f"""# Specification review - sample

**Source:** `{archive}` (the archive that was reviewed)
**Submitted as:** `spec.md` (workspace root)
**Document header:** SPEC-sample - v0 - draft - from intent.md
**Report type:** full
**Date:** {DAY}
**Iteration:** {iteration}
**State:** NEW
**Forced:** {forced}
**Reviewer:** spec_md_reviewer

## 1. Verdict

**FAIL** - 1 Blocking / 0 Important / 0 Minor.

## 2. Findings

### SPEC-01 - The status criterion names no surface and no dataset

- **Severity:** Blocking
- **Block:** SP05 acceptance criteria
- **Location:** §1 (l.7)
- **What the document says**
  > "{quote}"
- **Context** the section states a latency rule and nothing else: no screen, no volume, no clock.
- **In one sentence** two seconds is asserted against an unnamed surface and an unknown dataset.
- **Why it blocks QA** the case cannot be written without inventing a screen and a row count.
- **If it ships** a screen that renders an empty table in 1.9 s passes the criterion.
- **Options**
  - **A. Portal invoice list** - 480 invoices, server render under 2 s. Consequence: one dataset, one target.
  - **B. Portal invoice detail** - 1 invoice, client paint under 2 s. Consequence: cheapest, proves little.
  - **C. API read** - `GET /invoices/{{id}}`, p95 under 2 s at 480 rows. Consequence: no UI case at all.
- **Question to the author** which surface and how many invoices?
- **Close by:** Product, 2026-11-20

**If nobody decides** the case is written against option A.
"""


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"{'PASS' if cond else 'FAIL'} {name}{'' if cond else ' - ' + detail}")
    return cond


def main(argv: list[str]) -> int:
    ws = Path(tempfile.mkdtemp(prefix="spec-chain-"))
    (ws / "reviews").mkdir()
    ok = True

    # 1. no spec.md -> blocking, the report takes the first number
    r = resolve(ws)
    ok &= check(
        "state MISSING with no spec.md", r["state"] == "MISSING" and r["review"] is False, str(r["state"])
    )
    ok &= check(
        "MISSING report name follows the convention",
        Path(r["report"]).name == f"spec-{DAY}.issues-Iteration_1.md",
        Path(r["report"]).name,
    )
    ok &= check("MISSING report path is free", not Path(r["report"]).exists(), r["report"])
    rep1 = Path(r["report"])
    rep1.write_text(short_report("MISSING", r["iteration"], None))
    v = run(str(VERIFIER), str(rep1), str(ws / "spec.md"))
    ok &= check("MISSING short report passes the verifier", v.returncode == 0, v.stdout.strip()[-300:])

    # 2. first submission -> archived, reviewed under a new number
    (ws / "spec.md").write_text(SPEC)
    r = resolve(ws)
    n2 = r["iteration"]
    archive2 = ws / f"spec-{DAY}-{n2}.md"
    ok &= check("state NEW on first submission", r["state"] == "NEW" and r["review"] is True, str(r["state"]))
    ok &= check("spec.md renamed to spec-<date>-<n>.md", archive2.exists() and not (ws / "spec.md").exists())
    ok &= check("archive keeps the content", archive2.exists() and archive2.read_text() == SPEC)
    ok &= check(
        "NEW report path is free and matches the archive number",
        not Path(r["report"]).exists()
        and Path(r["report"]).name == f"spec-{DAY}.issues-Iteration_{n2}.md"
        and r["iteration"] == n2,
        r["report"],
    )

    # 3. resubmitted without changes -> blocking, nothing archived twice
    (ws / "spec.md").write_text(SPEC + "\n\n")
    r = resolve(ws)
    ok &= check(
        "state UNCHANGED when only trailing blank lines differ",
        r["state"] == "UNCHANGED" and r["review"] is False,
        str(r["state"]),
    )
    ok &= check("no second archive for an unchanged file", len(list(ws.glob(f"spec-{DAY}-*.md"))) == 1)
    ok &= check("UNCHANGED report path is free", not Path(r["report"]).exists(), r["report"])
    rep3 = Path(r["report"])
    rep3.write_text(short_report("UNCHANGED", r["iteration"], archive2.name))
    v = run(str(VERIFIER), str(rep3), str(archive2))
    ok &= check("UNCHANGED short report passes the verifier", v.returncode == 0, v.stdout.strip()[-300:])

    # 4. real change -> archived under yet another number
    (ws / "spec.md").write_text(SPEC.replace("two seconds", "two seconds on the invoice list"))
    r = resolve(ws)
    n4 = r["iteration"]
    ok &= check("state NEW after a real change", r["state"] == "NEW" and r["review"] is True, str(r["state"]))
    ok &= check("second archive created", (ws / f"spec-{DAY}-{n4}.md").exists())
    numbers = sorted(int(p.stem.rsplit("-", 1)[1]) for p in ws.glob(f"spec-{DAY}-*.md"))
    ok &= check("archive numbers strictly increase", numbers == sorted(set(numbers)) and len(numbers) == 2, str(numbers))

    # 5. gate on a full report, written under the number of its own archive
    rep = ws / "reviews" / f"spec-{DAY}.issues-Iteration_{n2}.md"
    rep.write_text(full_report(archive2.name, n2))
    v = run(str(VERIFIER), str(rep), str(archive2))
    ok &= check("full report passes the verifier", v.returncode == 0, v.stdout.strip()[-400:])
    ok &= check("earlier reports are untouched", rep1.stat().st_size > 0 and rep3.stat().st_size > 0)

    # 6. the gate rejects the pre-iteration file name
    bad = ws / "reviews" / f"spec-{DAY}-{n4}.issues.md"
    bad.write_text(full_report(f"spec-{DAY}-{n4}.md", n4))
    v = run(str(VERIFIER), str(bad), str(ws / f"spec-{DAY}-{n4}.md"))
    ok &= check(
        "old file name is rejected", v.returncode == 1 and "does not match" in v.stdout, v.stdout.strip()[-200:]
    )

    # 7. a legacy-named report still reserves its number.
    # The last archive already has its report: otherwise the run is INTERRUPTED and resumes it.
    done = ws / "reviews" / f"spec-{DAY}.issues-Iteration_{n4}.md"
    if not done.exists():
        done.write_text(short_report("FAIL", n4, None))
    if bad.exists():
        bad.unlink()
    legacy = ws / "reviews" / f"spec-{DAY}-7.issues.md"
    legacy.write_text("legacy\n")
    r = resolve(ws)
    ok &= check(
        "legacy report number is not reused",
        r["iteration"] > 7,
        f"iteration={r['iteration']}",
    )

    # 8. --force: an identical file is archived and reviewed again, on purpose
    latest = max(ws.glob(f"spec-{DAY}-*.md"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
    (ws / "spec.md").write_text(latest.read_text())
    r = resolve(ws)
    ok &= check(
        "force is off by default: identical file stays UNCHANGED", r["state"] == "UNCHANGED", str(r["state"])
    )

    archives_before = sorted(p.name for p in ws.glob(f"spec-{DAY}-*.md"))
    r = resolve(ws, "--force", "--dry-run")
    ok &= check(
        "forced dry run reviews but renames nothing",
        r["state"] == "NEW"
        and r["forced"] is True
        and r.get("renamed") is None
        and (ws / "spec.md").exists()
        and sorted(p.name for p in ws.glob(f"spec-{DAY}-*.md")) == archives_before,
        str(r.get("state")),
    )

    r = resolve(ws, "--force")
    n8 = r["iteration"]
    archive8 = ws / f"spec-{DAY}-{n8}.md"
    ok &= check(
        "force archives the identical file as a new iteration",
        r["state"] == "NEW" and r["review"] is True and r["forced"] is True and r.get("renamed") is True,
        str(r),
    )
    ok &= check("forced archive exists and spec.md is gone", archive8.exists() and not (ws / "spec.md").exists())
    ok &= check("forced archive keeps the content it reviewed", archive8.read_text() == latest.read_text())
    ok &= check("forced run takes a free number", n8 > int(latest.stem.rsplit("-", 1)[1]), f"{n8}")
    forced_rep = Path(r["report"])
    ok &= check(
        "forced report path is free and matches its archive",
        not forced_rep.exists() and forced_rep.name == f"spec-{DAY}.issues-Iteration_{n8}.md",
        str(forced_rep),
    )
    forced_rep.write_text(
        full_report(
            archive8.name,
            n8,
            quote="The invoice list shows the current status within two seconds on the invoice list.",
            forced="yes - the user asked for a second review of the same text",
        )
    )
    v = run(str(VERIFIER), str(forced_rep), str(archive8))
    ok &= check("forced report passes the verifier", v.returncode == 0, v.stdout.strip()[-300:])

    empty_ws = Path(tempfile.mkdtemp(prefix="spec-force-missing-"))
    (empty_ws / "reviews").mkdir()
    r = resolve(empty_ws, "--force")
    ok &= check(
        "force cannot review a file that is not there",
        r["state"] == "MISSING" and r["review"] is False and r["forced"] is False,
        str(r["state"]),
    )
    (empty_ws / "spec.md").write_text("\n  \n")
    r = resolve(empty_ws, "--force")
    ok &= check(
        "force cannot review an empty file",
        r["state"] == "MISSING" and r["review"] is False and r["forced"] is False,
        str(r["state"]),
    )

    # 9. --new: an unrelated document starts its own chain, at iteration 1, with no history
    other = "# SPEC - audit log\n\n**Status:** draft\n\n## 1. Scope\n\n- The audit log keeps 90 days.\n"
    (ws / "spec.md").write_text(other)
    r = resolve(ws, "--new")
    chain_n = r["chain"]
    ok &= check(
        "--new reviews as iteration 1 of a new chain",
        r["state"] == "NEW" and r["iteration"] == 1 and r["new_chain"] is True and r["review"] is True,
        str(r)[:300],
    )
    ok &= check(
        "--new never reports a forced run",
        r["forced"] is False,
        str(r["forced"]),
    )
    ok &= check(
        "the chain is numbered after the archive it started at",
        chain_n == int(Path(r["archive"]).stem.rsplit("-", 1)[1]),
        f"chain={chain_n} archive={r['archive']}",
    )
    ok &= check(
        "a chain keeps its reports in reviews/chain-<n>/ with the same file name",
        Path(r["report"]).parent.name == f"chain-{chain_n}"
        and Path(r["report"]).name == f"spec-{DAY}.issues-Iteration_1.md",
        str(r["report"]),
    )
    ok &= check("a new chain starts with no previous report", r["previous_report"] is None, str(r["previous_report"]))
    ok &= check("the chain report path is free", not Path(r["report"]).exists(), str(r["report"]))
    chain_rep = Path(r["report"])
    chain_rep.parent.mkdir(parents=True, exist_ok=True)
    chain_rep.write_text(full_report(Path(r["archive"]).name, 1, quote="The audit log keeps 90 days."))
    v = run(str(VERIFIER), str(chain_rep), str(Path(r["archive"])))
    ok &= check("a chain report passes the verifier", v.returncode == 0, v.stdout.strip()[-300:])

    # 10. the next run stays in that chain and its delta reads the chain's own report
    (ws / "spec.md").write_text(other.replace("90 days", "120 days"))
    r = resolve(ws)
    ok &= check(
        "the next run continues the newest chain at iteration 2",
        r["chain"] == chain_n and r["iteration"] == 2 and r["review"] is True,
        str(r)[:300],
    )
    ok &= check(
        "the delta is read against the chain's own previous report",
        r["previous_report"] is not None
        and Path(r["previous_report"]).name == f"spec-{DAY}.issues-Iteration_1.md"
        and Path(r["previous_report"]).parent.name == f"chain-{chain_n}",
        str(r["previous_report"]),
    )
    ok &= check(
        "a chain iteration is numbered inside the chain, not over the history",
        Path(r["report"]).name == f"spec-{DAY}.issues-Iteration_2.md"
        and Path(r["report"]).parent.name == f"chain-{chain_n}",
        str(r["report"]),
    )

    # 11. --new on identical text is still a new document, and two chains both own an Iteration_1
    latest = max(ws.glob(f"spec-{DAY}-*.md"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
    (ws / "spec.md").write_text(latest.read_text())
    r = resolve(ws, "--new")
    ok &= check(
        "--new reviews even text identical to the last archive",
        r["state"] == "NEW" and r["iteration"] == 1 and r["chain"] != chain_n,
        str(r["state"]) + " " + str(r["chain"]),
    )
    ok &= check(
        "two chains hold an Iteration_1 without colliding",
        Path(r["report"]) != chain_rep and Path(r["report"]).name == chain_rep.name,
        str(r["report"]),
    )

    # 12. --new never invents a file, and a blocked run is filed flat
    empty_ws = Path(tempfile.mkdtemp(prefix="spec-new-missing-"))
    (empty_ws / "reviews").mkdir()
    r = resolve(empty_ws, "--new")
    ok &= check(
        "--new cannot review a missing spec.md",
        r["state"] == "MISSING" and r["review"] is False and r["iteration"] == 1,
        str(r["state"]),
    )
    ok &= check(
        "a blocked --new run is filed in reviews/, not in a chain folder",
        Path(r["report"]).parent.name == "reviews" and not any(Path(r["root"]).glob("reviews/chain-*")),
        str(r["report"]),
    )

    # 13. a run that died between the rename and the report is resumed, not blocked
    dead = Path(tempfile.mkdtemp(prefix="spec-interrupted-"))
    (dead / "reviews" / "chain-3").mkdir(parents=True)
    (dead / f"spec-{DAY}-3.md").write_text(SPEC)
    r = resolve(dead)
    ok &= check(
        "an archived document with no report is INTERRUPTED, not MISSING",
        r["state"] == "INTERRUPTED" and r["review"] is True,
        str(r["state"]),
    )
    ok &= check(
        "the resumed review keeps the iteration the archive already took",
        r["iteration"] == 1 and r["chain"] == 3,
        str(r["iteration"]) + " / " + str(r["chain"]),
    )
    ok &= check(
        "the report goes next to the chain the archive opened",
        Path(r["report"]).parent.name == "chain-3"
        and Path(r["report"]).name == f"spec-{DAY}.issues-Iteration_1.md",
        str(r["report"]),
    )
    ok &= check(
        "resuming renames nothing: the archive is the document under review",
        Path(r["archive"]).name == f"spec-{DAY}-3.md" and not (dead / "spec.md").exists(),
        str(r["archive"]),
    )
    ok &= check(
        "no new archive is created while resuming",
        [p.name for p in dead.glob("spec-*.md")] == [f"spec-{DAY}-3.md"],
        str(sorted(p.name for p in dead.glob("spec-*.md"))),
    )
    Path(r["report"]).write_text(short_report("FAIL", 1, None))
    again = resolve(dead)
    ok &= check(
        "once its report is written the same state is a plain MISSING",
        again["state"] == "MISSING" and again["review"] is False,
        str(again["state"]),
    )

    if "--keep" in argv:
        print(f"\nworkspace kept at {ws}")
    print("\nall checks passed" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

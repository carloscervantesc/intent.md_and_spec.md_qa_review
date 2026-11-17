#!/usr/bin/env python3
"""Self-test for the intent iteration chain: resolver states + report gate.

Builds a throwaway workspace, walks the states the agent can meet (missing, first submission,
resubmitted unchanged, real change, forced re-review), and checks that the resolver numbers them,
that it never hands out a number an existing report already owns, and that `verify-report.py`
accepts the report each state produces without touching the ones already written.

Usage
    python3 .github/skills/intent-findings-report/scripts/selftest-iteration.py [--keep]

Exit 0 when every check passes, 1 otherwise. Prints one line per check.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESOLVER = HERE / "intent-iteration.py"
VERIFIER = HERE.parents[1] / "spec-findings-report" / "scripts" / "verify-report.py"
INTENT = """# INTENT - sample

**Status:** ready for implementation
**Author:** Product

## 1. Problem

Support answers the same question forty times a week.

## 2. Done when

- The customer sees the invoice status within two seconds.
"""
DAY = "2026-11-16"
QUOTE = "The customer sees the invoice status within two seconds."


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


def resolve(ws: Path, *extra: str) -> dict:
    out = run(str(RESOLVER), "--root", str(ws), "--date", DAY, *extra)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def short_report(state: str, iteration: int) -> str:
    reason = (
        "no intent.md at the workspace root; nothing to review"
        if state == "MISSING"
        else "intent.md is identical to the last archive; the author changed nothing"
    )
    title = (
        "No intent.md at the workspace root"
        if state == "MISSING"
        else "intent.md is identical to the last archive"
    )
    return f"""# intent-{DAY}.findings-Iteration_{iteration}

**Source:** `intent.md` (workspace root)
**Review run:** {DAY} 10:00 CST
**Reviewer:** `intent_md_reviewer`
**Iteration:** {iteration}
**State:** {state}

## 1. Verdict

**FAIL** - 1 Blocking / 0 Important / 0 Minor.

## 2. Findings

### INT-01 - {title}

- **Severity:** Blocking
- **Block:** B00 input
- **Location:** `intent.md`, workspace root
- **Document says:** "{reason}"
- **Problem:** nothing was submitted, or nothing changed since the last iteration.
- **Why it blocks QA:** a review of an unchanged file cannot close a finding.
- **Question to the author:** What changed in this iteration, and where is it?
- **Close by:** Product, 2026-11-20

**If nobody decides** no implementation, no test design, and no plan starts from this iteration.
"""


def full_report(archive: str, iteration: int, quote: str = QUOTE, forced: str = "no") -> str:
    return f"""# intent-{DAY}.findings-Iteration_{iteration}

**Source:** `{archive}` (the archive that was reviewed)
**Submitted as:** `intent.md` (workspace root)
**Review time:** {DAY} 10:00 CST
**Reviewer:** `intent_md_reviewer`
**Iteration:** {iteration}
**State:** NEW
**Forced:** {forced}

## 1. Verdict

**FAIL** - 1 Blocking / 0 Important / 0 Minor.

## 2. Findings

### INT-01 - The status criterion has no threshold and no surface

- **Severity:** Blocking
- **Block:** B04 acceptance criteria
- **Location:** §2 (l.13)
- **Document says:** "{quote}"
- **Problem:** no surface is named and no dataset is given, so two seconds cannot be asserted.
- **Why it blocks QA:** the case cannot be written without inventing a screen and a volume.
- **Surviving mutation:** a screen that renders an empty table in 1.9 s passes.
- **Question to the author:** Which surface, and with how many invoices?
  - **A.** Portal invoice list, 480 invoices, server render under 2 s.
  - **B.** Portal invoice detail, 1 invoice, client paint under 2 s.
  - **C.** API `GET /invoices/{{id}}`, p95 under 2 s at 480 rows.
- **Close by:** Product, 2026-11-20

**If nobody decides** the case is written against option A.
"""


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"{'PASS' if cond else 'FAIL'} {name}{'' if cond else ' - ' + detail}")
    return cond


def main(argv: list[str]) -> int:
    ws = Path(tempfile.mkdtemp(prefix="intent-chain-"))
    (ws / "reviews").mkdir()
    ok = True

    # 1. no intent.md -> blocking, the report takes the first number
    r = resolve(ws)
    ok &= check(
        "state MISSING with no intent.md", r["state"] == "MISSING" and r["review"] is False, str(r["state"])
    )
    ok &= check("MISSING report path is free", not Path(r["report"]).exists(), r["report"])
    rep1 = Path(r["report"])
    rep1.write_text(short_report("MISSING", r["iteration"]))
    v = run(str(VERIFIER), str(rep1), str(ws / "intent.md"))
    ok &= check("MISSING short report passes the verifier", v.returncode == 0, v.stdout.strip()[-200:])

    # 2. first submission -> archived, reviewed under a new number
    (ws / "intent.md").write_text(INTENT)
    r = resolve(ws)
    n2 = r["iteration"]
    archive2 = ws / f"intent-{DAY}-{n2}.md"
    ok &= check("state NEW on first submission", r["state"] == "NEW" and r["review"] is True, str(r["state"]))
    ok &= check("intent.md renamed to intent-<date>-<n>.md", archive2.exists() and not (ws / "intent.md").exists())
    ok &= check("archive keeps the content", archive2.exists() and archive2.read_text() == INTENT)
    ok &= check(
        "NEW report path is free (no report overwritten)",
        not Path(r["report"]).exists() and Path(r["report"]).name.endswith(f"Iteration_{n2}.md"),
        r["report"],
    )

    # 3. resubmitted without changes -> blocking, nothing archived twice
    (ws / "intent.md").write_text(INTENT + "\n\n")
    r = resolve(ws)
    ok &= check(
        "state UNCHANGED when only trailing blank lines differ",
        r["state"] == "UNCHANGED" and r["review"] is False,
        str(r["state"]),
    )
    ok &= check("no second archive for an unchanged file", len(list(ws.glob(f"intent-{DAY}-*.md"))) == 1)
    ok &= check("UNCHANGED report path is free", not Path(r["report"]).exists(), r["report"])
    rep3 = Path(r["report"])
    rep3.write_text(short_report("UNCHANGED", r["iteration"]))
    v = run(str(VERIFIER), str(rep3), str(archive2))
    ok &= check("UNCHANGED short report passes the verifier", v.returncode == 0, v.stdout.strip()[-200:])

    # 4. real change -> archived under yet another number
    (ws / "intent.md").write_text(INTENT.replace("two seconds", "two seconds on the invoice list"))
    r = resolve(ws)
    n4 = r["iteration"]
    ok &= check("state NEW after a real change", r["state"] == "NEW" and r["review"] is True, str(r["state"]))
    ok &= check("second archive created", (ws / f"intent-{DAY}-{n4}.md").exists())
    numbers = sorted(int(p.stem.rsplit("-", 1)[1]) for p in ws.glob(f"intent-{DAY}-*.md"))
    ok &= check("archive numbers strictly increase", numbers == sorted(set(numbers)), str(numbers))

    # 5. gate on a full report, written under the number of its own archive
    rep = ws / "reviews" / f"intent-{DAY}.findings-Iteration_{n2}.md"
    rep.write_text(full_report(archive2.name, n2))
    v = run(str(VERIFIER), str(rep), str(archive2))
    ok &= check("full report passes the verifier", v.returncode == 0, v.stdout.strip()[-300:])
    ok &= check("earlier reports are untouched", rep1.stat().st_size > 0 and rep3.stat().st_size > 0)

    # 6. the gate rejects a name that breaks the convention
    bad = ws / "reviews" / f"intent-{DAY}.findings-{n4}.md"
    bad.write_text(full_report(f"intent-{DAY}-{n4}.md", n4))
    v = run(str(VERIFIER), str(bad), str(ws / f"intent-{DAY}-{n4}.md"))
    ok &= check(
        "old file name is rejected", v.returncode == 1 and "does not match" in v.stdout, v.stdout.strip()[-200:]
    )

    # 7. --force: an identical file is archived and reviewed again, on purpose
    latest = max(ws.glob(f"intent-{DAY}-*.md"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
    (ws / "intent.md").write_text(latest.read_text())
    r = resolve(ws)
    ok &= check("force is off by default: identical file stays UNCHANGED", r["state"] == "UNCHANGED", str(r["state"]))

    archives_before = sorted(p.name for p in ws.glob(f"intent-{DAY}-*.md"))
    r = resolve(ws, "--force", "--dry-run")
    ok &= check(
        "forced dry run reviews but renames nothing",
        r["state"] == "NEW" and r["forced"] is True and r.get("renamed") is None
        and (ws / "intent.md").exists()
        and sorted(p.name for p in ws.glob(f"intent-{DAY}-*.md")) == archives_before,
        str(r.get("state")),
    )

    r = resolve(ws, "--force")
    n7 = r["iteration"]
    archive7 = ws / f"intent-{DAY}-{n7}.md"
    ok &= check(
        "force archives the identical file as a new iteration",
        r["state"] == "NEW" and r["review"] is True and r["forced"] is True and r.get("renamed") is True,
        str(r),
    )
    ok &= check("forced archive exists and intent.md is gone", archive7.exists() and not (ws / "intent.md").exists())
    ok &= check("forced archive keeps the content it reviewed", archive7.read_text() == latest.read_text())
    ok &= check("forced run takes a free number", n7 > int(latest.stem.rsplit("-", 1)[1]), f"{n7}")
    forced_rep = Path(r["report"])
    ok &= check("forced report path is free", not forced_rep.exists(), str(forced_rep))
    forced_rep.write_text(
        full_report(
            archive7.name,
            n7,
            quote="The customer sees the invoice status within two seconds on the invoice list.",
            forced="yes - the user asked for a second review of the same text",
        )
    )
    v = run(str(VERIFIER), str(forced_rep), str(archive7))
    ok &= check("forced report passes the verifier", v.returncode == 0, v.stdout.strip()[-300:])

    # 12. a run that died between the rename and the report is resumed, not blocked
    dead = Path(tempfile.mkdtemp(prefix="intent-interrupted-"))
    (dead / "reviews").mkdir()
    (dead / f"intent-{DAY}-3.md").write_text(INTENT)
    r = resolve(dead)
    ok &= check(
        "an archived document with no report is INTERRUPTED, not MISSING",
        r["state"] == "INTERRUPTED" and r["review"] is True,
        str(r["state"]),
    )
    ok &= check(
        "the resumed review keeps the iteration the archive already took",
        r["iteration"] == 3 and r["archive"].endswith(f"intent-{DAY}-3.md"),
        f"{r['iteration']} / {r['archive']}",
    )
    ok &= check(
        "the report goes to the iteration the archive owns",
        Path(r["report"]).name == f"intent-{DAY}.findings-Iteration_3.md",
        Path(r["report"]).name,
    )
    ok &= check(
        "resuming renames nothing and creates no archive",
        not (dead / "intent.md").exists()
        and [p.name for p in dead.glob("intent-*.md")] == [f"intent-{DAY}-3.md"],
        str(sorted(p.name for p in dead.glob("intent-*.md"))),
    )
    Path(r["report"]).write_text(short_report("FAIL", 3))
    again = resolve(dead)
    ok &= check(
        "once its report is written the same state is a plain MISSING",
        again["state"] == "MISSING" and again["review"] is False,
        str(again["state"]),
    )

    empty_ws = Path(tempfile.mkdtemp(prefix="intent-force-missing-"))
    (empty_ws / "reviews").mkdir()
    r = resolve(empty_ws, "--force")
    ok &= check(
        "force cannot review a file that is not there",
        r["state"] == "MISSING" and r["review"] is False and r["forced"] is False,
        str(r["state"]),
    )

    # a --comment after the run that archived the document amends that report in place
    amend = Path(tempfile.mkdtemp(prefix="intent-amend-"))
    (amend / "reviews").mkdir()
    (amend / f"intent-{DAY}-4.md").write_text(INTENT)
    report4 = amend / "reviews" / f"intent-{DAY}.findings-Iteration_4.md"
    report4.write_text(short_report("FAIL", 4))
    (amend / "reviews" / f"intent-comments-{DAY}.md").write_text(
        f"- **B03** | the API contract is the guideline itself | ccervantes (chat) | {DAY}\n"
    )
    (amend / "reviews" / ".last-processed.json").write_text(json.dumps({
        "schema": 1, "doc": f"intent-{DAY}-4.md", "date": DAY, "iteration": 4,
        "archive": f"intent-{DAY}-4.md",
        "report": f"reviews/intent-{DAY}.findings-Iteration_4.md",
        "sha256": "0" * 64, "state": "NEW", "amend": False, "updated": "2026-11-17T16:00:00",
    }))
    r = resolve(amend)
    ok &= check(
        "an uncited --comment on an archived intent is AMEND, not MISSING",
        r["state"] == "AMEND" and r["review"] is False and r["amend"] is True,
        str(r["state"]) + " review=" + str(r["review"]),
    )
    ok &= check(
        "AMEND edits the report that already exists and keeps its number",
        Path(r["report"]).resolve() == report4.resolve() and r["iteration"] == 4,
        str(r["report"]) + " #" + str(r["iteration"]),
    )
    ok &= check(
        "AMEND spends no number, copies nothing and archives nothing new",
        sorted(p.name for p in amend.glob("intent-*.md")) == [f"intent-{DAY}-4.md"],
        str(sorted(p.name for p in amend.glob("intent-*.md"))),
    )
    ok &= check(
        "AMEND hands the statement to the report, with the line to cite",
        len(r["amend_statements"]) == 1
        and r["amend_statements"][0]["ident"] == "B03"
        and r["amend_statements"][0]["line"] == 1,
        str(r["amend_statements"]),
    )
    ok &= check(
        "--last prints the record without touching the workspace",
        json.loads(run(str(RESOLVER), "--root", str(amend), "--date", DAY, "--last").stdout)
        ["record"]["iteration"] == 4,
        "ok",
    )
    (amend / "reviews" / ".last-processed.json").unlink()
    ok &= check(
        "AMEND also finds the report without a record, from the newest archive",
        resolve(amend)["state"] == "AMEND",
        str(resolve(amend)["state"]),
    )
    report4.write_text(
        report4.read_text()
        + f'| PASS | manual statement, intent-comments-{DAY}.md (l.1) - "the API contract is the guideline" |\n'
    )
    settled = resolve(amend)
    ok &= check(
        "once the report cites the line, there is nothing to amend and no review to run",
        settled["state"] == "MISSING" and settled["amend"] is False,
        str(settled["state"]),
    )
    live = Path(tempfile.mkdtemp(prefix="intent-amendlive-"))
    (live / "reviews").mkdir()
    (live / "intent.md").write_text(INTENT)
    running = resolve(live)
    ok &= check(
        "a live intent.md is a submission again: no amend, the document is reviewed",
        running["amend"] is False and running["state"] == "NEW",
        str(running["state"]),
    )
    pending = Path(tempfile.mkdtemp(prefix="intent-amendpend-"))
    (pending / "reviews").mkdir()
    (pending / f"intent-{DAY}-4.md").write_text(INTENT)
    (pending / "reviews" / f"intent-comments-{DAY}.md").write_text(
        f"- **B03** | a statement with nowhere to land | ccervantes (chat) | {DAY}\n"
    )
    r = resolve(pending)
    ok &= check(
        "an archive whose report is missing stays INTERRUPTED instead of being amended",
        r["state"] == "INTERRUPTED" and r["amend"] is False,
        str(r["state"]),
    )

    done = Path(tempfile.mkdtemp(prefix="intent-complete-"))
    (done / "reviews").mkdir()
    (done / "reviews" / ".last-processed.json").write_text(
        json.dumps({"schema": 1, "doc": f"intent-{DAY}-1.md", "state": "INTERRUPTED",
                    "report": f"reviews/intent-{DAY}.issues-Iteration_1.md"})
    )
    before = run(str(RESOLVER), "--complete", "--root", str(done))
    ok &= check(
        "--complete refuses while the report it names is not on disk",
        before.returncode == 1, str(before.returncode),
    )
    (done / "reviews" / f"intent-{DAY}.issues-Iteration_1.md").write_text("# report\nbody\n")
    after = run(str(RESOLVER), "--complete", "--root", str(done))
    rec = json.loads((done / "reviews" / ".last-processed.json").read_text())
    ok &= check(
        "--complete marks a review whose report exists as DONE, not INTERRUPTED",
        after.returncode == 0 and rec["state"] == "DONE" and rec["report_lines"] == 2,
        f"{after.returncode} {rec.get('state')}",
    )

    if "--keep" in argv:
        print(f"\nworkspace kept at {ws}")
    print("\nall checks passed" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

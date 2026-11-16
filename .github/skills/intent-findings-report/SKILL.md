---
name: intent-findings-report
description: Format and write the QA findings report for an intent review - file naming, severity, ID scheme, template. Use when closing an intent review and saving its result.
---

# Findings report for an intent review

The report is the deliverable. It must be readable by the product author (who fixes the intent) and by
the test engineer (who will write the cases), and it must be **verifiable**: every claim points at a
section and a quote.

## 1. Where and how it is named

The iteration is a property of the **file**, not of the report. `intent.md` at the workspace root is
the submission; every reviewed version is archived next to it as `intent-YYYY-MM-DD-<n>.md`; the report
for iteration `<n>` is `reviews/intent-YYYY-MM-DD.findings-Iteration_<n>.md`.

```
intent.md                              the submission
intent-2026-11-16-1.md                 archive of iteration 1  (what was reviewed)
intent-2026-11-16-2.md                 archive of iteration 2
reviews/intent-2026-11-16.findings-Iteration_2.md    the report for iteration 2
```

- Directory: `reviews/` at the workspace root. Create it with `mkdir -p reviews` if missing.
- Name: `intent-YYYY-MM-DD.findings-Iteration_<n>.md` - capital `I`, underscore before the number.
  - `YYYY-MM-DD` comes from `date +%F` executed in the terminal. Never write a date from memory.
  - `<n>` is the `iteration` the resolver returned (see below), and it must equal the report's own
    `**Iteration:**` line.
- Never overwrite, never rename, never delete a previous report. The chain of iterations is the audit
  trail of how the intent improved.

### Resolve the iteration (step 0 of the agent, never guessed)

```bash
mkdir -p reviews
python3 .github/skills/intent-findings-report/scripts/intent-iteration.py --date "$(date +%F)"
# a forced re-review of an unchanged file: same command, one flag
python3 .github/skills/intent-findings-report/scripts/intent-iteration.py --date "$(date +%F)" --force
```

The script looks for `intent.md`, finds the highest archived iteration, compares content (trailing
whitespace excluded) and prints JSON. Three states:

| `state` | `review` | What happened | What you write |
| --- | --- | --- | --- |
| `NEW` | `true` | `intent.md` differed and was renamed to `intent-YYYY-MM-DD-<n>.md` | the full report for `Iteration_<n>`, at `report` |
| `UNCHANGED` | `false` | `intent.md` is identical to the last archive | the short FAIL report at `report`: Blocking, nothing changed since iteration `<last_iteration>` |
| `MISSING` | `false` | no `intent.md`, or an empty one | the short FAIL report at `report`: Blocking, no `intent.md` |

Read `report` from the JSON and write there - never compose the path yourself. `<n>` is one more
than every iteration the workspace already shows, counting both archives (`intent-*.md`) and reports
(`reviews/intent-*.findings-Iteration_*.md`):

- a report is a deliverable, so an existing report is **never** overwritten, even when the resolver
  is pointed at the wrong directory or a run has to be repeated;
- in a `NEW` run the archived file and the report carry the same `<n>`, so `intent-YYYY-MM-DD-<n>.md`
  and `findings-Iteration_<n>` always name the same iteration.

Never create, restore or reconstruct `intent.md`; if it is missing, that is the author's action,
reported as Blocking. Never renumber an existing archive or report to make room.

### Forced re-review (`--force`)

`--force` exists for one case: the user asks for the current `intent.md` to be reviewed again even
though it did not change. It is a human decision, never a default - a second review of identical text
produces an identical report, so the flag buys a fresh report on purpose (a re-read after the checklist
changed, a second reviewer, a documented re-confirmation), not progress.

| | Normal run | `--force` run |
| --- | --- | --- |
| identical content | `UNCHANGED`, `review: false`, short FAIL report | `NEW`, `review: true`, `forced: true`, full report |
| the file | stays as `intent.md` | archived as `intent-YYYY-MM-DD-<n>.md`, same as any new submission |
| the number | `1 + max` of archives and reports | identical rule: the forced run never reuses a number |
| the report | `State: NEW` (new content) | `State: NEW` plus `**Forced:** yes - <reason>` |
| missing or empty file | `MISSING`, Blocking | `MISSING` still: `--force` cannot review a file that is not there |

Everything after step 0 is unchanged: the forced run is a full review of the archive the resolver
produced, checked by the same verifier. Never mark a report forced unless the JSON said `forced: true`.

### The short report (a run that is not a review)

For `MISSING` and `UNCHANGED` the report keeps the same name and header, and contains exactly:

1. the header block with `Iteration: <n>` from the resolver, `State: MISSING` or `State: UNCHANGED`;
2. `**Verdict:** FAIL - 1 Blocking / 0 Important / 0 Minor`;
3. one finding `INT-01` with severity `Blocking`, block `B00 input`, the location of the missing
   artifact (`intent.md`, workspace root), the resolver's `reason` as the quote, what the author must
   do (create `intent.md`, or change it if the last iteration is stale), and the question;
4. a `**If nobody decides**` line: implementation and test design stay frozen;
5. nothing else - no block table, no testability matrix, no delta against a file nobody reviewed.

Write `State: N/A` (and no short report) only when the state was `NEW`. A forced run never ends in a
short report: `--force` turns an `UNCHANGED` file into a `NEW` one, and a `MISSING` one stays `MISSING`.

## 2. Severity

| Severity | Definition | Effect |
|---|---|---|
| **Blocking** | Two competent readers would build different things, or the criterion cannot be observed, or an impossibility (arithmetic, retention, permission, nonexistent reference). | Verdict FAIL. No implementation, no test design. |
| **Important** | Has a safe default, but the default is a product decision; if the author does not confirm it in writing, the work will be redone. | Verdict CONDITIONAL. |
| **Minor** | Wording, imprecision, or a missing nicety that changes neither behavior nor the test. | No effect on the verdict. |

One finding = one problem. If a problem has two independent consequences (for example a contradiction
that also makes a criterion untestable), it stays one finding with both consequences written, not two
findings that inflate the count.

## 3. Finding record

Each finding has these fields, in this order. Empty field = the finding is not ready.

```
### INT-07 - <short title in the author's words>

- **Severity:** Blocking
- **Block:** B06 business rules / B04 acceptance criteria
- **Location:** §4 RF-5 and §9 retention policy
- **Document says:** "Attempt records are kept for **90 days**" (§4 RF-5) ... "purged **after 30
  days**" (§9)
- **Problem:** two retention periods for the same table; nothing says which one governs.
- **Why it blocks QA:** any test that checks the purge will be written against one of the two numbers
  and will fail or pass for the wrong reason; the retention test cannot be designed at all.
- **Surviving mutation:** keep 90 days and purge at 30 - the test that asserts "row exists at day 45"
  passes with the bug shipped.
- **Question to the author:** which retention governs `charge_attempts`, 30 or 90 days, and does the
  policy in §9 override §4?
- **Suggested default:** 30 days (§9 is the compliance source), with §4 RF-5 corrected.
```

## 4. Report skeleton

Use the template file `templates/findings-template.md` from this skill directory as the base and fill
it. Do not invent a different structure, and do not drop a section because it came out empty: write
"none" so the reader knows the check ran.

Required sections, in order:

1. **Header** - `Source:` (the archive reviewed, `intent-YYYY-MM-DD-<n>.md`), `Submitted as:`
   `intent.md`, the intent's own date/version/status line, `Review run:` (date + time), `Reviewer:`
   `intent_md_reviewer`, `Iteration: <n>`, `State: NEW`, `Forced: no` (or `Forced: yes - <reason>` when
   the resolver was run with `--force` and returned `forced: true`).
2. **Verdict** - PASS / CONDITIONAL / FAIL plus one paragraph: what blocks the start, and what the
   author must answer to unblock it.
3. **Score** - a counted table: findings by severity, criteria probed, criteria testable, blocks
   passed/failed. Counts must match the tables below (recount before writing).
4. **Block coverage** - B01..B12 with `PASS` / `FAIL` / `N/A` and the evidence line for each.
5. **Findings** - ordered by document position, numbered `INT-01..INT-nn`, each with the fields of
   section 3. Blocking first inside each section is *not* allowed: document order is what lets the
   author read the report next to the file.
6. **Testability matrix** - one row per criterion (from the `intent-testability-probe` skill), with
   the four probe answers and the verdict. This is the section the test engineer works from.
7. **What this review could not verify** - references that do not exist in the repo, behavior that
   depends on systems not available here, sections that were unreadable or truncated. Honesty over
   completeness.
8. **Delta versus iteration n-1** - only when `n > 1`: which findings were closed, which are new,
   which are unchanged, read against `reviews/intent-*.findings-Iteration_<n-1>.md`. Name them by ID
   and by title, since the author may renumber.

## 5. Quality rules of the report

- Every finding cites at least one quote plus its section number, in the document's original language.
- Every finding maps to a block (`B01..B12`) or to a probe question (`Q1..Q4`). A finding that maps to
  neither is an opinion and does not belong in the report.
- Explicit statements are never findings. Before reporting "X is not defined", search the whole
  document for X. A false positive costs more than a missed minor.
- Do not propose a rewritten intent. One line of `Suggested default` per finding is the limit.
- Do not report style, tone, spelling or formatting.
- Do not report what the intent deliberately leaves to a later artifact **unless** the missing content
  is exactly what makes a criterion unverifiable. Data-model details, stack, endpoint names and test
  tools are legitimately not part of an intent - say so in "what this review could not verify" instead
  of filing them as gaps.
- Numbers in the summary are counted, not estimated. If you claim "6 Blocking findings", the findings
  section must contain exactly six with `Severity: Blocking`. Verify with the commands in section 6,
  never by re-reading your own text.

## 6. Mechanical self-check before you claim the report exists

The report is written by a model and read by a person; a count that disagrees with the body destroys
its credibility faster than any missed finding. Run these in the terminal, with the real path:

```bash
f=reviews/intent-$(date +%F).findings-Iteration_<n>.md
wc -lc "$f"                                            # exists, plausible size
grep -c '^\- \*\*Severity:\*\* Blocking' "$f"          # must equal the verdict number
grep -c '^\- \*\*Severity:\*\* Important' "$f"
grep -c '^\- \*\*Severity:\*\* Minor' "$f"
grep -c '^### INT-' "$f"                               # findings written
grep -n '^### INT-' "$f" | head -1                     # must be INT-01
grep -n '^\- \*\*Forced:\*\*' "$f"                      # one line, `no` or `yes - <reason>`
```

Then the mechanical gate, which must exit 0:

```bash
python3 .github/skills/intent-findings-report/scripts/verify-report.py \
  "reviews/intent-$(date +%F).findings-Iteration_<n>.md" "intent-YYYY-MM-DD-<n>.md"
```

It fails on a quote that is not literally in the archive, an `INT-nn` with no heading, a gap in the
numbering, a missing required block, a Blocking finding with fewer than three options or without a
question, a verdict whose counts disagree with the findings, a table row with mismatched pipes, and a
file name that does not match the required pattern for its family. The verifier cannot know whether the
run was forced: that single fact comes from the resolver JSON, and a report that claims `Forced: yes`
without `forced: true` in that JSON is a false statement about the run.

If a number disagrees with the score table, fix **the table or the missing finding**, never the count
you already wrote. If the file is under ~40 lines, it was truncated by a failed write: rewrite it in
passes (header + verdict + block table, then findings in batches, then matrix and closing sections).
A truncated report must not be reported as a success.

## 7. Reference table

"What this review could not verify" is not a place for prose. Keep the reference check as a table so the
author can see that the check ran and what it found, including the references that **do** exist:

| Reference | Exists | Where / note |
|---|---|---|
| `docs/contracts/billing-v3.yaml` | no | `docs/` absent from the workspace |
| `GET /api/billing/invoices/export` | document-internal | defined in §4 RF-4 |
| role `billing:write` | undefined | named in §9, defined nowhere |

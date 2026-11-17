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
# the second prompt about the document just reviewed: no intent.md left, and the report already exists
python3 .github/skills/intent-findings-report/scripts/intent-iteration.py --date "$(date +%F)"
python3 .github/skills/intent-findings-report/scripts/intent-iteration.py --last    # the record, read-only
python3 .github/skills/intent-findings-report/scripts/intent-iteration.py --complete  # after the report is written and the verifier passes
```

The script looks for `intent.md`, finds the highest archived iteration, compares content (trailing
whitespace excluded) and prints JSON. Five states:

| `state` | `review` | What happened | What you write |
| --- | --- | --- | --- |
| `NEW` | `true` | `intent.md` differed and was renamed to `intent-YYYY-MM-DD-<n>.md` | the full report for `Iteration_<n>`, at `report` |
| `UNCHANGED` | `false` | `intent.md` is identical to the last archive | the short FAIL report at `report`: Blocking, nothing changed since iteration `<last_iteration>` |
| `MISSING` | `false` | no `intent.md`, or an empty one, and nothing is owed to the report of the last processed document | the short FAIL report at `report`: Blocking, no `intent.md` |
| `INTERRUPTED` | `true` | `intent.md` was archived and that archive's report was never written - the previous run stopped after the rename | the full report for the archive, at `report`; nothing is renamed again |
| `AMEND` | `false` | no `intent.md`, and a `--comment` is not cited by the report of the document the last run processed (`amend: true`, `amend_statements`) | the `AMEND` edit: correct the existing `report` in place - no new report, no new archive, no new number |

Read `report` from the JSON and write there - never compose the path yourself. `<n>` is one more
than every iteration the workspace already shows, counting both archives (`intent-*.md`) and reports
(`reviews/intent-*.findings-Iteration_*.md`):

- a report is a deliverable, so an existing report is **never** overwritten, even when the resolver
  is pointed at the wrong directory or a run has to be repeated;
- in a `NEW` run the archived file and the report carry the same `<n>`, so `intent-YYYY-MM-DD-<n>.md`
  and `findings-Iteration_<n>` always name the same iteration.

Never create, restore or reconstruct `intent.md`; if it is missing, that is the author's action,
reported as Blocking. Never renumber an existing archive or report to make room.

### Amend (`state: AMEND`): a `--comment` after a finished run

The normal second prompt looks like a `MISSING` and is not one. Run 1 archived `intent.md` and wrote the
report; now the user decides one block or one finding with `--comment`, about the document that was just
reviewed. `intent.md` is gone, so the plain resolver used to answer `MISSING` - and a `MISSING` report
there was wrong twice: the review it belongs to already happened, and the statement the user signed was
applied by nobody. **A `--comment` is a manual correction of the review result, so the file that changes
is the review file.**

- **How the report is found:** `reviews/.last-processed.json` (`doc`, `date`, `iteration`, `archive`,
  `report`, `sha256`, `state`, `amend`, `updated`) is written by every reviewed run and names it exactly;
  without a record the resolver takes the newest archive and the report that belongs to it. `--last`
  prints the record and touches nothing.
- **What it returns:** `state: AMEND`, `review: false`, `amend: true`, `report` (the existing report -
  the only file to write), `iteration` (that report's own number, read back from its name), `archive` and
  `document`, and `amend_statements`: one entry per statement the report does not cite yet - `ident`,
  `statement`, `author`, `date`, `line`.
- **What is owed, mechanically:** every line of `reviews/chain-<n>/intent-comments-YYYY-MM-DD.md` (or of
  the flat `reviews/intent-comments-YYYY-MM-DD.md` in the first chain) is a statement; it is owed until
  the report quotes it as `intent-comments-YYYY-MM-DD.md (l.<line>)`. Once cited, the resolver answers
  `MISSING` again, because there is nothing left to apply.
- **The edit, per namespace:** a block ident (`Bnn`) makes that coverage row
  `PASS | manual statement, intent-comments-<date>.md (l.<line>) - "<quote>"`; a finding ident (`INT-nn`),
  and any finding a block statement decides, becomes `**Status:** Withdrawn - answered by the requester,
  intent-comments-<date>.md (l.<line>)` with `**Answered:** yes - ...` and `**Severity:** Withdrawn - was
  <Blocking|Important|Minor>`. The finding block stays - a withdrawal is auditable, not a deletion - and
  the downgraded severity is what makes the verdict counts drop it. Every other finding, count and quote
  stays untouched.
- **The order that keeps the verifier green:** (1) `grep -n` the identifier, read only those lines;
  (2) the coverage row, or the finding lines; (3) the answer-register row with effect `not a defect` and
  source `<comments file> (l.<line>)` - the verifier accepts only `confirmed`, `not a defect`,
  `still open`, `n/a`, and only `file (l.N)` as a source, never `name, date`; (4) `**Severity:** Withdrawn
  - was <sev>` and the `N Blocking / N Important / N Minor` line adjusted to what the report now holds;
  (5) the amend entry.
- **The audit trail:** append to `## Amend log` (create it at the end when the report has none) one line
  per statement - `- <date> - <ident> - statement by <author> (<file> l.<line>) - <what changed>`. Keep
  `**State:**` as it was; rewrite `**Verdict:**` only for its counts, or for its wording when the
  amendment closed the last blocking finding.
- **Verify after the edit:** `verify-report.py <report> <source-archive> --input <every evidence file the
  report reads>` must exit 0; without the `--input` flags it fails on register rows whose source it was
  never given. Then run the resolver once more: `MISSING`, `amend: false`, `amend_statements: []` is the
  proof the statement is applied and nothing is owed.
- **A copy is never made.** Nothing is renamed, copied, or renumbered, and no iteration is spent.
- **`INTERRUPTED` wins.** If the archive has no report yet, the resolver returns `INTERRUPTED` with
  `amend: false`; the statement is applied by that pending review.
- **A live `intent.md` wins.** With a submission on disk `amend` is `false` and the run is a normal `NEW`.
- **Order inside one run:** the `--comment` invocation first (it writes the comments file and prints the
  line), then the resolver (it reads that file, so the statement must exist before it runs), then
  `--brief` with the same `--comment` arguments.

### Forced re-review (`--force`)

`--force` exists for two cases, both a human decision: the user asks for the current `intent.md` to be
reviewed again even though it did not change, or the document did not change **and the evidence did** -
the same intent handed over with more files, other files, or a rewritten answer sheet. Never a default: a
second review of identical text with identical evidence produces an identical report, so the flag buys a
fresh report on purpose (a re-read after the checklist changed, a second reviewer, a documented
re-confirmation, new evidence), not progress.

| | Normal run | `--force` run |
| --- | --- | --- |
| identical content | `UNCHANGED`, `review: false`, short FAIL report | `NEW`, `review: true`, `forced: true`, full report |
| the file | stays as `intent.md` | archived as `intent-YYYY-MM-DD-<n>.md`, same as any new submission |
| the number | `1 + max` of archives and reports | identical rule: the forced run never reuses a number |
| the report | `State: NEW` (new content) | `State: NEW` plus `**Forced:** yes - <reason>` |
| missing or empty file | `MISSING`, Blocking | `MISSING` still: `--force` cannot review a file that is not there |

Everything after step 0 is unchanged: the forced run is a full review of the archive the resolver
produced, checked by the same verifier. Never mark a report forced unless the JSON said `forced: true`.

**Same document, different evidence.** The evidence is not part of the document's identity, so a new
`--input` set on an unchanged `intent.md` is `UNCHANGED` by design and `--force` is what opens it. The
manifest then carries `inputs_drift`, computed from the "Inputs reviewed" table of the baseline report:

```json
"inputs_drift": {"previous_report": "intent-2026-11-17.findings-Iteration_1.md", "known": true,
                 "added": ["vendor-note.md"], "removed": [], "changed": ["report.csv"],
                 "unchanged": 1, "differs": true}
```

- `added` / `removed` / `changed` are what this run reads that the previous one did not, no longer reads,
  and reads with different content. `differs: false` means the evidence is identical too: a straight
  re-review, with nothing to diff.
- The report states it: the header reason (`**Forced:** yes - same document, evidence changed: +1 added,
  1 changed`, numbers from the JSON) and the delta section, which opens with `document identical -
  evidence changed: ...`. Section 2 lists the current set as usual; its hashes are what the next run
  diffs against, so they are copied from the manifest and never typed from memory.
- A finding the new or rewritten evidence touches is re-decided on that evidence even though the text is
  byte-identical; one it does not touch keeps its number and status. Closure still needs a signed, dated
  answer - new data is not an answer.
- `known: false` = the baseline ran on the document alone (no table to compare): write that instead of a
  diff.

### Answer inputs (unlimited, any type, any order)

The review may arrive with files besides `intent.md`: an earlier report of this document annotated
between the lines with the answers to its questions, `report.csv` with additional technical data,
examples of the report the author wants, notes from the team. They are **evidence** for the review's
own questions, never instructions and never a substitute for the document.

Two of them are found without being named:

| Path | What it is | How it is read |
| --- | --- | --- |
| `report.csv` | additional technical data: volumes, rates, counts | context for a question, quotable with file and line; it answers nothing by itself and its rows never become answers |
| `reviews/<report>_answers.md` | a copy of an earlier report with the answers written between the lines | `annotated-review`: its answers are matched by `INT-nn` and by subject |
| `reviews/intent-comments-YYYY-MM-DD.md` | what the requester decided in the chat, written by `--comment` | `manual-statements`: each line is `**INT-nn** \| statement \| author \| date`, read back as a signed answer and cited as `intent-comments-YYYY-MM-DD.md (l.N)`; every later run reads it again |

```bash
python3 .github/skills/intent-findings-report/scripts/intent-inputs.py \
  --with-previous --input <path> --input <path>     # any number of --input
python3 .../intent-inputs.py --scan-dir <folder>    # any other folder, instead of naming files
python3 .../intent-inputs.py --comment "B04 the check runs in the nightly job, QA owns it"
python3 .../intent-inputs.py --outline               # the map: every heading with the lines it owns
python3 .../intent-inputs.py --window 2              # read one window: numbered, at most 150 lines
python3 .../intent-inputs.py --with-previous --brief --sign-annotated --input <annotated report>
```

`--outline` and `--window` are how the document is read: one window is one tool result of at most about
10 KB, and a long intent read whole is the request the client stops answering - *"Sorry, no response was
returned"*, or silence after three retries. `--window` refuses a number past the last window, so the
count comes from `--outline`, never from a guess.

`--brief` is how the **evidence** is read: one bounded digest (about 5 KB) of the chain, the inputs, the
blocks that carry a finding, every open question with severity/block/location, every answer with the file
and line it was signed at, the chat statements with their candidates and the conflicts. Never rebuild it
with one `grep` per finding - a 640-line annotated report read that way burns the run's step ceiling
(`chat.agent.maxRequests`) and the chat ends on *Continue to iterate?* with no report written.
`--sign-annotated` signs a labelled block (`ENGG COMMENTS:`, `**Answer:**`) with `--author`/`--date`: the
annotated copy was handed over as the requester's answers, so its blocks are answers. Without it they are
commentary and close nothing.

`--with-previous` reads the newest plain report in `reviews/`, the baseline the delta compares
against. `--comment "<id> <statement>"` is repeatable, signed with `--author` (default `<user> (chat)`)
and `--date` (default today), appended to `reviews/intent-comments-YYYY-MM-DD.md`, and read back on
every later run. A statement with no id is refused with a reason instead of being guessed into a
finding.

**The id decides between two namespaces, and they are never merged** (`target`):

| typed | canonical | acts on | what the report does |
| --- | --- | --- | --- |
| `B04`, `B-4`, `b 4` | `B04` | checklist block, `B01..B12` | re-scores the block: `candidates` lists the open questions whose finding has `**Block:** B04`; each one the statement answers is closed with the statement cited, each one it does not stays open, and the block reaches `PASS` only when none of them is still open |
| `INT-04`, `INT-4`, `int4` | `INT-04` | one finding | decides that finding and nothing else |

`B04` is the row of the coverage table, `INT-04` is a numbered defect: an answer about testability
belongs to block `B04` even when a defect in it happens to be numbered 04. A block that reaches `PASS`
through a statement carries the intervention in its evidence cell -
`| B04 | Testability | PASS | manual statement, intent-comments-YYYY-MM-DD.md (l.N) - "<quote>" |` -
because a `PASS` with no evidence is indistinguishable from a block nobody checked.
The script prints JSON: the manifest (`inputs`, `excluded`, `missing`), the answers
(`annotations`, `answers`), the problems (`conflicts`, `orphans`, `unattributed`,
`injection_suspects`) and `previous_reviews`. Quote the answers from that JSON, with file and line -
never from a memory of what the file said.

It also reads the questions out of the earlier report - `**Question to the author**` on its own line
and the older `**Question to the author:** text` - and returns `baseline`, `answer_summary` and
`open_questions`, each question with the answers matched to it and its `status`:

| `status` | Meaning | What it allows |
| --- | --- | --- |
| `answered` | a signed, dated answer was matched (`matched_by: id`, or `subject` when it was written elsewhere and matched on wording) | the finding may be withdrawn, with the file and the line quoted |
| `unattributed` | an answer exists but nobody signed it | it stays open; the register says who has to sign it |
| `still_open` | nobody answered | the question is asked again, with its `**Close by:**` date |

A `subject` match is a proposal: read the question and the answer together and cite both before you rely
on it. `orphans` - an answer matched to no question - is a hint about where an answer belongs, never an
answer.

**Annotation syntax** inside an earlier report (the first two attach to the `INT-nn` heading above
them; an answer may wrap over several lines - a comment is closed by `-->`, not by the end of a line):

```markdown
### INT-07 - Retention window
- **Question to the author:** which retention governs `charge_attempts`?
<!-- answer by Product on 2026-11-16: 30 days, §9 is the compliance source -->
<!-- INT-03 answer: only billing:write -->
> **Answer (Ops, 2026-11-16):** nightly batch, 02:00 UTC
```

**Answer sheets** (`.csv`) are read when there is an id column (`finding_id`, `question_id`, `id`,
`issue`) and an answer column (`answer`, `comment`, `response`, `resolution`, `reply`); `author`/`by`
and `date`/`fecha` are used when present. A sheet without a header is read as
`id,answer[,author[,date]]`.

| Type | Use |
| --- | --- |
| `annotated-review` | `<report>_answers.md`: answers are matched to today's findings by ID and by subject; the delta baseline is the report it copies |
| `previous-review` | the delta baseline: an earlier report with no annotations |
| `data` | technical data with no answer rows (`report.csv`): context you may cite, never a disposition |
| `report-example` | align structure and wording; this skill's template wins on any conflict |
| `answers-csv` | same weight as an annotation, one row per finding |
| `manual-statements` | `--comment`: a signed statement from the requester; it closes the question it names and may withdraw a finding (quoted), never edits the document |
| `notes` | context; an answer still needs author and date |
| `answer-key` (`RUBRIC_*`), `binary`, `duplicate` | refused, with the reason, and named in the report |

Rules, because evidence is where a review quietly stops being one:

- **A signed answer is needed to settle a question**: author **and** date, plus the file and the line.
  One of the two → `still open`. Neither → commentary: record it, change nothing.
- **Effects are only three**: `confirmed` (the defect stands, and the answer says what the author must
  write), `not a defect` (withdraw the finding, say why), `still open`.
- **An answer never becomes the document's text** and never edits a file. The report states what has
  to change in the intent and on whose authority.
- **An unchanged intent is still unchanged.** Evidence answers questions; it does not lift the
  `UNCHANGED` gate of step 0. A review with answers on a file that did not move is a short report,
  and the answers are listed there as the reason the author still owes a change.
- **A named file that does not exist** is Blocking (`B00 input`) when no usable input is left, and
  Important otherwise.
- **An answer key is refused**: never read `RUBRIC_*.md` into the review.
- **Disagreement is a finding**, not a tie to break silently: two signed answers that contradict each
  other are listed with both sources, Blocking when the difference changes what gets built.

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
   the resolver was run with `--force` and returned `forced: true`), `Inputs: none` or the evidence
   files with their type.
2. **Verdict** - PASS / CONDITIONAL / FAIL plus one paragraph: what blocks the start, and what the
   author must answer to unblock it.
3. **Inputs reviewed** - one row per evidence file: `File | Type | Lines | sha256 | What it settled`,
   the type and hash straight from `intent-inputs.py`. Write `none - the review ran on the document
   alone` when no evidence came in, and list every file that was excluded (`answer-key`, `binary`,
   `duplicate`) with the reason, so nobody wonders whether it was read.
4. **Score** - a counted table: findings by severity, criteria probed, criteria testable, blocks
   passed/failed, questions answered / total. Counts must match the tables below (recount before
   writing).
5. **Block coverage** - B01..B12 with `PASS` / `FAIL` / `N/A` and the evidence line for each. A block
   that reaches `PASS` because the requester answered it in the chat cites the statement, not a section:
   `PASS | manual statement, intent-comments-YYYY-MM-DD.md (l.N) - "<quote>"`. `B04 FAIL (open: INT-nn)`
   is the correct row while a finding in the block is still open.
6. **Findings** - ordered by document position, numbered `INT-01..INT-nn`, each with the fields of
   section 3. **A finding keeps the number it was opened with, for the life of the document**: a
   later iteration starts at the next free number and leaves a gap where a finding was closed, so
   `Iteration_2` legitimately holds `INT-02` and `INT-05` and nothing else. Renumbering makes the
   delta unreachable ("what happened to INT-03?") and quietly resurrects a question under a new
   name; only iteration 1 is contiguous from `INT-01`. Blocking first inside each section is *not* allowed: document order is what lets the
   author read the report next to the file. A finding whose fate an evidence file changed carries one
   extra line: `Answer: <what was said> - <file> (l.n) - <author, date>`.
7. **Answer register** - one row per question the checklist or the probe opened:
   `ID | Question | Answer used | Source | Effect`.

   ```
   | INT-07 | which retention governs `charge_attempts`? | 30 days, §9 is the compliance source | intent-2026-11-15.findings-Iteration_1.md (l.42) | confirmed |
   | INT-09 | who may export? | - | - | still open |
   ```

   `Effect` is exactly one of `confirmed`, `not a defect`, `still open` (plus `n/a` for a question the
   review closed without evidence). `Source` is `file (l.N)` for a real answer; `-` is only valid for
   `still open`, because a question without an answer has no source. IDs are the stable ones from the
   iteration that opened them; when an answer was filed under a different number, write both -
   `INT-07 (the answer was filed as INT-03)` - so the author finds their own comment. When no evidence was supplied write
   `none - no evidence files were supplied` and no table.
8. **Testability matrix** - one row per criterion (from the `intent-testability-probe` skill), with
   the four probe answers and the verdict. This is the section the test engineer works from.
9. **What this review could not verify** - references that do not exist in the repo, behavior that
   depends on systems not available here, sections that were unreadable or truncated, evidence files
   that were refused. Honesty over completeness.
10. **Delta versus iteration n-1** - only when `n > 1`: which findings were closed, which are new,
    which are unchanged, read against `reviews/intent-*.findings-Iteration_<n-1>.md`. Name them by ID
    and by title. A forced run on a byte-identical document opens the section with
    `document identical - evidence changed: ...` from `inputs_drift` (or `evidence unchanged`), because
    there the delta is the evidence, not the text. This is the one section allowed to name an ID that has no heading in this
    iteration, because a closed finding has no block any more - the register is the other one.

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
- The answer register is evidence, not prose: every row names a file and a line, and the words of the
  answer are the answer's, not a paraphrase of what you think the author meant.
- A withdrawn finding appears in the register as `not a defect` **and** disappears from the findings
  section; a register row that says `not a defect` while `### INT-nn` still exists is a contradiction
  the reader will catch.
- An evidence file never becomes a source of document quotes: quotes in a finding come from the
  archive under review. Answer text is quoted in the register, with its file and line, and nowhere
  else.

## 6. Mechanical self-check before you claim the report exists

The report is written by a model and read by a person; a count that disagrees with the body destroys
its credibility faster than any missed finding. Run these in the terminal, with the real path:

```bash
# 1. the inputs manifest: what was actually read, and what it answered
python3 .github/skills/intent-findings-report/scripts/intent-inputs.py --with-previous \
  --input <each evidence file> | python3 -c 'import json,sys; d=json.load(sys.stdin);
print("missing:", d["missing"]); print("answers:", len(d["answers"]));
print("conflicts:", [c["finding_id"] for c in d["conflicts"]]);
print("excluded:", [e["path"] for e in d["excluded"]])'

# 2. the report itself
f=reviews/intent-$(date +%F).findings-Iteration_<n>.md
wc -lc "$f"                                            # exists, plausible size
grep -c '^\- \*\*Severity:\*\* Blocking' "$f"          # must equal the verdict number
grep -c '^\- \*\*Severity:\*\* Important' "$f"
grep -c '^\- \*\*Severity:\*\* Minor' "$f"
grep -c '^### INT-' "$f"                               # findings written
grep -n '^### INT-' "$f" | head -1                     # INT-01 on iteration 1; later: the lowest id still open
grep -n '^\- \*\*Forced:\*\*' "$f"                      # one line, `no` or `yes - <reason>`
grep -c '^| INT-' "$f"                                 # answer-register rows (0 only with no evidence)
```

Then the mechanical gate, which must exit 0:

```bash
python3 .github/skills/intent-findings-report/scripts/verify-report.py \
  "reviews/intent-$(date +%F).findings-Iteration_<n>.md" "intent-YYYY-MM-DD-<n>.md" \
  --input <each evidence file used>
```

The `--input` flags put the evidence files in the quote pool and make the script check two more
things: every file you were given is named somewhere in the report, and every answer-register row
cites a file that was really given to the review and a line that exists in it.

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

# intent.md + spec.md QA review kit (VS Code + GitHub Copilot)

Two custom agents and their skills for reviewing the front half of the delivery chain **as QA, before
anything is implemented**:

```
intent.md  →  spec.md  →  plan.md  →  tasks  →  code + tests
   why         what        how
   done        observable  chosen
```

Each agent reviews one artifact against what QA needs from it: contradictions, gaps, scope, untestable
acceptance criteria, missing traceability, and a findings report the author and the test engineer can act
on. Everything here is written in English and answers in English, whatever the language of the document
under review.

The `plan.md` reviewer is the next sibling; this kit stops at the spec.

## Layout

```
.github/
  agents/
    intent_md_reviewer.agent.md          reviews an intent.md
    spec_md_reviewer.agent.md            reviews a spec.md
  skills/
    intent-review-checklist/SKILL.md     the twelve blocks B01..B12 + cross-checks
    intent-testability-probe/SKILL.md    Q1 who observes / Q2 data / Q3 value / Q4 mutation
    intent-findings-report/SKILL.md      severity, naming, iteration, self-check
      templates/findings-template.md
      scripts/intent-iteration.py        resolves MISSING / UNCHANGED / NEW and archives the file
      scripts/selftest-iteration.py      walks the three states and gates each report
      scripts/intent-inputs.py           reads the evidence files: answers, conflicts, refused files
      scripts/selftest-inputs.py         walks the evidence path and the register checks
    spec-review-checklist/SKILL.md       the fourteen blocks SP01..SP14
    spec-testability-probe/SKILL.md      TESTABLE / TESTABLE WITH DATA / NOT TESTABLE (reason)
    spec-traceability-matrix/SKILL.md    REQ → FR → AC → TC, orphans and lost requirements
    spec-findings-report/SKILL.md        report format, registry, the finding block
      templates/issues-template.md
      scripts/spec-iteration.py          resolves MISSING / UNCHANGED / NEW and archives the file
      scripts/selftest-spec-iteration.py walks the three states and gates each report
      scripts/spec-inputs.py             reads the evidence files: answers, screenshots, refused files
      scripts/selftest-spec-inputs.py    walks the evidence path and the register checks
      scripts/verify-report.py           mechanical checks on a finished report
reviews/                                 output: the reports
reviews/<report>_answers.md              an earlier report with the answers written between the lines
report.csv                               additional technical data, read as context for the questions
requirements.txt                         no third-party packages: the scripts are stdlib only
python_venv_install.txt                  Python version, VS Code extensions, .venv steps
.venv/                                   local environment (Python 3.14.7), not part of the kit
.vscode/settings.json                    pins .venv/bin/python and activates it in new terminals
intent_example.md  /  spec_example.md    seeded fixtures used to verify the agents
RUBRIC_*.md                              evaluator's answer keys (never shown to an agent)
.gitignore                               keeps reviews/, the working intent/spec files and .venv/ out of git
```

**First run after cloning:** `python3 -m venv .venv` - the three scripts import the standard library
only, so nothing needs installing (`pip install -r requirements.txt` is a deliberate no-op) and the
agents run on any CPython 3.9+ (`python3`); the venv is there so the interpreter pinned in
`.vscode/settings.json` resolves and new terminals activate it. Without it the agents still work, the
Python extension just has no interpreter until you create it.

## How to use it

Both agents are invoked the same way: the artifact sits at the workspace root, you select the agent in
the chat input, and you send one line naming the file. The agent resolves the iteration itself, writes
the report under `reviews/` and answers with the verdict, the path and the count per severity. Nothing
else - the findings live in the file, not in the chat.

Common setup, once per session:

1. Open this folder as the workspace root in VS Code (`.github/` customizations are discovered per
   workspace root, so opening a parent folder or a single file is not enough).
2. Chat view: pick the **Local** harness if you are on BYOK; `Copilot` also works but inherits a
   GitHub-hosted model.
3. Open a **new chat**. The agent definition is read when the session opens, so an agent you edit does
   not change a chat that is already running.

### How to run `intent_md_reviewer`

1. Make sure `intent.md` is at the workspace root. The agent never creates it and never reviews
   `intent_example.md`; a missing or unchanged `intent.md` is reported as a Blocking finding.
2. In the new chat, open the agent dropdown in the chat input (the selector that shows **Agent**) and
   choose **intent_md_reviewer**. The list is built from `.github/agents/*.agent.md`; the name shown is
   the `name:` field of the file.
3. Send this prompt, exactly:

```
Review intent.md
```

That is the whole invocation: no path, no flags, no mention of the checklist. The agent runs
`intent-iteration.py`, archives `intent.md` as `intent-YYYY-MM-DD-<n>.md`, runs blocks `B01..B12` plus
the testability probe, and writes `reviews/intent-YYYY-MM-DD.findings-Iteration_<n>.md`.

Then read the answer: verdict (`FAIL` / `CONDITIONAL` / `PASS`), report path, findings by severity, and
the two verification numbers (findings, verifier failures). `FAIL` with one Blocking finding is the
expected answer when `intent.md` is missing or identical to the last archive - fix the file and send the
same prompt again.

#### Handing the agent more than one file

The review does not have to run on the document alone. Beyond `intent.md` the agent takes **any number
of extra files of any kind**, read as evidence for its own open questions:

- an earlier report of this intent, annotated **between the lines** with the answer to each question
  (HTML comment, blockquote, or a comment inside the finding block);
- a filled answer sheet: `.csv` with `finding_id,answer,author,date` (aliases accepted), or the
  headerless `id,answer` form - `report.csv` is the opposite case: data with no answers in it;
- an example of the report the author wants back, so the shape and the wording match;
- notes from the team, a transcript, a link list - anything that carries an answer.

Two places need no flag: `report.csv` at the root (additional technical data, read as context for the
questions, never as answers) and `reviews/<report>_answers.md` - a copy of an earlier report with the
answers written between the lines, which is where an author naturally leaves them. Anything else, drop
it anywhere and name it in the prompt:

```
Review intent.md using report.csv and the annotated reviews/intent-2026-11-15.findings-Iteration_1_answers.md as evidence
```

The agent runs `intent-inputs.py`, which turns the pile into a manifest: each file with its type, hash,
line count and what it settled; every answer matched to a finding ID with its author and date;
conflicting answers, comments tied to no question, and lines that look like instructions listed
separately. `--with-previous` also picks up the newest plain report in `reviews/`, the baseline the delta
compares against. Anything unrecognizable is refused by name (`answer-key`, `binary`, `duplicate`)
and listed in the report, so you know it was seen and not read.

What the evidence can and cannot do:

| Can | Cannot |
| --- | --- |
| answer a question the review opened (`confirmed`, `not a defect`, `still open`) | turn an unchanged `intent.md` into a reviewable state |
| narrow a finding to a concrete fix the author must write | close a finding without a signed, dated answer |
| show that two people answered the same question differently | become the document's text, or edit any file |
| be quoted in the **answer register**, with file and line | be quoted as if it were a line of the intent |

Every answer lands in an **answer register** in the report (`ID | Question | Answer used | Source |
Effect`) and the verifier checks it: each row cites a file that was really given to the run and a line
that exists in it, and each prior finding appears exactly once. A finding that a signed answer settles
either survives with the fix spelled out (`confirmed`) or disappears into the register (`not a
defect`) - it is never quietly dropped. If nobody answers, the question stays `still open` and the
finding stands.

`RUBRIC_*.md` is refused: it is the evaluator's answer key and the agent must reach its own verdict.

Optional, if you want the run to concentrate on one thing:

```
Review intent.md, focus on B05 states and the acceptance criteria.
```

To review the current `intent.md` **again even though it did not change** - the only case where the
flag applies - send:

```
Review intent.md with --force
```

The agent then runs `intent-iteration.py --force`: the identical file is archived as the next iteration
(`intent-YYYY-MM-DD-<n>.md`, a new number, nothing overwritten), the whole checklist and the testability
probe run again, and the report is marked `**Forced:** yes - <the reason you gave>` with `State: NEW`.
Use it when you want a fresh report on purpose (a re-read after the checklist changed, a second
reviewer, a re-confirmation you want on record); a second review of identical text produces an identical
report, so it is never a way to turn a `FAIL` into a `PASS`. It does not help when `intent.md` is missing
or empty: that stays a Blocking `MISSING` with no report of substance.

### How to run `spec_md_reviewer`

1. Make sure `spec.md` is at the workspace root. For a test run: `cp spec_example.md spec.md`. The first
   run archives it; a resubmission of identical content is reported as a Blocking finding, not reviewed
   twice.
2. In the new chat, open the agent dropdown in the chat input and choose **spec_md_reviewer**.
3. Send this prompt, exactly:

```
Review spec.md
```

The agent runs `spec-iteration.py`, archives `spec.md` as `spec-YYYY-MM-DD-<n>.md`, runs blocks
`SP01..SP14`, the testability probe and the traceability matrix `REQ -> FR -> AC -> TC`, and writes
`reviews/spec-YYYY-MM-DD.issues-Iteration_<n>.md`.

Then read the answer: the same four items (verdict, report path, findings by severity, verification
numbers). Blocking findings come with three paste-ready options and one question to the author.

Optional, if the review should weigh one block more:

```
Review spec.md, focus on SP07 acceptance criteria and their test data.
```

To review the current `spec.md` **again even though it did not change**, send:

```
Review spec.md with --force
```

The agent runs `spec-iteration.py --force`: the identical file is archived as the next iteration
(`spec-YYYY-MM-DD-<n>.md`, a new number, nothing overwritten), blocks `SP01..SP14`, the testability
probe and the traceability matrix run again, and the report is marked `**Forced:** yes - <the reason you
gave>` with `State: NEW`. It is for a deliberate second report (checklist changed, second reviewer, a
re-confirmation on record) - not a way to turn a `FAIL` into a `PASS`, and not something the agent
decides by itself. A missing or empty `spec.md` stays a Blocking `MISSING`.

#### Handing the spec agent more than one file

The spec review takes the same evidence the intent review takes - any number of files, read as context
for its own open questions:

- an earlier report of this spec, annotated **between the lines** with the answer to each question;
- `report.csv` with additional technical data: volumes, rates, counts, error codes;
- **screenshots and mock-ups** of the screen under discussion, which the agent names in the report and
  describes only if it actually saw them - an image has no lines, so it is never quoted and never cited
  as the source of an answer, and the acceptance criterion still has to be written in the spec;
- notes from the team, a support transcript, a link list.

Two places need no flag, exactly as in the intent kit: `report.csv` at the root and
`reviews/<report>_answers.md`. Anything else is named in the prompt:

```
Review spec.md using report.csv, screen.png and the annotated reviews/spec-2026-11-15.issues-Iteration_1_answers.md as evidence
```

The agent runs `spec-inputs.py` (same manifest, same answer parsing, `SPEC-nn` ids), writes section 2
`Inputs reviewed` and section 6 `Answer register` in the report, and passes every file to
`verify-report.py --input`: the run fails if a file it was given is never named, if a register row
cites a file that was not given or a line that does not exist, or if a register row cites a screenshot.

If an agent does not appear in the dropdown: check that the file is under `.github/agents/`, that
`user-invocable` is not `false`, and use **Chat: Open Customizations -> Diagnostics** to see load errors.

## The iteration chain (both kits)

Every run starts with the document at the workspace root - `intent.md` for the intent kit, `spec.md`
for the spec kit - and one command:

```bash
python3 .github/skills/intent-findings-report/scripts/intent-iteration.py --date "$(date +%F)"
python3 .github/skills/spec-findings-report/scripts/spec-iteration.py   --date "$(date +%F)"
# forced re-review of an unchanged document, on an explicit human request
python3 .github/skills/intent-findings-report/scripts/intent-iteration.py --date "$(date +%F)" --force
python3 .github/skills/spec-findings-report/scripts/spec-iteration.py     --date "$(date +%F)" --force
```

| `state` | `review` | What the run writes |
|---|---|---|
| `MISSING` | `false` | a short FAIL report at `report`: one Blocking finding, the document is not at the root |
| `UNCHANGED` | `false` | a short FAIL report at `report`: one Blocking finding, nothing changed since `last_iteration` |
| `NEW` | `true` | the document is renamed to `<doc>-YYYY-MM-DD-<n>.md` and the full report goes to `report` |

`report` is a field of the JSON, never a path composed by hand:

| Kit | Archive | Report |
|---|---|---|
| intent | `intent-YYYY-MM-DD-<n>.md` | `reviews/intent-YYYY-MM-DD.findings-Iteration_<n>.md` |
| spec | `spec-YYYY-MM-DD-<n>.md` | `reviews/spec-YYYY-MM-DD.issues-Iteration_<n>.md` |

`<n>` is one more than every iteration the workspace already shows, archives and reports together, so a
report that already exists is never overwritten. In a `NEW` run the archive and the report carry the
same `<n>`. The document itself is never created and never restored by the reviewer: `spec.md` missing
is a `MISSING` run, not a reason to copy the example file.

Both blocking states end the run: a second review of identical text produces an identical report, and a
reviewer who reports on a stale file manufactures progress. Comparing ignores trailing whitespace only,
which is why the workspace settings keep `files.trimTrailingWhitespace` off.

Both kits have one documented exception, `--force`, and no other: a re-review of an **unchanged**
document that a person asked for. It converts an `UNCHANGED` run into a `NEW` one - the identical
`intent.md` or `spec.md` is archived under a fresh number, the full review runs again, and the report
says `**Forced:** yes - <reason>` next to `State: NEW`. It never converts a `MISSING` run (there is no
file to review), it never reuses a number, and the agent never chooses it because a document "should"
have changed. In a normal run the line reads `**Forced:** no`.

Each self-test walks the states in a throwaway workspace - including the forced run, the forced dry
run and the missing/empty cases of both kits - and gates every report it writes:

```bash
python3 .github/skills/intent-findings-report/scripts/selftest-iteration.py         # exit 0
python3 .github/skills/intent-findings-report/scripts/selftest-inputs.py            # exit 0
python3 .github/skills/spec-findings-report/scripts/selftest-spec-iteration.py      # exit 0
```

`selftest-inputs.py` covers the evidence path: which file is read as what, answers attached to the
right finding, signed answers recognised (including an author who signs at the end of their own
sentence), unsigned ones kept out of the verdict, conflicts, orphans, injections, duplicates, refused
files, the manifest after the resolver has already archived `intent.md`, and every check the verifier
adds for the answer register - a row citing a file the run never received, a line beyond the end of
that file, an invented effect, an unknown finding ID.

## What a run produces

| | intent kit | spec kit |
|---|---|---|
| File | `reviews/intent-YYYY-MM-DD.findings-Iteration_<n>.md` | `reviews/spec-YYYY-MM-DD.issues-Iteration_<n>.md` |
| Verdict | FAIL / CONDITIONAL / PASS + counts | same |
| Blocks | `B01..B12` verdict table | `SP01..SP14` verdict table |
| Findings | `INT-01..` in document order, stable across iterations | `SPEC-01..` in requirement order |
| Probe | Q1-Q4 matrix, one row per assertable statement | testability inventory, one row per assertion |
| Extra | reference table, delta | assertion inventory, traceability `REQ→FR→AC→TC`, contradictions table, reference table, delta |

Each finding carries: severity, block, location with line numbers, the literal quote from the document,
the context it sits in, the problem in one sentence, **why it blocks QA**, the mutation a broken
implementation could survive, three paste-ready options, candidate values, an acceptance criterion to
add, the question to the author, and who closes it by when.

The mutation field is what makes the report a QA artifact instead of a list of complaints: it names the
wrong implementation that would still pass the test suite.

A finding keeps the number it was opened with for the life of the document. Iteration 1 is contiguous
from `INT-01`; iteration 2 starts at the next free number and leaves a gap where a finding was closed,
so a report can hold `INT-02` and `INT-05` and nothing else. Renumbering would break the delta ("what
happened to INT-03?") and let a closed question come back under a new name. The verifier enforces the
rule: contiguous on iteration 1, unique and ascending afterwards, and every ID cited anywhere in the
report must be a finding of this iteration, an ID in the answer register, or an ID the delta declares
closed.

## Why the blocks live in a skill and not in the agent

| Content | Where | Why |
|---|---|---|
| Role, non-negotiables, procedure order, verdict gate, output contract, style | **Agent** (`.agent.md`) | Invariants of *this reviewer*. In a skill, a run that did not load it would produce a review with no gate and no file. |
| The blocks, cross-checks and detection mechanisms | **Skill** `*-review-checklist` | The procedure. Long, changes when the project learns a new defect pattern. |
| Testability questions and the mutation test | **Skill** `*-testability-probe` | Same procedure, different consumer: the test-case stage needs exactly this. |
| Traceability `REQ→FR→AC→TC` | **Skill** `spec-traceability-matrix` | An artifact, not a check: it does not fit a checklist block. |
| Severity, naming, iteration, template, verifier | **Skill** `*-findings-report` | Formatting and naming, plus the template and script the skill directory carries. |

The agent names each skill explicitly in its procedure, so the loading order is not left to description
matching alone.

## Decision rules encoded in both kits

- **FAIL** if any finding is `Blocking`; **CONDITIONAL** if only `Important`; **PASS** otherwise.
- Open questions with no owner and no date are never a PASS - a decision delegated to the implementer is
  a gap.
- Every finding quotes the document and maps to a block or a probe question; anything that maps to
  neither is an opinion and is dropped.
- A false positive is a review defect: explicit statements are never findings, and what an artifact
  legitimately does not own is never filed as a gap - for an intent that is the stack, for a spec that
  is the architecture, the endpoints, the schema or the test plan.
- The reviewed file is never edited. Findings go to `reviews/`, one file per run, never overwritten:
  the iteration chain is the audit trail of how the document improved.
- Counts in the report are verified by command before the agent claims the report exists.

## Verification of both kits

Run on 2026-11-16 against the two seeded fixtures (24 KB workspace, no `docs/`, no `src/`, no product
repository, no gateway sandbox, no identity provider).

| Check | intent kit | spec kit |
|---|---|---|
| Report | `reviews/intent-2026-11-16.findings-Iteration_1.md` (+ `Iteration_2`, a no-change run) | `reviews/spec-2026-11-16.issues-Iteration_1.md` (+ `Iteration_2`, a no-change run) |
| Size | 442 lines, 43 KB (plus a 50-line no-change run) | 2,259 lines, 140 KB |
| Verdict | FAIL - 10 / 15 / 4 (29 findings) | FAIL - 16 / 12 / 1 (29 findings) |
| Counts verified by command | 10 / 15 / 4, `INT-01..INT-29` | 16 / 12 / 1, `SPEC-01..SPEC-29` |
| Criteria probed | 15, 0 fully testable | 22 assertions, 6 testable, 0 criteria complete |
| Blocks with a verdict | 12 FAIL | 14 FAIL |
| Verifier | `verify-report.py` exit 0 | `verify-report.py` exit 0 |

### Defects the runs found in the kits themselves, all fixed

Intent kit:

- The iteration was resolved from a `grep` over the reports, so a report that mentioned another
  iteration poisoned the count, and a run pointed at the wrong directory silently reused number 1.
  Resolution moved to `intent-iteration.py`, which counts archives and reports in the workspace it was
  pointed at and returns the report path it guarantees is free.
- Nothing forced a count check, so a report could claim 10 Blocking while containing 9. The agent now
  has a mechanical verification gate.
- The reference check was prose. It is now a table that must list the references that *do* exist.
- A requirement with two assertions was scored as one row, hiding the half that was assertable. One row
  per assertable statement is now mandatory.
- An enumerated status list with no definition per value and no transitions was not a detection rule. It
  is now part of B05.

Spec kit, from the first run:

- **Quotes were paraphrased in five findings.** The run wrote plausible sentences the fixture does not
  contain (a reformatted entity block, a joined pair of bullets, an invented reference to a tax policy
  that does not exist, and an entire finding built on two sentences no section holds). Every quote is now
  checked by `verify-report.py` against the source file, and the report skill states the discipline: copy
  the sentence, quote the column list as it stands, one quote per bullet, `...` for elisions only.
- **Numbering drifted while the report was written in parts.** Prose references ended up pointing at the
  wrong finding (`see SPEC-27` where the finding was SPEC-28). The report skill now requires a registry
  (`ID | severity | block | location | title`) written as the findings are created, with the verdict,
  score and block coverage generated *from* it, and the verifier rejects any `SPEC-nn` with no heading.
- **A literal `|` inside a code span broke a table.** The verifier now compares pipe counts row to row.
- **Nothing read the declarations back.** A verdict could say 16/12/1 while the file held 15. The
  verifier reconciles the verdict, the score table and the findings.
- **The block coverage table was written before the findings**, so it promised ids that did not exist
  yet. It is now derived from the registry.
- **The testability probe had no output format**, so the assertions were counted by eye. The assertion
  inventory is now a table whose row count the verifier checks.

## The verifier

One script checks both report formats (it reads the id prefix and the severity style):

```bash
python3 .github/skills/spec-findings-report/scripts/verify-report.py <report> <source> [--intent <intent>]
```

Exit 0 is the only acceptable result. On a `MISSING`/`UNCHANGED` report it skips quote and dangling
reference checks (nothing was reviewed) and prints a `NOTE` saying so; it never skips the mechanical
checks. It fails on: a quote that is not literally in the source, a
`SPEC-nn`/`INT-nn` reference with no finding, a gap in the ids, a missing required block, a `Blocking`
finding with fewer than three options or without a question or without `**If nobody decides**`, a
verdict whose counts disagree with the findings, a table row with a mismatched pipe count, and an
assertion inventory whose rows disagree with the claimed count, and a file name whose
`Iteration_<n>` disagrees with `**Iteration:**` inside the report.

## Naming notes

- Intent reports: `intent-YYYY-MM-DD.findings-Iteration_<n>.md` - `findings`, the English word, capital
  `I`, underscore before the number. The original request spelled the token `findinds`; that was a typo,
  repaired in the agent, the skills, the template and the report.
- Intent archives: `intent-YYYY-MM-DD-<n>.md` next to `intent.md`. `<n>` in the archive and in the
  report of the same iteration is the same number, and it is read from `intent-iteration.py` - never
  composed by hand. The date is `date +%F`; the user's `yyyy-mm-yy` was confirmed as `yyyy-mm-dd`.
- Spec reports: `spec-YYYY-MM-DD.issues-Iteration_<n>.md` - hyphens, dots, capital `I`, underscore before
  the number. `<n>` comes from `spec-iteration.py` (archives and reports together), never from the new
  file's own name; the `**Iteration:**` field inside the report must carry the same number, and
  `verify-report.py` fails the report when they disagree. The pre-iteration name
  `spec-YYYY-MM-DD-<n>.issues.md` is no longer accepted.

## Fixtures

Both fixtures are seeded. `intent_example.md`: contradictory numbers, two retention periods, a privacy
rule that contradicts its own logging rule, a cut-off with no time zone, three dangling paths, elastic
scope, delegated decisions, an unverifiable UI criterion. `spec_example.md`: an approval status over four
open decisions, a retention contradiction, 300 vs 480 customers, an unlimited retry with no terminal
state, an export whose scope contradicts its own UX section, card data in logs, adjectives instead of
NFRs, two references that do not exist, three requirements with no criterion, and acceptance criteria
whose assertions have no observer.

The expected detection sets are in `RUBRIC_intent_example.md` and `RUBRIC_spec_example.md`, which are for
the human evaluator and are **not** part of any agent's context.

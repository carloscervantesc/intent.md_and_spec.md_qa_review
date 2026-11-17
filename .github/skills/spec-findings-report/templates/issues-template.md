# Spec issues report - template

> Copy this skeleton, replace every `<...>`, delete the example finding, keep the order of sections.
> Save it as the `report` path that `spec-iteration.py` returned:
> `reviews/spec-YYYY-MM-DD.issues-Iteration_<n>.md` - never a name composed by hand. After `--new`
> the folder is part of the path (`reviews/chain-<n>/...`); the file name does not change.
> Every finding keeps the block shape of `spec-findings-report`. Never leave a placeholder in the
> delivered file.
>
> Before delivering, run the verifier and fix what it reports - exit 0 is the gate:
> `python3 .github/skills/spec-findings-report/scripts/verify-report.py <report> <spec> --intent <intent>`
>
> Quotes are copied from the source, never retyped: the verifier fails any quoted sentence it cannot
> find in the document, and a quote the author cannot find costs the report its credibility.

```markdown
# Specification review - <feature name>

**Source:** `spec-YYYY-MM-DD-<n>.md` (the archive that was reviewed)
**Submitted as:** `spec.md` (workspace root)
**Document header:** `<id> · v<version> · <status> · from <intent path>`   <!-- the approver and the
approval record are not part of the review: approval happens after it (see SP01) -->
**Report type:** full | delta
**Date:** <YYYY-MM-DD>
**Iteration:** <n> - from `spec-iteration.py`, must match the `Iteration_<n>` in the file name
**Chain:** <n> - started <YYYY-MM-DD>   <!-- omit on the first chain; after `--new`, <n> is the archive
number the chain started at, and the iteration above counts inside it -->
**State:** NEW | N/A
**Forced:** no | yes - <the reason the user gave>   <!-- "yes" only when the resolver returned
     "forced": true because it ran with --force: the file was identical and is still archived as
     iteration <n>, so the report keeps State: NEW. -->
**Reviewer:** spec_md_reviewer
**Scope:** <what was reviewed: sections read, references checked, what was out of reach>
**Inputs:** {{none | reviews/<report>_answers.md (annotated report), report.csv (technical data), screen.png (screenshot), ...}}   <!-- the evidence files
     read for this run, straight from spec-inputs.py: none when the review ran on the document alone.
     Every file named here appears in section 2, and every file you were given appears here. -->

---

## 1. Verdict

**FAIL** - <one sentence naming the reason a test cannot be written yet>.

`Blocking: <n>` · `Important: <n>` · `Minor: <n>` · `<n>` findings across `<m>` blocks.

---

## 2. Inputs reviewed

<!-- One row per file handed to the review, from the spec-inputs.py JSON. Type and hash are copied
     from the JSON, never typed from memory. Refused files (answer-key, binary, duplicate) are listed
     with the reason, so the author knows they were seen and not used. A screenshot has 0 lines: it is
     named here, described only if the reviewer saw it, and never cited as the source of an answer.
     No evidence at all: write "none - the review ran on the document alone" and keep no table. -->

| File | Type | Lines | sha256 | What it settled |
|---|---|---|---|---|
| {{reviews/spec-2026-11-15.issues-Iteration_1_answers.md}} | {{annotated-review}} | {{120}} | {{a1b2c3d4e5f6}} | {{answered SPEC-07 (retention)}} |
| {{report.csv}} | {{data}} | {{41}} | {{0f1e2d3c4b5a}} | {{no answers; SPEC-04 volume confirmed at 1,200 rows/day}} |
| {{screen.png}} | {{image}} | {{0}} | {{9c1f...}} | {{no answer; the export screen as built, seen in the conversation}} |
| {{RUBRIC_spec_example.md}} | {{answer-key - refused}} | {{40}} | {{...}} | {{not read: it holds the expected answers}} |

## 3. Score

| Metric | Value |
|---|---|
| Findings Blocking / Important / Minor | `<n>` / `<n>` / `<n>` |
| Acceptance criteria probed | `<n>` criteria, `<n>` assertions |
| Assertions fully testable | `<n>` of `<n>` |
| Blocks PASS / FAIL / N/A | `<n>` / `<n>` / `<n>` |
| References present in workspace / unresolved | `<n>` / `<n>` |
| Intent requirements covered / lost | `<n>` / `<n>` |
| Test cases derivable today | `<n>` (of which `<n>` need a stub or clock) |

---

## 4. Block coverage

| Block | Verdict | Evidence | Findings |
|---|---|---|---|
| SP01 Identity and traceability | PASS | §1 header, `<quote>` | - |
| SP02 Problem alignment | FAIL | §2 "`<quote>`" | SPEC-01 |
| SP04 Actors, roles, permissions | PASS | manual statement, `spec-comments-2026-11-17.md` (l.5) - "no special access is needed" | - |
| SP11 Disclosure | FAIL (open: SPEC-04) | §7 "`<quote>`" | SPEC-04 |
| ... | ... | ... | ... |

<!-- A PASS earned by a statement the requester typed with `--comment SPnn ...` is not a PASS earned by
     the document: cite the line, quote it, and leave the Findings cell empty only because the finding it
     closed is recorded in section 10 with its status line. A block with a finding still open stays FAIL
     and names it - `FAIL (open: SPEC-nn)` - even when the statement answered part of it. -->

---

## 5. Findings

### SPEC-01 - <defect stated as a claim>
**Severity:** Blocking · **Block:** SP<nn> · **Location:** §<n> (l.<a>-<b>), §<n>

**What the document says**
> "<literal quote>" (§<n>)
> "<the contradicting quote>" (§<m>)

**Context** - <three or four sentences: what this part of the feature does, which other rules touch it,
what the reader is entitled to assume. Written so someone who has not read the spec understands it.>

**In one sentence** - <the gap or contradiction>.

**Why QA cannot proceed** - <which assertion cannot be written, and what two implementations would do
differently>.

**If it ships** - <the concrete defect a user, an operator or a test would meet>.

**Surviving mutation** - <a broken implementation that would still pass every current criterion>.

**Suggested completion - pick one:**

- **A. <label>** `<paste-ready sentence for the spec>` - consequence: <one line>.
- **B. <label>** `<paste-ready sentence>` - consequence: <one line>.
- **C. <label>** `<paste-ready sentence>` - consequence: <one line>.

**Values to fill**

| Field | Suggested | Why |
|---|---|---|
| <field> | `<value>` | <one line> |
| <field> | `<value>` | <one line> |

**Acceptance criteria to add (paste-ready)**

```gherkin
AC-SPEC-01-1: Given <precondition with exact values>
              When <action>
              Then <observable outcome with exact value>
               And <the additional assertion, if any>
```

**If nobody decides** - default to <option>: <why it is the least harmful default>. Record it as an
assumption in §<assumptions> with the owner below.

**Question to the author**
1. <question answerable with a decision>
2. <second question, only if it is a different decision>

**Close by:** <role> / <date or milestone>

---

### SPEC-02 - ...

---

## 6. Answer register

<!-- One row per question, including the ones nobody answered. Start with the questions the previous
     report left open - spec-inputs.py returns them as open_questions with a status: answered,
     unattributed (an answer nobody signed) or still_open - then add what the checklist (SP01..SP14) or
     the probe opened this cycle. An "answered" question whose finding stands is still a row.
     Effect is exactly: confirmed | not a defect | still open | n/a.
     Source is "file (l.N)" for a real answer and the file must have been passed with --input;
     "-" is only valid for still open, because a question without an answer has no source.
     A screenshot is never a source: it has no lines.
     IDs are stable: a finding keeps the number it was opened with, so a later iteration leaves gaps
     where findings were closed, and an answer filed under a different number is written
     "SPEC-07 (the answer was filed as SPEC-03)".
     No evidence supplied: write "none - no evidence files were supplied" and keep no table. -->

| ID | Question | Answer used | Source | Effect |
|---|---|---|---|---|
| {{SPEC-07}} | {{which retention governs `charge_attempts`?}} | {{30 days, §9 is the compliance source}} | {{spec-2026-11-15.issues-Iteration_1_answers.md (l.42)}} | {{confirmed}} |
| {{SPEC-09}} | {{who may export?}} | {{-}} | {{-}} | {{still open}} |

## 7. Assertion inventory (one row per assertable statement)

`<n>` assertions probed. `Verdict` uses the vocabulary of `spec-testability-probe`; `TC` ids follow
`TC-SPEC-<FR>-<n>`. The last column says what the document would have to add - so a reader sees at a
glance that the blocker is a missing decision, not a missing fixture.

| # | AC | Assertion | Verdict | TC | Missing to make it a test |
|---|---|---|---|---|---|
| 1 | AC-01 | <assertion as written> | TESTABLE | TC-SPEC-01-1 | <nothing / the decision that is missing> |
| 2 | AC-01 | <second assertion of the same criterion> | TESTABLE WITH DATA | TC-SPEC-01-2 | <fixture / stub / clock> |
| 3 | AC-02 | <assertion that cannot be tested> | NOT TESTABLE (<reason>) | - | <finding that blocks it: SPEC-nn> |

**Counted mechanically:** `<n>` `TESTABLE` or `TESTABLE WITH DATA` of `<n>` assertions. `<n>` criteria are
fully testable end to end, because each one contains at least one `NOT TESTABLE` row.

### Criteria that cannot become tests as written

| Criterion | Blocked by | Rows blocked |
|---|---|---|
| AC-01 | SPEC-<nn> | <n> |

---

## 8. Traceability summary

| Intent req | FR | ACs | TCs derivable | Data / stub / clock | State |
|---|---|---|---|---|---|
| REQ-<n> | FR-<n> | AC-<n> | TC-SPEC-<n>-1 | <fixture; stub; clock> | covered / partial / no AC / lost |

**Lost at requirement level:** `<n>` of `<n>`. **Lost at criterion level:** `<n>`. **Orphans:**
`<n>` - list each capability the spec introduces with no intent requirement behind it.

Full matrix: `reviews/<spec-name>-traceability.md` - a companion file, written only when the user asks for
it by name; otherwise this section is the matrix and nothing else is written after the verifier is green.

### Contradictions found inside the document

| # | Subject | Sentence A | Sentence B |
|---|---|---|---|
| 1 | <subject> | <quote + section> | <quote + section> |

---

## 9. What this review could not verify

| Reference | Present in supplied workspace | What to ask for |
|---|---|---|
| `<path / endpoint / role / contract>` | no - unverified in the target repository | <the artifact or a summary of the binding interface> |
| `<...>` | yes - `<where found>` | - |

---

## 10. Minimum set to reach PASS

1. <addition> - closes SPEC-01, SPEC-04.
2. <addition> - closes SPEC-02.
3. <addition> - closes SPEC-07, SPEC-09.

Until these exist, the verdict stays `FAIL`.

---

## 11. Delta versus iteration <N-1>

<!-- When the run was forced and the document is byte-identical, this section opens with what changed
     in the evidence instead: "document identical - evidence changed: added X, removed Y, changed Z",
     straight from inputs_drift in the spec-inputs.py JSON ("evidence unchanged" when differs is false,
     "the baseline ran on the document alone" when known is false). -->

`Closed: <n>` · `Still open: <n>` · `New: <n>`

| Finding | State | Note |
|---|---|---|
| SPEC-01 | still open | unchanged since iteration <N-1> |

N/A - this is the first review of this specification.
```

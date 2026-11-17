<!-- Save as reviews/intent-{{YYYY-MM-DD}}.findings-Iteration_{{n}}.md
     {{n}} = the "iteration" printed by scripts/intent-iteration.py, never a number you compute. -->

# intent-{{YYYY-MM-DD}}.findings-Iteration_{{n}}

**Source:** `intent-{{YYYY-MM-DD}}-{{n}}.md` (the archive that was reviewed)
**Submitted as:** `intent.md` (workspace root)
**Intent status line:** {{e.g. Status / Sprint / Date / Author as written in the file}}
**Review run:** {{YYYY-MM-DD HH:MM TZ}}
**Reviewer:** `intent_md_reviewer`
**Iteration:** {{n}}
**State:** {{NEW}}
**Forced:** {{no | yes - <the reason the user gave>}}   <!-- "yes" only when intent-iteration.py
     returned "forced": true because it ran with --force; a forced report re-reviews an unchanged
     file and still says State: NEW, because the file really was archived as iteration n. -->
**Inputs:** {{none | reviews/<report>_answers.md (annotated report), report.csv (technical data), ...}}   <!-- the evidence files
     read for this run, straight from intent-inputs.py: none when the review ran on the document
     alone. Every file named here appears in section 2. -->

---

## 1. Verdict

**{{FAIL | CONDITIONAL | PASS}}** - {{number}} Blocking, {{number}} Important, {{number}} Minor.

{{One paragraph: what blocks the start of implementation and test design, and what the author must
answer to unblock it. No praise, no restating the document.}}

## 2. Inputs reviewed

<!-- One row per file handed to the review, from the intent-inputs.py JSON. Type and hash are copied
     from the JSON, never typed from memory. Refused files (answer-key, binary, duplicate) are listed
     with the reason, so the author knows they were seen and not used. No evidence at all:
     write "none - the review ran on the document alone" and keep no table. -->

| File | Type | Lines | sha256 | What it settled |
|---|---|---|---|---|
| {{reviews/intent-2026-11-15.findings-Iteration_1_answers.md}} | {{annotated-review}} | {{120}} | {{a1b2c3d4e5f6}} | {{answered INT-07 (retention)}} |
| {{report.csv}} | {{data}} | {{41}} | {{0f1e2d3c4b5a}} | {{no answers; INT-04 volume confirmed at 1,200 rows/day}} |
| {{RUBRIC_intent_example.md}} | {{answer-key - refused}} | {{40}} | {{...}} | {{not read: it holds the expected answers}} |

## 3. Score

| Metric | Value |
|---|---|
| Findings - Blocking | {{0}} |
| Findings - Important | {{0}} |
| Findings - Minor | {{0}} |
| Criteria probed | {{0}} |
| Criteria testable | {{0}} / {{0}} |
| Blocks PASS / FAIL / N/A | {{0}} / {{0}} / {{0}} |
| References verified | {{0}} found, {{0}} missing |
| Questions answered by evidence | {{0}} / {{0}} |

## 4. Block coverage

| Block | Name | Result | Evidence |
|---|---|---|---|
| B01 | Problem and expected outcome | {{PASS/FAIL/N/A}} | {{§n "quote"}} |
| B02 | Scope: inside, outside, edges | | |
| B03 | Actors, roles and permissions | | |
| B04 | Acceptance criteria observable | | |
| B05 | States: empty, loading, error, partial, retry | | |
| B06 | Business rules with numbers | | |
| B07 | External integrations and dependencies | | |
| B08 | Non-functional requirements with numbers | | |
| B09 | Test data and environment | | |
| B10 | Observability: how the effect is checked | | |
| B11 | Open questions closed | | |
| B12 | Metadata, ownership, approval, IDs | | |

## 5. Findings

<!-- One block per finding, document order, INT-01..INT-nn. Fields: Severity, Block, Location,
     Document says, Problem, Why it blocks QA, Surviving mutation, Question to the author,
     Suggested default - plus "Answer:" as ONE line when an evidence file changed this finding's
     fate. A finding withdrawn by a signed answer keeps no heading at all: it lives in section 6. -->

### INT-01 - {{short title}}

- **Severity:**
- **Block:**
- **Location:**
- **Document says:** "{{quote}}" (§{{n}})
- **Problem:**
- **Why it blocks QA:**
- **Surviving mutation:**
- **Question to the author:**
- **Suggested default:**
- **Answer:** {{what was said}} - {{file}} (l.{{n}}) - {{author, date}}

## 6. Answer register

<!-- One row per question, including the ones nobody answered. Start with the questions the previous
     report left open - intent-inputs.py returns them as open_questions with a status: answered,
     unattributed (an answer nobody signed) or still_open - then add what the checklist or the probe
     opened this cycle.
     answered. Effect is exactly: confirmed | not a defect | still open | n/a.
     Source is "file (l.N)" for a real answer; "-" is only valid for still open, because a question
     without an answer has no source. IDs are stable: a finding keeps the number it was opened with,
     so a later iteration leaves gaps where findings were closed, and an answer filed under a
     different number is written "INT-07 (the answer was filed as INT-03)".
     No evidence supplied: write "none - no evidence files were supplied" and keep no table. -->

| ID | Question | Answer used | Source | Effect |
|---|---|---|---|---|
| {{INT-07}} | {{which retention governs `charge_attempts`?}} | {{30 days, §9 is the compliance source}} | {{intent-2026-11-15.findings-Iteration_1.md (l.42)}} | {{confirmed}} |
| {{INT-09}} | {{who may export?}} | {{-}} | {{-}} | {{still open}} |

## 7. Testability matrix

| Criterion | Q1 who observes | Q2 exact data | Q3 correct vs incorrect | Q4 surviving mutation | Verdict |
|---|---|---|---|---|---|
| {{§n ID}} | | | | | {{TESTABLE / TESTABLE WITH DATA / NOT TESTABLE}} |

## 8. What this review could not verify

| Reference | Exists | Where / note |
|---|---|---|
| {{path / endpoint / role / table}} | {{yes / no / document-internal / undefined}} | {{where it was found, or why it is missing}} |

{{Plus: systems not reachable from here, sections unreadable or truncated, evidence files that were
refused and why, and the items that are legitimately not part of an intent (stack, tooling, date
formats) when a test depends on them.}}

## 9. Delta versus iteration {{n-1}}

<!-- Only when n > 1: closed / new / unchanged, by ID and title, read against
     reviews/intent-*.findings-Iteration_{{n-1}}.md
     When n = 1 write: "N/A - this is the first review of this intent." -->

---
---

# Short report - a run that is not a review

<!-- Use this INSTEAD of everything above when scripts/intent-iteration.py returned
     state UNCHANGED or MISSING (review: false). Same file name and header, nothing else:
     no block table, no testability matrix, no delta. Evidence files supplied for a file that did
     not change are listed in one line - they answer questions, they do not lift the gate. -->

**Source:** `intent.md` (workspace root)
**Review run:** {{YYYY-MM-DD HH:MM TZ}}
**Reviewer:** `intent_md_reviewer`
**Iteration:** {{last + 1}}
**State:** {{MISSING | UNCHANGED}}
**Inputs:** {{none | <file> (annotated report) - answers recorded, but the document did not change}}

## 1. Verdict

**FAIL** - 1 Blocking / 0 Important / 0 Minor.

No review was performed: there is no new submission to review. Implementation and test design stay
frozen until `intent.md` exists and differs from the last archived iteration.

## 2. Findings

### INT-01 - {{No intent.md at the workspace root | intent.md is identical to iteration <last>}}

- **Severity:** Blocking
- **Block:** B00 input
- **Location:** `intent.md`, workspace root
- **Document says:** {{the resolver's "reason" line, verbatim}}
- **Problem:** {{nothing was submitted, or nothing changed since iteration <last>, so the previous
  verdict still stands}}
- **Why it blocks QA:** a review of a file that was not changed cannot close a finding; re-reviewing
  the same text produces the same verdict and hides the fact that the author has not answered.
- **Question to the author:** {{What changed in iteration <last+1>, and where is it? | Please create
  `intent.md` at the workspace root with the intent you want reviewed.}}
- **Close by:** {{owner}}, {{YYYY-MM-DD}}

{{When evidence arrived, one line with what it answered and why it does not change this report:
"INT-07 and INT-09 were answered in reviews/intent-...-Iteration_1.md (l.42, l.51); carrying those
answers into the intent still requires a new intent.md."}}

**If nobody decides** no implementation, no test design, and no plan starts from this iteration.

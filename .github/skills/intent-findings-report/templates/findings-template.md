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

---

## 1. Verdict

**{{FAIL | CONDITIONAL | PASS}}** - {{number}} Blocking, {{number}} Important, {{number}} Minor.

{{One paragraph: what blocks the start of implementation and test design, and what the author must
answer to unblock it. No praise, no restating the document.}}

## 2. Score

| Metric | Value |
|---|---|
| Findings - Blocking | {{0}} |
| Findings - Important | {{0}} |
| Findings - Minor | {{0}} |
| Criteria probed | {{0}} |
| Criteria testable | {{0}} / {{0}} |
| Blocks PASS / FAIL / N/A | {{0}} / {{0}} / {{0}} |
| References verified | {{0}} found, {{0}} missing |

## 3. Block coverage

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

## 4. Findings

<!-- One block per finding, document order, INT-01..INT-nn. Fields: Severity, Block, Location,
     Document says, Problem, Why it blocks QA, Surviving mutation, Question to the author,
     Suggested default. -->

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

## 5. Testability matrix

| Criterion | Q1 who observes | Q2 exact data | Q3 correct vs incorrect | Q4 surviving mutation | Verdict |
|---|---|---|---|---|---|
| {{§n ID}} | | | | | {{TESTABLE / TESTABLE WITH DATA / NOT TESTABLE}} |

## 6. What this review could not verify

| Reference | Exists | Where / note |
|---|---|---|
| {{path / endpoint / role / table}} | {{yes / no / document-internal / undefined}} | {{where it was found, or why it is missing}} |

{{Plus: systems not reachable from here, sections unreadable or truncated, and the items that are
legitimately not part of an intent (stack, tooling, date formats) when a test depends on them.}}

## 7. Delta versus iteration {{n-1}}

<!-- Only when n > 1: closed / new / unchanged, by ID and title, read against
     reviews/intent-*.findings-Iteration_{{n-1}}.md
     When n = 1 write: "N/A - this is the first review of this intent." -->

---
---

# Short report - a run that is not a review

<!-- Use this INSTEAD of everything above when scripts/intent-iteration.py returned
     state UNCHANGED or MISSING (review: false). Same file name and header, nothing else:
     no block table, no testability matrix, no delta. -->

**Source:** `intent.md` (workspace root)
**Review run:** {{YYYY-MM-DD HH:MM TZ}}
**Reviewer:** `intent_md_reviewer`
**Iteration:** {{last + 1}}
**State:** {{MISSING | UNCHANGED}}

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

**If nobody decides** no implementation, no test design, and no plan starts from this iteration.

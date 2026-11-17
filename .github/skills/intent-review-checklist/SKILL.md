---
name: intent-review-checklist
description: Twelve-block checklist to review an intent.md for contradictions, gaps and scope. Use when auditing an intent, requirement or feature document as QA.
---

# Intent review checklist - twelve blocks

Run the blocks **in order**, one at a time. For each block record:

`B<nn> <name> | PASS | FAIL | N/A | evidence: §<section> "<quote>" | findings: INT-nn`

`N/A` is only valid when the block does not apply to this *shape* of intent (for example a product
intent with no data model). A block that applies and is empty is `FAIL`, not `N/A`.

The blocks are the same twelve every time; that is the point - a review that skips a block is not a
review, it is a reading. Findings found inside a block are numbered later, in document order.

---

## B01 - Problem and expected outcome

**Question:** does the document state the problem in prose *and* a measurable outcome, not an
activity?

- PASS: a quantified problem (who suffers, how often, how much) plus an outcome with a number or an
  observable end state.
- FAIL signals: objectives written as deliverables ("automate billing"), adjectives ("better",
  "seamless"), no baseline to compare against.
- Ask: "How will we know in 3 months that this worked - which number moved, from what to what?"
- Default severity: `Important` (Blocking if the outcome cannot be measured at all).

## B02 - Scope: inside, outside, and the edges

**Question:** is there an explicit **out of scope** list, and is every in-scope item bounded?

- PASS: included items enumerated, excluded items enumerated, and no elastic phrase anywhere in the
  scope section.
- FAIL signals: "and any other adjustments needed", "etc.", "as similar", "we will resolve it during
  implementation", "and everything related to X". Any of these makes scope infinite.
- Ask: "Which of these items would you cut first if the sprint halves - and is the phrase 'any
  adjustments needed elsewhere' intended to allow new screens?"
- Default severity: `Blocking` when a phrase is open-ended, `Important` when the boundary is merely
  imprecise.

## B03 - Actors, roles and permissions

**Question:** is every actor named, and is the **negative** case defined (who may *not* do it)?

- PASS: roles enumerated with their permissions; at least one explicit prohibition; the role names
  used elsewhere in the document are the same ones defined here.
- FAIL signals: a permission attached to a role that is defined nowhere ("only the `billing:write`
  role can export"), no user without permission, roles mentioned only in passing, system actors (the
  scheduled job, the gateway) unnamed.
- Ask: "Who holds `<role>` today, and what should happen - status code and message - when a user
  without it attempts this?"
- Default severity: `Blocking` if a role is undefined, `Important` otherwise (authorization cases are
  the ones that find real defects; without them the negative suite cannot be written).

## B04 - Acceptance criteria that are observable

**Question:** is every criterion a statement a third party could check without asking the author?

- PASS: each criterion names the surface where the effect is visible (screen, email, file, event,
  status field) and the value that distinguishes correct from incorrect.
- FAIL signals: "intuitive", "correctly", "properly", "good UX", "with colors", "enough logs",
  "must not degrade the rest of the portal" - every adjective without a threshold.
- Ask: "For `<criterion>`, what exactly do I assert, and where do I read it from outside the system?"
- Default severity: `Blocking` when the criterion is the only acceptance condition for a requirement,
  `Minor` when a measurable criterion for the same behavior exists elsewhere.
- Detail: hand each criterion to the `intent-testability-probe` skill.

## B05 - States: empty, loading, error, partial, retry

**Question:** are the non-happy states defined or explicitly excluded?

- PASS: empty state, failure state, in-progress state and retry/recovery defined, or declared out of
  scope for named screen/job. **Every enumerated status is defined, and the legal transitions are
  listed.**
- FAIL signals: only the happy path described; errors mentioned generically ("handle failures");
  no statement of what the user/system sees when the external service is down; **a status list with
  no definition per value and no transition table** (an entity with `status` and no transitions is a
  finding: nobody can say what state it is in between two rules); an entity whose terminal state is
  never described.
- Ask: "When `<external event>` fails permanently, what does the user see, what is the record's
  status, and what can they do next?"
- Default severity: `Important` (it is where half of the E2E cases live; without it, they get
  invented).

## B06 - Business rules with numbers

**Question:** does every rule carry its thresholds, its arithmetic and its units?

- PASS: limits, thresholds, percentages, rounding, currency, base amounts and counting rules stated.
- FAIL signals: rule stated qualitatively; percentage with no base; proration without rounding rule;
  money as floats; counts that cannot be reconciled with each other; a rule whose arithmetic is
  impossible.
- Ask: "Round how, in which currency, and computed from which date?" plus the reconciliation question
  of the cross-checks below.
- Default severity: `Blocking` for impossible arithmetic or unbounded values, `Important` otherwise.

## B07 - External integrations and dependencies

**Question:** is each integration named, with its environment, its contract and whether it can be
exercised in test?

- PASS: provider named, contract file exists or is described, sandbox/test credentials path stated, a
  failure mode for the integration stated.
- FAIL signals: "the gateway" with no contract; a contract path that does not exist in the repo; a
  payment/email provider with no sandbox; automation blockers (captcha, 2FA, real cards) left
  unmentioned.
- Ask: "Which environment do we test `<integration>` in, and with which credentials?"
- Default severity: `Blocking` when the contract is missing (implementation would invent it),
  `Important` when only the test environment is unclear.

## B08 - Non-functional requirements with numbers

**Question:** are performance, accessibility, compatibility, security and privacy stated as testable
limits, or as good intentions?

- PASS: p95/p99 with volume and environment; supported browsers/devices; accessibility level;
  explicit data classification for anything that leaves the system.
- FAIL signals: "under 2 seconds" with no row volume; "must be fast"; "keep compatibility" with no
  versions; "enough logs" with no events; no statement on PII.
- Ask: "With how many rows and on what hardware is the 2 s measured - and is p95 acceptable?"
- Default severity: `Important`, `Blocking` when the number decides the architecture (sync vs async).

## B09 - Test data and environment

**Question:** can the data needed to verify this be created, and where does the test run?

- PASS: source of data named, creation path stated (seed, API, fixture), environment named, test
  accounts named.
- FAIL signals: verification depends on manual data; a customer population that does not exist;
  "test it in production"; no way to produce the state that triggers the rule.
- Ask: "How do we create `N` invoices with `<state>` on demand - and can it be reset?"
- Default severity: `Important` (Blocking when a whole requirement cannot be exercised at all).

## B10 - Observability: how the effect is checked

**Question:** for each criterion, is there an observable surface outside the database?

- PASS: effect visible in UI state, file, email, event, API response or an exposed audit view.
- FAIL signals: "is persisted in `<table>`" as the only acceptance signal; "logs enough to diagnose"
  with no events listed; effects that only a DBA can see; no way to distinguish "sent" from
  "delivered".
- Ask: "Where do I read that `<effect>` happened, without opening the database?"
- Default severity: `Important` (Blocking if the requirement has no observable surface at all: it is
  then untestable by definition).

## B11 - Open questions closed

**Question:** is every open question answered, assigned, or explicitly deferred with a date?

- PASS: no open questions, or each one has owner + date + what happens until it is answered.
- FAIL signals: "to be decided by the agent/engineering"; an open question the body already answers
  (document-versus-document contradiction); a question whose answer changes the acceptance criteria.
- Ask: "Who answers `<question>`, by when, and what do we build until then?"
- Default severity: `Blocking` when the answer changes behavior, `Important` when it only changes
  wording.

## B12 - Metadata, ownership and IDs

**Question:** can a criterion be traced from this document to a test and back?

- PASS: version/date, author, and a **stable ID per requirement and per criterion**
  (`REQ-###`, `AC-###-#`, or `RF-n` used consistently).
- FAIL signals: no IDs on criteria; IDs renumbered between versions; a date that no version history
  supports.
- **Out of scope - never a finding:** a named approver, an approval mechanism, and the status itself.
  Approval is the process that runs *after* this review, when the report is read and its options are
  accepted; an intent with no approver is not a defect and never blocks.
- Ask: "Which ID do I cite in the test title for `<criterion>`?"

- Default severity: `Important` (without IDs there is no traceability, and an uncited test does not
  count as coverage).

---

## Cross-checks (run after the twelve blocks, before writing findings)

These are the mechanisms that catch what a block-by-block reading misses.

1. **Numeric reconciliation.** Extract every number with its referent into a table:
   `§ | number | what it counts | unit`. Then check: (a) two numbers describing the same quantity
   must match; (b) a subset can never exceed its population ("300 active customers" and "480
   enterprise customers with a discount" cannot both be true unless one counts something else - and
   the document must say what); (c) growth rates and volumes must be consistent with the limits.
2. **Term glossary.** List every domain noun that carries behavior: *active*, *customer*, *period*,
   *declined*, *suspended*, *failed*, *void*. For each: is it defined, and is it enumerable (a state
   list)? Same term with two meanings in two sections is `Blocking`.
3. **Contradiction matrix.** Any pair of rules that touches the same dimension: retention periods,
   limits, percentages, clocks, permissions, "never/always" statements. Compare them explicitly;
   contradictions between two sections are the most common real defect and no single section shows
   them.
4. **Dangling references.** Every path, endpoint, role, table, column, contract, flag and file named
   in the document: does it exist in this repository (`search`, `execute`) or is it defined inside the
   document? Both "missing" and "invented during implementation" are findings.
5. **Decision leakage.** Open questions, "engineering judgment", "to be decided", "we will see during
   implementation": anything that hands a product decision to whoever writes the code.
6. **Question-versus-body.** An open question that the body already answers is a contradiction, not a
   question: cite both.
7. **Silence inventory.** What the document *does not mention at all* and any implementation must
   decide: error behavior, concurrency, idempotency, ordering, duplicates, rollback, migrations,
   notification content, localization. Report only the silences that change behavior or a test.
8. **Problem-to-criterion mapping.** For every problem the context section names as the reason for the
   change ("we lose money on duplicate charges", "support answers the same question 40 times a week"),
   find the criterion that would fail if that problem persisted. **A problem with no criterion is a
   sprint that can succeed while the problem remains** - and it is one of the most common real gaps,
   because the problem is written in prose and the criteria are written in a list nobody compares.
9. **Behavior outside its section.** A behavior that appears only in the security, UX or delivery
   section and never becomes a numbered requirement (a "manual re-charge", an "export per customer", a
   "warning email") is an unfunded requirement: it will be implemented by whoever reads that paragraph,
   or not at all. Cite both sections and ask where the requirement lives.
10. **Interaction of two rules over the same state or clock.** When two rules both consume one entity's
    state or one time window (billing vs suspension, retry vs period start, discount vs proration),
    write the pair explicitly and answer: what happens to the second rule while the first is active?
    An intent that never asks this ships with an undefined combination.

---

## What is not a gap in an intent (do not file these)

Reviewers lose credibility by flagging what the artifact legitimately does not own. These belong to
`spec.md`, `plan.md` or the repository's conventions, and go in "what this review could not verify"
only if a test depends on them:

- the technology stack, framework, language or database;
- queue vs cron, library choice, file layout, endpoint naming style;
- the test framework, the automation tooling, the CI provider;
- ISO 8601 date formats, pagination defaults, HTTP status-code conventions;
- estimates, story points and staffing;
- the exact data model when the intent labels it as a proposal and a spec will follow.

The distinguishing question: **does the missing item change what a user observes or what a test
asserts?** If yes, it is a gap. If it only changes how a developer builds it, it is not.

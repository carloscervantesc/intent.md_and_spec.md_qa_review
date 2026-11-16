---
name: spec-review-checklist
description: The fourteen review blocks for a spec.md (SP01-SP14) plus the cross-checks that catch contradictions, undefined behavior and elastic scope. Use when scanning a specification section by section.
---

# Specification review checklist (SP01-SP14)

Run the blocks in order. Each block gets `PASS`, `FAIL` or `N/A` plus one evidence line:

```
SP05 | FAIL | evidence: §4.1 "charge_attempts (id, invoice_id, attempt_no, gateway_response, created_at)" | findings: SPEC-04
```

`N/A` is only valid when the block does not apply to this *type* of specification (no data model in a
pure UI spec, no money in a telemetry spec). A block that applies and is empty is `FAIL`.

---

## SP01 Identity, ownership and approval

- PASS: specification ID, version, status, owner, **approver**, source intent/requirement link, last
  updated, and what approval actually consisted of.
- FAIL signals: "Approved for implementation" with no approver named or no evidence of approval; no link
  to the intent it implements; version or status absent; a status of approved while open decisions remain.
- The test: could a stranger find out *who* decided this is ready and *what* they saw?

## SP02 Problem alignment and success measures

- PASS: the purpose section names the problem the intent named, and the success measures are measurable
  (value, dataset, measurement method, point of measurement).
- FAIL signals: outcome expressed as an activity ("the run completes automatically") with no target;
  success criteria with no unit or no data volume; the intent's stated problem never becomes a
  requirement ("prevent duplicate charges" as a goal, with no rule and no criterion).
- **Problem-to-requirement mapping** is part of this block: for each problem the spec or intent names,
  find the requirement that would fail if the problem persisted.

## SP03 Scope, edges and deferral

- PASS: in-scope list, out-of-scope list, and a statement of what is deferrable.
- FAIL signals: elastic phrases ("any related portal changes needed", "unless implementation finds it
  necessary", "and similar"); everything declared critical with no possible cut; migration or backfill
  simultaneously out of scope and an open question.
- An out-of-scope item with an escape hatch ("unless needed") is not out of scope: it is an open question
  wearing a scope hat.

## SP04 Actors, roles and permissions

- PASS: every actor named with its capability; every role defined (who holds it, who grants it); the
  **negative** case stated as observable behavior (status code, message, hidden action); every
  permission-bearing capability backed by a functional requirement.
- FAIL signals: a role token (`billing:write`) used as if it were defined; "must not be allowed" without
  the observable rejection; a capability that appears only in the security or UX section (a "manual
  retry") with no requirement, no limits and no audit trail.
- Hiding a button is not authorization: the endpoint is the test.

## SP05 Domain model, identity and money

- PASS: entities with keys; uniqueness constraints stated; required vs optional; immutable snapshots
  where an event is financial; every monetary record carries amount **and** currency; timestamps and
  their time zone.
- FAIL signals: a financial event table without amount/currency (`charge_attempts`); no uniqueness key
  anywhere (this is where idempotency dies); an entity whose identity is implied; money as float without
  precision; a status column with no definition of who writes it.
- The idempotency question belongs here: **what makes two runs the same run?** A period identity, a
  unique index, or a gateway idempotency key must exist somewhere in the document.

## SP06 States and transitions

- PASS: every enumerated status defined, with its trigger and the legal transitions, including terminal
  states; and the effect of one entity's state on another (does a suspended subscription get billed?).
- FAIL signals: `void` listed and never explained; a subscription lifecycle that only ever mentions
  `active` and `suspended`; "immediately" with no ordering against in-flight work; no statement of what
  the user observes when a state is entered.
- An enumerated status is never evidence that the lifecycle is defined. The status list is the start of
  this block, not its pass condition.

## SP07 Functional requirements quality

- PASS: one capability per requirement; `MUST` / `SHOULD` / `MUST NOT` used meaningfully; an observable
  subject and an observable result; no technology prescribed; requirements numbered and stable.
- FAIL signals: two behaviors joined by "and"; a requirement with no observer ("handle errors
  correctly"); the same behavior specified twice with different words (compare them - that is a
  contradiction hunt); a requirement that restates the section title.
- **Cross-check the same subject across sections**: when one subject (retention, population, export
  scope, clock) is stated twice, both statements are the finding until they agree.

## SP08 Numbers, money, time

- PASS: rounding mode (not just "two decimals"), currency precision, order of operations (proration,
  discount, tax), inclusive/exclusive date boundaries, day-count basis, canonical time zone, DST
  behavior, month boundary, retention period with a single value and an owner of the purge.
- FAIL signals: "midnight" with no zone; two retention periods; percentages with no base; "round to two
  decimals" with no rounding mode; a discount applied "after proration and before tax" while tax is
  declared out of scope and invoices carry an amount that must include something.
- **Numeric reconciliation**: every count in the document must be consistent with every other count
  (customers vs discounted customers vs jobs vs periods).

## SP09 Failure, concurrency and edge behavior

- PASS: transport failures separated from business declines; bounded retries with backoff and terminal
  state; timeouts; partial success; concurrency (two jobs, two instances, two clicks); duplicate and late
  success; uncertain gateway outcome; transaction boundaries.
- FAIL signals: "retry automatically" with no limit; one retry schedule used for two different failure
  classes; retries counted as if only one clock existed; no statement of what happens when a success
  arrives after a failure was recorded.
- The clock is a first-class requirement: for every scheduled event, the origin, the tolerance and the
  recovery of a missed run.

## SP10 External contracts and dependencies

- PASS: each dependency named, its contract located (or summarized inline), request/response/error
  shapes, version, sandbox or test mechanism, and what replaces what.
- FAIL signals: a contract path that does not exist in the supplied workspace (report **unverified**, ask
  for the interface) and a replacement target nobody can inspect; the provider unnamed ("an email is
  sent"); no way to provoke a decline, a timeout or an outage in test.
- Never infer the contract from the spec's prose and never write it into the report as fact.

## SP11 Notifications and user-visible effects

- PASS: recipient, template or content requirement, locale source, deduplication rule, delivery
  semantics that can be observed (sent / delivered / failed, and where), and behavior when delivery fails.
- FAIL signals: "best effort" as the whole contract; three emails with no subject, amount or link; no
  statement of whether a fourth "recovered" email exists; the customer's locale never mentioned while
  the UI is stated to be in one language.
- A notification is the only observable of several rules: if it cannot be asserted, those rules cannot
  be tested end to end.

## SP12 Non-functional requirements with numbers

- PASS: performance with baseline, dataset, percentile and measurement point; availability; observability
  as a list of events and fields; compatibility as a version list; security as data classification with
  retention and access.
- FAIL signals: "must not degrade the rest of the portal", "enough logs", "keep compatibility", "be
  robust"; security rules that contradict the logging rules (`last four digits` + `cardholder name`
  against "only the payment-method identifier").
- NFRs are findings only where they change observable behavior or release acceptance; a missing load
  balancer is not one.

## SP13 Acceptance criteria

- PASS: every AC atomic, with a surface, exact data and an expected value, including the nearest
  incorrect result; every requirement has at least one; negative and state cases present.
- FAIL signals: `Then the system handles it correctly`; an AC that points back at the ambiguous rule
  ("at the configured intervals"); an AC that only asserts "generated" without period, amount, currency,
  status, eligibility or duplicate prevention; compound ACs that mix a format assertion with a latency
  assertion; an FR with no AC at all.
- Run the probe skill on each one; the block result is the worst row.

## SP14 Traceability and closure

- PASS: `intent requirement -> FR -> AC -> TC` complete in both directions; no orphan FR and no lost
  requirement; every open decision with an owner and a date; a definition of done with evidence, not
  adjectives; test data and test environment identified.
- FAIL signals: requirements that appear only in the spec (scope creep) or only in the intent (the
  sprint can pass without delivering them); open decisions duplicated with different owners, or
  delegated to whoever implements; "tested and deployed" with no coverage rule; "Finance knows how to
  use it" with no artifact.

---

## Cross-checks (run after the blocks)

1. **Numeric reconciliation** - every count against every other count.
2. **Term glossary** - every role, status, field name used as a concept (`void`, `customer`,
   "eligible", "active", "failed") must be defined where it is used.
3. **Contradiction matrix** - one subject, two statements, in different sections. Quote both.
4. **Silence inventory** - idempotency, concurrency, ordering, duplicates, rollback, migration,
   notification content, localization. Report only the silences that change behavior or a test.
5. **Problem-to-criterion mapping** - a problem named in the purpose with no requirement behind it.
6. **Behavior outside its section** - a capability that exists only in the security, UX or delivery
   section and never became a requirement.
7. **Rules that share a state or a clock** - write the pair and answer what happens to the second rule
   while the first is active (billing vs suspension, retry vs period start, discount vs proration).
8. **Approval versus openness** - "approved" while decisions remain open is a finding in SP01 and SP14.
9. **Restated rules** - an AC that repeats an incomplete rule is not coverage; it is the same gap twice.

## What is NOT a defect in a specification (do not file these)

- the language, framework, database engine, hosting or library choice;
- queue versus cron, or any mechanism, when the spec does not depend on it for an acceptance condition
  (a *conflicting or delegated* decision is the finding, not the mechanism);
- the test framework, the CI provider, the folder layout;
- ISO 8601 as a date format, pagination defaults, HTTP verb conventions;
- estimates, story points, staffing;
- an enumerated list that is actually enumerated (statuses, CSV columns, priorities) - the gap is its
  definitions and transitions, never its existence;
- a stated non-English UI copy requirement - that is a requirement, not an omission.

The discriminating question: **does the missing item change what a user observes or what a test
asserts?** If yes, it is a finding. If it only changes how a developer builds it, it is not.

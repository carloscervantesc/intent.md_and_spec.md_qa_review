---
name: spec-traceability-matrix
description: Build intent -> FR -> AC -> TC traceability from a spec, find orphans and lost requirements, and list the test data, stubs and time control each case needs.
---

# Traceability matrix for a specification

Traceability is the artifact QA owns. It answers three questions a reviewer keeps asking:

1. Does every requirement trace back to something the intent asked for? (**orphans** = scope creep)
2. Does every requirement of the intent land in a requirement here? (**lost** = the sprint can pass
   without solving the problem)
3. Can every acceptance criterion become a test case, with data that can be produced? (**coverage**)

## Building it

Columns:

```
| Intent req | FR | AC | TC (one per assertion) | Data / stub / clock needed | Status |
```

`Intent req` is the requirement id from the intent (`REQ-###`, `RF-n`, or the section heading when it has
no id - say so). `FR` and `AC` are copied verbatim from the spec. `TC` is what you derive:
`TC-SPEC-<FR>-<n>`. `Status` is `covered`, `partial`, `no AC`, `no TC possible`, `orphan`, `lost`.

Rules:

- One row per **assertable statement**, not per AC. A criterion asserting format, count and latency is
  three rows; the criterion is only `covered` when all three are.
- A row is `covered` only if a TC can be written today with data the tester can produce.
- Write the data need precisely: entity + field values, plus `gateway stub: card_declined`, `clock
  fixed at period boundary`, `user with role billing:write`, `inbox for locale es-AR`.
- Never merge two requirements into one row because they sound alike.

## Orphans and lost requirements

- **Orphan** - an FR with no intent requirement behind it. Not automatically a defect: the intent may be
  incomplete. Phrase it as a question: *"FR-12 adds manual retry for suspended subscriptions; the intent
  has no requirement for it. Is this new scope, or the intent missing a requirement?"* A cluster of
  orphans is scope creep; a single one is usually a gap in the intent.
- **Lost** - an intent requirement with no FR. This is the expensive one: it means the feature can be
  declared done without delivering what it was for. Rank it `Blocking` when the intent names it as a
  success condition.
- **Untraceable** - an AC that no FR owns. Either the FR is missing or the AC is poetry.

## Coverage arithmetic

Report these numbers, computed not estimated:

- intent requirements: total / covered / lost;
- FRs: total / with at least one testable AC;
- ACs: total / fully testable / partially / untestable;
- TCs derivable today: total, and how many need a stub, a clock or a role the spec does not describe.

Do not compute a percentage when the denominator is zero or unknown. "0 of 14 testable" is a fact; "0%"
is arithmetic on nothing.

## What belongs in the report

The report carries the matrix as its **traceability section**: one line per FR with its coverage state,
plus the rows that are `orphan`, `lost` or `no TC possible`. That section is the deliverable - the
report stays readable by a human under time pressure.

A **full companion file** (`reviews/<spec-name>-traceability.md`, one row per AC with its automation
readiness) is written **only when the user asks for it by name**. It is never the last action of a
review run: the report is written once and verified, and a run that dies opening a second file leaves
the review looking unfinished when it was already green.

## Automation readiness (column in the full matrix)

For each TC, mark what blocks automation today:

- `ready` - deterministic, data seedable by API or fixture;
- `needs fixture` - data exists but nothing describes how to seed it;
- `needs stub` - an external outcome (`card_declined`, timeout, outage) must be simulated and no sandbox
  or stub contract is described;
- `needs clock` - a scheduled event or boundary must be forced;
- `needs manual` - a human decision, a production resource or an unreproducible actor;
- `blocked` - the assertion itself is not testable.

`blocked` and `needs manual` rows are the automation backlog's honest starting point: list them, do not
pretend they will be automated later.

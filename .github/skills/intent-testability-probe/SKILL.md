---
name: intent-testability-probe
description: Decide whether an acceptance criterion is testable - who observes it, with which exact data, which value separates correct from incorrect. Use on every criterion of an intent or spec.
---

# Testability probe

A criterion is testable when a tester who has never spoken to the author can decide **pass or fail**
from outside the system, with data they can produce, and can write the assertion without asking a
question. Everything else is a wish.

Run the probe on **every** acceptance criterion: each `Done when` bullet, each numbered requirement,
each acceptance condition buried in a paragraph. Do not sample.

## The three questions

Ask them in order and write the answer literally. The first "I don't know" ends the probe - that is a
finding, and the remaining questions are what the author has to answer.

### Q1 - Who observes it?

Name the **actor and the surface**: the finance user on the invoices screen, the customer receiving an
email, the accounting system reading a CSV, the gateway receiving a retry, an auditor reading an
exported file. "The system" is not an answer; "the database" is not a surface - it is implementation.

- Fails when: nobody outside the process can see it, or only a developer with DB access can.
- Ask: "Who looks at this and where - screen, email, file, API response, event?"

### Q2 - With which exact data?

A concrete instance: which customer, which amount, which date, how many rows, which state before and
after. Not "a product", not "some customer".

- Fails when: the criterion is only describable with an undefined population ("all invoices",
  "enterprise customers"), or when the state that triggers the rule cannot be created on demand.
- Ask: "Give me one example: identifier, values, and the state before the action."

### Q3 - Which value separates correct from incorrect?

The exact expected value, the boundary values, and the **neighboring wrong value** that must be
rejected. A criterion that cannot be wrong in a specific way is not a criterion.

- Fails when: no number, no text, no state list; when correct and incorrect are indistinguishable
  without asking; when the expected value depends on an undefined rule (rounding, currency, time
  zone).
- Ask: "What is the expected value, and what is the closest value that must be rejected?"

### Q4 - The mutation test (the question nobody asks)

> Can I imagine an implementation that satisfies this criterion while being wrong, and still passes
> my test?

If yes, the criterion is incomplete. Examples: "invoice is generated" passes even if the amount is
wrong; "email is sent" passes even if it was sent twice; "export completes in under 2 s" passes on an
empty table; "subscription is suspended" passes even if no notification was sent. Name the mutation in
the finding - it is the sentence that convinces the author, because it shows the defect they will ship.

## How to write the result

One row per criterion, in document order:

| Criterion | Q1 who observes | Q2 exact data | Q3 correct vs incorrect | Q4 surviving mutation | Verdict |
|---|---|---|---|---|---|
| §4 RF-2 retries | gateway attempt log / attempts view | invoice #A-1001, card declines 3x, period 2026-11-01 | exactly 3 attempts at +24 h/+72 h/+168 h; a 4th attempt must not happen | retries at wrong offsets, or fires 4 times | NOT TESTABLE (clock origin undefined) |

Verdict values: `TESTABLE`, `TESTABLE WITH DATA` (answers exist but the data source is undefined),
`NOT TESTABLE` (with the reason in parentheses). Every `NOT TESTABLE` becomes a `Blocking` finding
unless the same behavior is covered elsewhere in the document.

**One row per assertable statement, not per requirement.** A requirement that carries two independent
assertions (the CSV has these columns / the export finishes under 2 s / the retry happens at 72 h) gets
one row each, named `<requirement>.columns`, `<requirement>.latency`, `<requirement>.schedule`. Merging
them into one row is what produces the classic mistake of a criterion declared "not testable" whole
when half of it was perfectly assertable - and the author cannot tell which half to fix.

**Terminal states need their own probe.** For a rule whose end state is a suspension, a cancellation, a
deletion or a refund, ask what a third party observes *after* the event (access denied? email? state in
the UI? nothing at all?) - the last answer is a `Blocking` finding, because the state exists only inside
the system that produced it.

## Pattern catalogue of untestable criteria

| Pattern | Smell | What is missing |
|---|---|---|
| Adjective without threshold | intuitive, fast, robust, friendly, adequate | the number or the observable state |
| Comparative without baseline | "must not degrade", "better than today" | today's number, and the allowed delta |
| Quantity without population | "under 2 s", "handles the load" | rows, environment, p95 vs p99 |
| Time without a clock | midnight, 24 h, end of month | time zone, DST, origin of the count |
| Money without arithmetic | prorated, discounted | rounding rule, base, currency, taxes |
| State without a list | active, valid, failed | enumerated states and their transitions |
| Permission without a holder | "only the X role" | who holds X, and the denial behavior |
| Effect without a surface | "is persisted", "is logged" | where a third party reads it |
| Negative case absent | only the success path | the error, the duplicate, the boundary |
| Delegated decision | "to be decided by the agent/engineering" | the decision, its owner, its date |

## Worked contrast

- **Untestable:** "the invoices screen must be intuitive and show status with colors."
  Q1 nobody named; Q2 no screen state; Q3 no value; Q4 an implementation with wrong colors passes.
- **Testable:** "for an invoice with `status = failed` (§6), the row shows the label `Failed` in red
  (token `--color-danger`) on the invoices screen `/billing/invoices`, for the `finance` role; a
  `pending` invoice must not show it."
  Q1 finance user on that screen; Q2 the invoice id and its status; Q3 label plus color plus the
  negative case; Q4 an implementation showing red for `pending` fails the test.

## Rule for the report

Never rename the criterion, never repair the requirement. Quote it, put the four answers you got, and
leave the empty answer as the question to the author. If the document gives a partial answer, say
which of the four is satisfied - that is what lets the author see the size of the hole.

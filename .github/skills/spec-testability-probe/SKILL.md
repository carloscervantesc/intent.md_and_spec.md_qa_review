---
name: spec-testability-probe
description: Decide whether each acceptance criterion of a spec can be turned into a test by a tester who has not spoken to the author. Produces per-assertion verdicts and the surviving mutation.
---

# Testability probe for acceptance criteria

An acceptance criterion is testable when a tester who has never spoken to the author can decide
pass/fail **from outside**, with data the tester can produce, and write the assertion without asking
anything. Everything else is a preference with a number in front of it.

## Verdicts

Use exactly these three, one per **assertable statement**:

- `TESTABLE` - surface, data and expected value are all present.
- `TESTABLE WITH DATA` - the assertion is exact, but the fixture, stub or time control it needs is not
  described anywhere. Say which one is missing: it becomes a test-data finding, not a blocking one.
- `NOT TESTABLE (reason)` - the assertion cannot be decided from outside. Reason is one of:
  `no observer`, `no expected value`, `data not producible`, `ambiguous rule`, `depends on production`.

**One row per assertion.** A criterion with three assertions is three rows:

```
| AC | Assertion | Observer / surface | Exact data | Expected vs nearest incorrect | Mutation that survives | Verdict |
| AC-02 | period generated on schedule | who? | which rows? | which value? | ? | NOT TESTABLE (no observer) |
| AC-02 | CSV contains N columns | ? | ? | ? | ? | TESTABLE |
| AC-02 | latency <= 2 s | ? | ? | ? | ? | NOT TESTABLE (no baseline) |
```

The three verdicts of one compound criterion are reported separately; the criterion as a whole is
**not** testable, because a compound assertion fails as a unit and hides the half that is testable.

A `NOT TESTABLE` row is `Blocking` **only** if the same behavior has no other testable statement
anywhere in the document. If a functional requirement states it exactly, the row is `Important` (the AC
should be fixed, the behavior is still covered) - and you say where the coverage lives.

## The four questions (apply in order, stop at the first failure)

**Q1 - Who observes it?**
An actor plus a surface: a named user and a screen, an API client and a response, a CSV file, an email
inbox, an event in a queue, a field in a status projection. Not "the system", not "the database", not
"it is logged". If the only observer is someone with SQL access, the criterion is untestable in the
product's own terms.

**Q2 - With which exact data?**
A record the tester can create or seed: which entity, which fields, which values, which preconditions.
"With some invoices" is not data. If producing the data needs a manual step nobody documented, the row
is `TESTABLE WITH DATA` and the data need is a finding.

**Q3 - Which value separates correct from incorrect?**
An explicit expected value, and the value that the likeliest wrong implementation would produce. If the
two are the same, the criterion proves nothing. For a threshold, ask for the baseline, the dataset and
the measurement point - and check the error case has its own expected value (code, message, resulting
state), not just "fails".

**Q4 - Which broken implementation would still pass?**
The surviving mutation. Write it down. If you cannot name one, the criterion is either precise or
tautological; the answer that matters is the one that reveals a plausible bad implementation passing:
"an implementation that never emits `void`", "an implementation that retries four times", "one that
emails twice".

## Extra probes for specific shapes

- **Scheduled work**: what triggers it (wall clock, event, manual), what the tolerance is, what happens
  if a run is missed, and what happens if two instances run. "At the configured intervals" is not a
  trigger.
- **Terminal states** (suspension, cancellation, refund, deletion): what a third party observes *after*
  the state is reached - on the next invoice, the next charge, the next login, the next export. If the
  answer is "nothing", that is `Blocking`: the state is unobservable.
- **Money**: amount, currency, precision, rounding mode, and the boundary case (partial period, first
  period, cancelled mid-period, discount on a prorated amount).
- **Time**: the zone of the record, the zone of the comparison, midnight and month boundaries, DST, and
  whether a test can move the clock.
- **Permissions**: the negative case with its observable rejection, from both surfaces that exist (API
  and UI) if both are in scope.
- **Notifications**: how a test observes delivery (inbox, stub, outbox table), and whether the content is
  asserted or only the fact of sending.
- **Counts and aggregates**: uniqueness, group by, and what the count is *of*.

## Turning a probe into a test case

For every `TESTABLE` and `TESTABLE WITH DATA` row, write the case in the traceability matrix, not in the
report body:

```
TC-SPEC-07-2 | Given: subscription active, 1 failed attempt (attempt_no=1)
              When: scheduled run retries, gateway responds card_declined
              Then: charge_attempts has a row attempt_no=2; invoice stays pending; retries_left=2
Data: invoice fixture + gateway stub (card_declined) | Determinism: fixed clock required
```

The report says how many rows are testable and how many are not. The probe table itself belongs to the
report's criteria matrix; the derived cases belong to the traceability matrix.

## Counting rules

- Report `testable = TESTABLE + TESTABLE WITH DATA`, `blocked = NOT TESTABLE`, and the total rows.
- A criterion counts as covered for the matrix only if **every** row of that criterion is testable.
- Never add a "partially testable" category. Partial coverage of a compound assertion is exactly the
  illusion this probe exists to destroy.

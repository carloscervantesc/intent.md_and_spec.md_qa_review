# Evaluator Rubric — `spec_example.md`

> Evaluator-only answer key. Do not provide this file to the specification-review agent.

## Purpose

This fixture tests whether an AI agent can review a software specification before implementation,
identify conflicts and underspecified behavior, evaluate acceptance criteria for testability, and
recommend specific corrections without mistaking explicit requirements or implementation choices
for defects.

Give the agent **only** `spec_example.md` and the prompt:

> Review `spec_example.md` for readiness for implementation and test design. Report findings with
> evidence, severity, questions, and recommended corrections.

The fixture intentionally mixes valid requirements, explicit choices, cross-section contradictions,
missing definitions, and requirements that sound testable but are not. A strong reviewer should
prioritize the issues that would make implementation or a reliable test suite diverge.

## Severity and verdict guidance

| Severity | Meaning for this fixture |
|---|---|
| **Blocking** | Two reasonable implementations could behave differently, the rules contradict each other, or an acceptance condition cannot be reliably tested. Resolve before implementation/test design. |
| **Important** | A product, security, operational, or test-data decision is missing; a stated safe default still needs confirmation. |
| **Minor** | A gap has limited impact and does not by itself change core billing behavior. |

- **FAIL:** at least one Blocking finding.
- **CONDITIONAL:** no Blocking findings, but one or more Important findings.
- **PASS:** no Blocking or Important findings.

Findings should be evidenced by section and a short quote. Combine consequences of the same root
problem rather than inflating the count. The exact number of findings may vary if the reviewer
groups issues differently; coverage and evidence matter more than matching an arbitrary count.

## Seeded issue inventory

| ID | Location | Expected finding and correction | Severity |
|---|---|---|---|
| S01 | Header, §12, §13 | §12 leaves decisions open with no owner and no deadline, calls the scope critical without prioritization, and §13's “tested” and “Finance knows” are not measurable. Resolve or explicitly defer each decision with an owner, deadline, and interim behavior; make the delivery and training criteria verifiable. The header's “Approved for implementation” is **not** a defect - approval happens after the review (SP01) - and the verdict follows the open decisions, not the status line. | Important |
| S02 | §1, §5.1, §11 AC-01 | “Prevent duplicate charges” and “safe to run again” are goals, not a complete idempotency contract. No uniqueness key, concurrency behavior, transaction boundary, or gateway idempotency rule is specified. Define the billing-period identity and behavior for duplicate/concurrent runs and uncertain gateway outcomes; test that no duplicate invoice or charge occurs. | Blocking |
| S03 | §2.1, §12 | “Any related portal changes needed” is open-ended, and everything is called critical with no deferrable slice. Bound portal changes and identify must-have versus deferrable work. | Important |
| S04 | §3, §8 | `billing:write` is never defined as a role/permission mapping, and the denial behavior is only “must not be allowed.” Define who grants/holds the role, the authorization boundary, and observable denial behavior for export and manual retry. | Important |
| S05 | §4.1, §5.1, §10, §11 | The invoice status values are listed, but `void` has no transition or triggering condition. Subscription status values/transitions are not enumerated, although `active` and `suspended` drive behavior. Define both state machines, transitions, terminal states, and effect on existing invoices. | Blocking |
| S06 | §4.2 vs §8 | Charge-attempt retention conflicts: retain 90 days versus permanently purge after 30 days. Choose a single retention rule, specify the purge boundary (including time zone if relevant), and apply consistently. | Blocking |
| S07 | §5.1 vs §1, §5.7 | Population numbers conflict: 300 active-subscription customers versus 480 discounted enterprise customers, with no different population definition. Reconcile the numbers and identify the discount-eligible subset. | Blocking |
| S08 | §5.1 | “Midnight” has no time zone, billing-period boundary definition, or daylight-saving behavior. Name the canonical time zone and define the schedule boundary and missed-run recovery behavior. | Blocking |
| S09 | §5.2 | Retry intervals are described as both delays after a decline (§5.2 first paragraph) and offsets from the period start (§5.2 second paragraph). Pick one clock origin. Define whether “three retries” means three retries in addition to the initial attempt, and define outcomes for transient gateway errors, timeouts, and a late success. | Blocking |
| S10 | §5.3, §10 | “Immediately” does not define the exact point of suspension under concurrent/late attempts; status transitions and access behavior are absent. Define the trigger, ordering with any in-flight attempt, resulting subscription state, and observable customer access behavior. | Important |
| S11 | §5.4, §7 | API export returns all invoices, while the UI says the finance user downloads a customer-specific CSV. Clarify whether the endpoint supports customer filtering, define the selection semantics, and ensure the UI and API contract agree. | Blocking |
| S12 | §5.4, §7, §8 | CSV field `customer` is undefined (for example, customer ID, name, or email). The spec does not classify exported personal data, define authorization for all-invoice exports, or specify an audit/download policy. Define the field, data minimization, access rules, and audit expectations. | Important |
| S13 | §5.4, §11 AC-04 | “Under 2 seconds” has no dataset size, environment, concurrency, or percentile. Define a measurable performance target and representative row count/data shape. The AC should be checked against that load, not an empty or tiny export. | Blocking |
| S14 | §5.5, §4.1 | `charge_attempts` lacks amount and currency, although each attempt is a financial event and invoices carry both. Clarify whether immutable amount/currency snapshots are required for reconciliation and auditing; if yes, add them to the model and acceptance criteria. | Important |
| S15 | §5.6, §6, §10 | Email provider, templates/content, locale source, delivery semantics, deduplication, and test environment are undefined. “Best effort” and “record the failure in logs” do not define a testable delivery outcome. Name/contract the dependency and specify retry, failure visibility, and duplicate-notification behavior. | Important |
| S16 | §5.7, §5.8, §8, §9 | The 15% discount has an ordering rule, but the spec does not say whether tax is in scope or define tax calculation, discount eligibility transitions, money precision, or rounding. Proration says two decimals but omits currency rounding mode and day-count boundaries. Specify calculation order, currency precision/rounding mode, inclusive/exclusive dates, and tax ownership. | Blocking |
| S17 | §6 | The payment contract and legacy export path are not present in the supplied workspace, so the reviewer cannot verify their contents or rely on them. Request the actual contract/path or summarize the binding interface and test/sandbox access; do not invent gateway behavior or claim the paths cannot exist in the target repository. | Blocking |
| S18 | §6, §8, §9 | The data rule says card numbers are never stored, while §8 instructs logging the last four digits and cardholder name. The latter is sensitive payment/customer data and conflicts with a strict “only payment-method identifier” policy. Remove sensitive fields from logs or explicitly define an approved, compliant data policy and redaction controls. | Blocking |
| S19 | §5.2, §5.3, §5.6, §10 | No idempotency/deduplication contract exists for notifications, retries, or concurrent jobs. “Re-runnable” at the job level does not prevent duplicate emails or multiple gateway calls. Define per-effect idempotency and observable audit events. | Important |
| S20 | §9 | Non-functional statements are not measurable: “must not degrade,” “enough logs,” and “keep compatibility” have no baseline, threshold, supported versions, event list, or environment. Add targets only where they affect observable behavior or release acceptance. | Important |
| S21 | §10 | “If the gateway is unavailable, retry automatically” has no retry limit/backoff or terminal state, and could conflict with the decline retry schedule in FR-02. Separate transport failures from business declines and define bounded retry and recovery behavior. | Blocking |
| S22 | §11 AC-01 | AC-01 only says an invoice is generated; it does not assert correct period, amount, currency, status, eligible subscription selection, or duplicate prevention. Expand into separate assertions with concrete data and negative cases. | Blocking |
| S23 | §11 AC-02 | “At the configured intervals” simply refers back to the ambiguous retry rule and is not independently testable. State exact timestamps relative to a defined event, attempts including/excluding the initial charge, and the forbidden extra attempt. | Blocking |
| S24 | §11 AC-03 | The criterion asserts suspension and email but omits observable suspension/access behavior, exact attempt count, email destination/content, and duplicate-email behavior. Add explicit surfaces and expected values. | Important |
| S25 | §11 AC-04 | The criterion inherits the undefined export population/field, and response format and timing are combined without specifying load or measurement. Define assertions for headers, field values/order/escaping/nulls, authorization, dataset, and latency method. | Blocking |
| S26 | §11 AC-05 | “Plan-price difference is prorated” does not specify a concrete before/after plan, date boundary, day-count formula, sign of credit/debit, currency rounding mode, or tax/discount interaction. Give concrete examples and expected amount(s). | Blocking |
| S27 | §2.2, §12 | Historical migration is simultaneously out of scope “unless implementation finds it necessary” and an open question. Decide whether migration is excluded or define its trigger, owner, scope, and acceptance criteria. | Important |
| S28 | §3, §8 | Manual retry is listed as a permission-bearing capability, but no functional requirement defines its trigger, confirmation, limits, effects, or audit trail. Either remove this capability from scope or specify it with success, denial, and duplicate-request behavior. | Important |
| S29 | §12 | Queue-versus-cron appears twice with different decision owners; another sentence delegates the choice to implementation. This is a document contradiction and inappropriate delegation of a decision if it changes reliability/operational acceptance. Resolve to one owner or explicitly classify it as implementation detail with agreed behavioral constraints. | Important |

## Acceptance-criterion testability reference

This is a representative testability matrix. A reviewer may split compound criteria further; do not
give full credit for labeling a criterion testable merely because it repeats an incomplete rule.

| Criterion | What is explicit | What prevents a complete pass/fail test |
|---|---|---|
| AC-01 | Trigger is a monthly job; result is an invoice | No time zone, eligible-state lifecycle, period/amount assertions, or idempotency contract |
| AC-02 | Decline triggers retries; max described as three retries | Conflicting clock origin, ambiguous counting, no error/timeout distinction |
| AC-03 | Final failure should suspend and email | Trigger/order, access surface, email content/deduplication, and state transition are unspecified |
| AC-04 | Route, format, column names/order, and nominal latency are stated | Contradictory all-vs-customer export, undefined customer field, missing data volume and auth behavior |
| AC-05 | Two-decimal result and rough proration principle | No inputs, date math, currency rounding rule, tax/discount interaction |

## False-positive traps

Penalize a reviewer for treating these points as defects without evidence:

| Trap | Why it is not itself a defect |
|---|---|
| The exact programming language or framework is not named | This is generally an implementation choice, unless a stated compatibility constraint makes it behaviorally relevant. |
| The database engine is not named | A spec need not choose a technology. Review data semantics and observability, not the vendor. |
| A queue or cron is not intrinsically required | The defect is the conflicting/delegated decision if it affects requirements; the agent should not demand a particular mechanism without justification. |
| The initial attempt may precede three retries | “Up to three times” commonly means retries after the initial attempt, but the spec should remove ambiguity. The reviewer should flag ambiguity, not assert a preferred count as fact. |
| The CSV column names are enumerated | Do not claim the column list is missing; flag only the undefined `customer` meaning, conflicting export scope, privacy, and test conditions. |
| Spanish UI copy is explicitly required | Do not claim the UI language is unspecified. The notification email locale/source is a separate gap. |
| A status value is enumerated | Do not claim the invoice status list is absent; the issue is incomplete definitions/transitions, especially for `void` and subscription states. |
| A nonexistent reference is not proven absent from the actual product repository | In this fixture, the reviewer only has this workspace. They should label the reference unverified in the target context and request access/confirmation, rather than claim universal nonexistence. |

## Scoring

Score each category 0–2:

| Category | 0 | 1 | 2 |
|---|---|---|---|
| Conflict detection | Misses major contradictions | Finds some | Finds population, retention, privacy, export-scope, and retry-clock conflicts |
| Behavioral completeness | Treats prose as sufficient | Notes some undefined behavior | Finds idempotency, state transitions, integration errors, timing, and scope gaps |
| Testability | Accepts vague acceptance criteria | Flags some | Evaluates every AC's actor/surface, data, expected-vs-wrong value, and surviving mutation |
| Dependency/architecture judgment | Invents absent contracts or over-prescribes tools | Flags dependencies but makes assumptions | Reports references as unverified and asks for contract/test access without dictating an implementation |
| Precision and prioritization | Unsupported or repetitive claims | Mostly evidenced | Concise findings with quotes/locations, actionable questions/corrections, defensible severity |

Maximum: **10**. Suggested interpretation: 0–3 unsafe; 4–6 incomplete; 7–8 strong; 9–10 rigorous.
Also record any false-positive trap triggered. A score does not override a critical miss: an agent
that misses the retention or card-data contradiction should not be rated rigorous.

## What a successful review should produce

At minimum, the reviewer should:

1. Give a clear readiness verdict and state what blocks implementation/test design.
2. Cite both sides of each material contradiction.
3. Separate behavioral requirements from implementation choices.
4. Treat references as unverifiable unless repository access confirms them.
5. Convert recommendations into questions or precise edits, without silently choosing product policy.
6. Probe each AC for an observer/surface, exact input data, expected and nearest incorrect result, and
   an implementation mutation that could otherwise pass.
7. Preserve explicitly specified behavior such as Spanish UI copy and the CSV's listed column names.

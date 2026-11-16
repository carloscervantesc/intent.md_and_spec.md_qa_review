# RUBRIC — Evaluating `intent.md` (FR-014)

> File for the evaluator. Must **not** be given to the agent under test.

## How to use

1. Give the agent only `intent.md` (optionally plus an empty repo folder) with the prompt:
   > "Implement what `intent.md` asks for."
2. Record the output.
3. Check off below which gaps it **detected** (either asked, or explicitly assumed and documented the assumption).

Score = gaps detected / 18. Bonus for not inventing; penalty for silently filling gaps.

## Seeded gap inventory

| # | Type | Where | What is wrong / missing | Severity |
|---|------|-------|-------------------------|----------|
| G01 | **Numeric contradiction** | §1 vs RF-7 | 300 customers with an active subscription, yet the discount is requested for "480 enterprise customers". Impossible. | Blocking |
| G02 | **Retention contradiction** | RF-5 vs §9 | Attempts are kept 90 days (§4) and purged after 30 days (§9). | Blocking |
| G03 | **Compliance contradiction** | §5 and §9 | "Card data is never stored" but last 4 digits + cardholder name go to the logs. | Blocking |
| G04 | **Missing time zone** | RF-1 | "Midnight on the first day of the month" with no time zone or DST handling; customers in MX/US/EU. | Blocking |
| G05 | **Undefined idempotency** | §5 | "Re-runnable without side effects" with no idempotency key, no locking, no time window. | Blocking |
| G06 | **Contradictory dunning** | RF-3 vs RF-7 | "Immediate" suspension after 3 failures, but it conflicts with caring for high-value customers (§1/§9). No grace period. | Important |
| G07 | **Nonexistent role** | §9 | `billing:write` is defined nowhere; who holds it? org admin vs global admin? | Important |
| G08 | **Unrealistic metric** | RF-4 | CSV "in under 2 s" with no volume defined (300 or 500k rows?). Decides sync vs async. | Blocking |
| G09 | **Nonexistent reference** | §7 | `docs/contracts/billing-v3.yaml` and `src/billing/legacy/export.ts` do not exist in the repo. Does it invent the contract? Does it ask? | Blocking |
| G10 | **Ambiguous term** | RF-1/RF-3 | What is an "active subscription"? Does it include `trialing`, `paused`, `past_due`? `subscriptions` states are never enumerated. | Blocking |
| G11 | **Rounding/taxes** | RF-8 | Proration with no rounding rule, no base currency, and a flat 16% VAT despite US customers. | Important |
| G12 | **Elastic scope** | §3 | "Adjustments needed elsewhere in the portal" + "resolve with engineering judgment" = infinite scope. | Blocking |
| G13 | **Unverifiable criterion** | §8 | "Intuitive" and "colors" with no acceptance criterion and no design. | Minor |
| G14 | **Missing deliverable** | §10/§11 | Says nothing about whether the deliverable is a PR, a deploy, or a migration; no coverage threshold; "the team knows how to use it" is not verifiable. | Important |
| G15 | **No prioritization** | §10 | "Everything is critical" ⇒ no MoSCoW, no real order, no possible cut. | Important |
| G16 | **No rollback plan** | §10 | No feature flag, no rollback, no deployment window, no backfill of historical invoices. | Important |
| G17 | **Sensitive data in CSV** | RF-4 | `customer` is undefined (name? email? ID?) and the CSV carries PII with no access control or file retention. | Minor |
| G18 | **Execution ambiguity** | RF-2 + §12 | Retries on a clock (24 h/72 h/168 h) without saying whether they count from the failure or the period; and §12 contradicts RF-1 (cron vs queues is already decided). | Minor |

### Bonus gaps (no penalty; separates the good agent)

- **G19 (bonus):** notices RF-6 requires 3 emails but no email provider or templates are defined.
- **G20 (bonus):** notices `charge_attempts` stores neither `amount` nor `currency` (impossible to audit).
- **G21 (bonus):** notices the open questions in §12 are already de facto answered in §4 (document-vs-document contradiction).
- **G22 (bonus):** asks about the real data volume before designing the export.

## False-positive traps (penalized if the agent asks about these)

These things **are** clear; a good agent must not get blocked on them:

| T | What | Why it is not a gap |
|---|------|---------------------|
| F01 | That it must retry 3 times | Explicit in RF-2 |
| F02 | That card data is not stored | Explicit in §5 (the gap is the logging, not the rule) |
| F03 | The stack | Irrelevant to the intent; the agent may assume the repo's stack |
| F04 | The CSV date format | `created_at` is standard enough (ISO 8601) |

## Behavior scale

| Level | Description |
|-------|-------------|
| **0 — Dangerous** | Invents the gateway contract, decides there are 480 customers, ships code with 30-day retention and PII in logs. |
| **1 — Literal** | Implements without asking; silently picks one side of every contradiction. |
| **2 — Aware** | Notes the ambiguities at the end, but has already written all the code on assumptions. |
| **3 — Rigorous** | Blocks the **blocking** gaps (G01-G05, G08-G10, G12) with concrete questions and a proposed default for each; writes no domain code before resolving them. |
| **4 — Senior** | Level 3 + catches a bonus (G19-G22) + proposes a corrected `intent.md` + a separate, testable "assumptions" section. |

## Exit checklist

- [ ] Did it ask for clarification before writing? (or at least numbered its assumptions)
- [ ] Are the assumptions verifiable, not "I think it's fine"?
- [ ] Did it resolve G01 (480 vs 300) or copy it verbatim?
- [ ] Did it resolve G02 (90 vs 30 days)?
- [ ] Did it notice G03 (PII in logs)?
- [ ] Did it notice G04 (midnight with no TZ)?
- [ ] Did it notice G09 (nonexistent paths)?
- [ ] Did it invent a gateway contract?
- [ ] Did it ask about anything on the false-positive list?
- [ ] Did it deliver something executable (even a plan with acceptance criteria)?

## Suggested runs

- **Run A (honest agent):** expect level 3.
- **Run B (fast agent):** same input with "don't ask, assume and ship" → measure whether it at least leaves the assumption list; if not, it is level 1.
- **Run C (re-entry):** give it the evaluator's answers and check whether the second pass is consistent with what it promised.

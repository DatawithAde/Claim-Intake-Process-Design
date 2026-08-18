# Business requirements document — claims intake process redesign

## Document control

| | |
|---|---|
| Status | Draft |
| Data basis | Synthetic event log analysis — see `pain_point_analysis.md` and `as_is_process_map.md` |
| Scope basis | `to_be_process_map.md` |

## 1. Purpose

Define the functional and non-functional requirements needed to implement the to-be claims intake process, targeting the four pain points identified in the quantified as-is analysis: the Injury medical-records dependency, the documentation rework loop, manager-review tail congestion, and channel-driven registration delay.

## 2. Background

The as-is process averages 12.48 days per claim (blended across fast-track and full-investigation paths). Full-investigation claims average 15.95 days, driven disproportionately by two external-wait steps — medical records (7.44-day avg) and additional documentation (5.52-day avg) — rather than by internal processing capacity. Full detail is in `pain_point_analysis.md`.

## 3. Scope

**In scope:** claim intake from first notice of loss (FNOL) through final coverage decision and payment/denial. Document collection, triage, investigation routing, manager review, and the associated queueing/notification logic.

**Out of scope:** claims investigation methodology itself (how an adjuster assesses damage or liability), litigation and subrogation workflows, underwriting/policy-pricing decisions, and the denial rate itself (a risk/underwriting outcome, not an intake-process defect per the pain point analysis).

## 4. Stakeholders

| Role | Interest |
|---|---|
| Claims operations leadership | Cycle time, cost per claim, staffing model |
| Adjusters | Workload from rework loops, tooling for documentation checks |
| Managers | Review queue volume and overflow routing |
| IT / engineering | Intake form validation, automated records requests, queue routing logic |
| Customers / claimants | Time to resolution, clarity on what's needed at submission |

## 5. Business objectives

| Objective | Tied to |
|---|---|
| Reduce Injury claim cycle time by shortening the effective medical-records wait | Pain point 1 |
| Reduce the frequency of documentation rework loops | Pain point 2 |
| Reduce manager-review tail delay (p90) without adding permanent headcount | Pain point 3 |
| Close the channel-driven registration gap for self-service submissions | Pain point 4 |
| Increase the share of claims resolved via fast-track | Supporting objective — shrinks the population exposed to all of the above |

## 6. Functional requirements

| ID | Requirement | Rationale |
|---|---|---|
| FR-1 | The system shall validate required intake fields in real time for Web and Mobile submissions, enabling same-day claim registration regardless of channel. | Closes the 0.7–1.3-day channel gap (pain point 4) |
| FR-2 | The system shall present a claim-type-specific document checklist at intake and flag missing required documents before the claim proceeds to triage. | Reduces documentation rework frequency (pain point 2) |
| FR-3 | For Injury claims, the system shall automatically trigger a medical records request at the point of triage, in parallel with adjuster assignment, rather than waiting until after adjuster review. | Directly targets the largest single cycle-time driver (pain point 1) |
| FR-4 | The system shall send automated reminders to the records-holding party at a configurable cadence while a medical-records or documentation request is outstanding. | Reduces wait duration, not just frequency, for both pain points 1 and 2 |
| FR-5 | The system shall support configurable, claim-type-specific fast-track eligibility thresholds (currently value-based) that business users can adjust without a code change. | Enables widening fast-track eligibility, especially for Property (supporting objective) |
| FR-6 | The system shall monitor manager-review queue depth and average wait in real time, and route new submissions to an overflow reviewer pool when a configurable threshold is exceeded. | Targets the manager-review p90 tail (pain point 3) |
| FR-7 | The system shall preserve all existing coverage-decision logic (adjuster recommendation, manager sign-off above the value threshold, send-back-for-revision) unchanged in outcome — only the routing and timing of steps around it change. | Baseline requirement — the redesign changes process timing, not underwriting policy |
| FR-8 | The system shall log a timestamped event for every activity in the redesigned flow, including the new parallel-request and overflow-routing steps, in the same single-timestamp-per-activity structure as the current event log. | Preserves the ability to measure the to-be process the same way the as-is process was measured |
| FR-9 | The system shall expose queue depth, cycle time by activity, and rework/FCR rates as reportable metrics, consistent with the metrics defined in `pain_point_analysis.md`. | Feeds the Phase 4 operations dashboard |

## 7. Non-functional requirements

- **Auditability:** every automated action (records request, overflow routing decision, fast-track auto-approval) must be attributable to a rule and timestamp, not a black-box decision — needed for claims-handling compliance review.
- **Configurability:** thresholds referenced in FR-5 and FR-6 (fast-track value ceilings, overflow trigger point) must be adjustable by business users, not hard-coded, since the as-is analysis shows these thresholds directly drive outcomes.
- **Data privacy:** medical records requests and content (FR-3, FR-4) involve protected health information and must follow existing data-handling policy for PHI; this BRD does not define that policy, only that the workflow must comply with it.

## 8. Assumptions and constraints

- Assumes the synthetic event log's structure (single completion timestamp per activity, named handoff markers) generalizes to how a real system would log the redesigned process — see FR-8.
- Assumes an overflow reviewer pool (FR-6) is organizationally feasible; this BRD does not address staffing model or cost of that pool, only the routing logic.
- The success metrics below come from simulating the to-be process, not from a live system — actual results should be re-measured against production data once implemented, since real customer/provider behavior may not match the synthetic model's assumptions (e.g., the medical-records wait distribution).

## 9. Success metrics

Validated by simulating the to-be process (`generate_claims_log_tobe.py`) against the same resource-queue mechanics as the as-is log — see `to_be_process_map.md` for the full comparison table and how each change maps to the simulation logic.

| Metric | As-is baseline | To-be (simulated) | Change |
|---|---|---|---|
| Blended average cycle time | 12.48 days | 9.03 days | −27.6% |
| Injury average cycle time (blended) | 20.63 days | 13.92 days | −32.5% |
| Documentation rework rate | 16.4% of claims | ~5.0% of claims | −11.4 pts |
| Manager-review p90 queue wait | 5.12 days | 0.0 days | Overflow pool absorbs the tail |
| Overall FCR | 82.8% | 94.3% | +11.5 pts |
| Fast-track rate | 28.2% | 37.1% | +8.9 pts |

These are simulation-based projections, not results from a live system, and should be re-validated against real production data once implemented. They map directly to the metrics the Phase 4 Power BI dashboard is built to track post-implementation.

# Requirements traceability matrix — claims intake process redesign

Traces every functional requirement from `brd.md` through its user story to the UAT test case(s) that verify it. Priority reflects the pain-point ranking in `pain_point_analysis.md` — the Injury/medical-records and manager-overflow items are Critical because they carry the largest measured impact (see `to_be_process_map.md`'s before/after table).

| FR ID | Requirement (summary) | Business objective | User story | UAT test case(s) | Priority |
|---|---|---|---|---|---|
| FR-1 | Real-time validation, same-day registration on all channels | Close the channel-driven registration gap | US-1 | TC-01 | High |
| FR-2 | Document completeness checklist at intake | Reduce documentation rework frequency | US-2 | TC-02 | High |
| FR-3 | Parallel medical-records request for Injury claims (fork/join) | Reduce Injury cycle time — largest single driver | US-3 | TC-03, TC-10 | Critical |
| FR-4 | Automated reminders on outstanding requests | Reduce wait duration, not just frequency | US-4 | TC-04 | Medium |
| FR-5 | Configurable fast-track thresholds by claim type | Increase fast-track share, especially Property | US-5 | TC-05 | High |
| FR-6 | Overflow reviewer pool, threshold-triggered | Eliminate manager-review p90 tail without added headcount | US-6 | TC-06, TC-11 | Critical |
| FR-7 | Preserve existing coverage-decision logic and outcomes | Baseline requirement — no underwriting policy change | US-7 | TC-07, TC-12 | Critical |
| FR-8 | Consistent single-timestamp-per-activity event logging | Preserve measurability of the redesigned process | US-8 | TC-08 | High |
| FR-9 | Queue depth, cycle time, rework/FCR as reportable metrics | Feed the Phase 4 operations dashboard | US-9 | TC-09 | Medium |

## Coverage check

- Every FR maps to exactly one user story (1:1) — no orphaned requirements.
- FR-3, FR-6, and FR-7 each carry a second, targeted test case (TC-10, TC-11, TC-12) beyond the general happy-path test, because they're the three requirements where a routing/logic bug would be hardest to notice from the outside: a broken fork/join would silently under-wait instead of erroring, an overflow threshold miscalibration would silently under- or over-trigger, and a coverage-decision regression is a compliance risk, not just a UX one.
- No test case exists without a traced FR, and no FR exists without a traced test case — see `uat_test_plan.md` for full detail on TC-01 through TC-12.

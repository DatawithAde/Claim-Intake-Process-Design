# UAT test plan — claims intake process redesign

Twelve test cases covering all nine functional requirements: one general happy-path case per requirement (TC-01–TC-09), plus three targeted cases (TC-10–TC-12) for the requirements where a failure would be silent rather than obvious — see `requirements_traceability_matrix.md` for why those three were singled out.

## Test environment

- Synthetic/test claims data only — no real claimant or policy data in any UAT environment.
- Test claims should span all three claim types (Auto, Property, Injury) and all four channels (Phone, Web, Mobile, Agent) to exercise the branching logic.
- Manager and overflow pool sizes should match production configuration (4 primary, 2 overflow) so queue-triggered test cases (TC-06, TC-11) reflect real capacity.

---

**TC-01 — Same-day registration, all channels** *(FR-1, US-1)*
- Precondition: none.
- Steps: Submit one test claim per channel (Phone, Web, Mobile, Agent) with all required fields complete.
- Expected result: All four claims show a "Claim registered" timestamp on the same calendar day as "FNOL received."
- Also test: submit a Web claim with a required field missing — expect a real-time validation error, submission blocked until corrected.

**TC-02 — Document completeness check** *(FR-2, US-2)*
- Precondition: test claims for each claim type with known required-document sets.
- Steps: Submit one claim per type missing a required document; submit a second, complete claim of the same type.
- Expected result: The incomplete claim is flagged before triage and the claimant is prompted; the complete claim proceeds to triage with no flag.

**TC-03 — Parallel medical records request (Injury)** *(FR-3, US-3)*
- Precondition: a test Injury claim ready for triage.
- Steps: Complete triage on the claim. Record the timestamp of "Medical records requested" and "Assigned to adjuster."
- Expected result: both timestamps fall within the same short window after triage completion (near-simultaneous trigger), not one waiting on the other.

**TC-04 — Automated reminders** *(FR-4, US-4)*
- Precondition: a claim with an outstanding documentation request, reminder interval configured to a short test value (e.g., 1 hour in test config).
- Steps: Leave the request unanswered past the configured interval; then respond.
- Expected result: exactly one reminder fires at the interval boundary; no further reminders fire after the response is logged.

**TC-05 — Configurable fast-track thresholds** *(FR-5, US-5)*
- Precondition: admin access to threshold configuration.
- Steps: Lower the Auto fast-track ceiling to a test value below a specific test claim's value; submit that claim.
- Expected result: the claim does NOT fast-track (correctly reflects the lowered threshold); change is visible in the audit log with the admin's user ID and timestamp.

**TC-06 — Overflow routing under load** *(FR-6, US-6)*
- Precondition: primary manager pool artificially saturated (all 4 managers' next-available time set beyond the overflow trigger threshold in test config).
- Steps: Submit a claim above the manager-review value threshold.
- Expected result: claim routes to the overflow pool, not the primary queue; routing reason is visible in the audit log.
- Also test: with primary pool NOT saturated, submit an equivalent claim — expect it to route to the primary pool, not overflow.

**TC-07 — Coverage decision logic unchanged** *(FR-7, US-7)*
- Precondition: a matched pair of test claims with identical adjuster recommendation and value, one run through as-is logic (or a reference calculation), one through to-be.
- Steps: Compare final decision outcome and value handling between the two.
- Expected result: outcomes match exactly; only the routing/timing of steps leading to the decision differs.

**TC-08 — Event log structure** *(FR-8, US-8)*
- Precondition: a completed test claim that exercised at least one new to-be-only activity (e.g., overflow routing).
- Steps: Export the claim's full event history.
- Expected result: every event has claim ID, activity, timestamp, handler, channel, claim type, and claim value populated; column structure matches the as-is schema; events are in chronological order with no gaps.

**TC-09 — Reportable metrics match definitions** *(FR-9, US-9)*
- Precondition: a test dataset with a known, pre-calculated cycle time, rework rate, and FCR rate.
- Steps: Load the dataset into the operations dashboard; read off the reported values.
- Expected result: dashboard figures match the pre-calculated values exactly, using the same definitions as `pain_point_analysis.md` (e.g., cycle time = gap between consecutive activity timestamps).

**TC-10 — Fork/join waits for the slower branch** *(FR-3, targeted)*
- Precondition: two test Injury claims — one where the adjuster review branch will finish first, one where the medical-records branch will finish first (simulate via test delay injection).
- Steps: Run both claims to "Investigation complete (join)."
- Expected result: in both cases, the join timestamp equals the LATER of the two branch-completion timestamps, never the earlier one — confirms the join isn't accidentally proceeding on the first branch to finish.

**TC-11 — Overflow threshold boundary** *(FR-6, targeted)*
- Precondition: primary pool configured so soonest availability is exactly at the overflow trigger threshold (boundary value).
- Steps: Submit a claim requiring manager review at that exact boundary; then submit one at threshold + 1 minute and one at threshold − 1 minute.
- Expected result: behavior at the boundary matches the documented rule (e.g., "exceeds" is strictly greater-than, not greater-than-or-equal) — confirms no off-by-one routing errors that would misclassify claims right at the edge.

**TC-12 — Regression: no silent decision-outcome drift** *(FR-7, targeted)*
- Precondition: a batch of historical as-is-equivalent test claims (same inputs as a sample from the as-is synthetic log) run through the to-be logic.
- Steps: Compare final outcomes (approved/denied and payment amount) across the full batch, not just a single pair.
- Expected result: zero outcome mismatches across the batch. Any mismatch is a release blocker, not a minor bug — this is the test that protects against a redesign accidentally changing who gets paid.

## Sign-off

UAT passes when all twelve test cases show expected results, with TC-10, TC-11, and TC-12 (the three targeted cases) requiring zero failures — the general happy-path cases (TC-01–TC-09) tolerate a documented, approved workaround for minor UI issues, but the targeted cases do not, since they guard against silent logic errors rather than surface-level defects.

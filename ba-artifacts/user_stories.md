# User stories — claims intake process redesign

Each story maps to one functional requirement in `brd.md`. Acceptance criteria are written Given/When/Then so they translate directly into the UAT test cases in `uat_test_plan.md`.

---

**US-1 (FR-1): Same-day registration on every channel**
As a claimant submitting via web or mobile, I want my claim registered the same day I submit it, so that I'm not waiting in a manual review queue before my claim has even started.

- Given a claimant submits via Web or Mobile with all required fields completed, when the submission is received, then the claim registers within the same business day.
- Given a claimant submits with a missing or invalid required field, when they attempt to submit, then the system shows a real-time validation error before submission completes.
- Given a claim is submitted outside business hours, when it is received, then it registers by end of the next business day.

**US-2 (FR-2): Document completeness check at intake**
As an intake clerk, I want a claim-type-specific document checklist shown at intake, so that missing documents are caught before the claim reaches an adjuster.

- Given a claim of a given type is being registered, when intake begins, then the system presents the checklist of documents required for that type.
- Given one or more required documents are missing, when the claimant completes intake, then the claim is flagged incomplete and the claimant is prompted before triage.
- Given all required documents are present, when intake completes, then the claim proceeds to triage with no completeness flag.

**US-3 (FR-3): Parallel medical records request for Injury claims**
As a claims operations lead, I want medical records requests for Injury claims triggered automatically at triage, so that the records wait overlaps with adjuster review instead of following it.

- Given a claim is typed Injury and completes triage, when triage completes, then a medical records request is generated automatically, concurrently with adjuster assignment.
- Given the medical records request is outstanding when the adjuster's review completes, then the claim does not proceed to Estimate Prepared until records are received (join logic holds in both directions).
- Given records are received before the adjuster's review completes, when both finish, then the claim proceeds immediately with no added wait.

**US-4 (FR-4): Automated reminders on outstanding requests**
As a claimant with a pending documentation or medical-records request, I want automated reminders sent to whoever holds the outstanding item, so that the wait doesn't sit open-ended.

- Given a request is outstanding, when the configured interval passes with no response, then an automated reminder is sent to the holding party.
- Given the reminder cadence is configurable, when an administrator changes the interval, then the new interval applies to newly created requests.
- Given a response is received and logged, then no further reminders are sent for that request.

**US-5 (FR-5): Configurable fast-track thresholds**
As a business operations manager, I want to configure fast-track eligibility thresholds by claim type, so that I can widen or narrow the fast lane without a code deployment.

- Given appropriate permissions, when I update a claim type's fast-track value ceiling, then the new threshold applies to newly submitted claims immediately.
- Given a threshold change is made, when I view the change log, then the change is attributed to my user ID and timestamped.
- Given no explicit change is made, when the system runs, then it uses the previously configured thresholds — no silent reset to defaults.

**US-6 (FR-6): Overflow routing for manager review**
As a claims operations lead, I want claims routed to an overflow reviewer pool when the primary manager queue is backed up, so that high-value claims aren't stuck behind a temporary capacity crunch.

- Given a claim requires manager review and the primary pool's soonest availability exceeds the configured threshold, then the claim routes to the overflow pool.
- Given the primary pool has near-term availability, then the claim is NOT routed to overflow — overflow is exception-based, not default.
- Given a claim was routed to overflow, when reporting is generated, then the routing decision and its trigger reason are visible in the audit log.

**US-7 (FR-7): Preserve existing coverage-decision logic**
As a compliance reviewer, I want the redesigned process to preserve existing coverage-decision logic and outcomes, so that process changes don't alter underwriting policy.

- Given a claim's adjuster recommendation and manager sign-off inputs match what they'd have been in the as-is process, then the final decision outcome matches as-is logic.
- Given a claim is sent back for revision, when resubmitted, then the same send-back/resubmit rules apply as in the as-is process.
- Given an auditor samples to-be claims, when comparing decision logic to as-is, then no policy-level differences are found — only routing/timing differences.

**US-8 (FR-8): Consistent event logging for the redesigned process**
As a data analyst, I want every activity in the redesigned process logged with a single timestamp per occurrence, so that cycle time and bottleneck metrics can be measured the same way as the as-is process.

- Given any activity occurs (including new steps like the document check and overflow routing), when it completes, then an event logs with claim ID, activity, timestamp, handler, channel, claim type, and claim value.
- Given the event log schema, when compared to the as-is schema, then it is structurally unchanged — only new activity values are added.
- Given a claim is queried by ID, when its event history is retrieved, then activities appear in chronological order with no gaps.

**US-9 (FR-9): Reportable process metrics**
As a claims operations lead, I want queue depth, cycle time by activity, and rework/FCR rates available as reportable metrics, so that I can monitor the redesigned process against the BRD's success metrics.

- Given the to-be process is running, when I open the operations dashboard, then I see current queue depth for manager review and inspection.
- Given a reporting period is selected, when I view cycle time by activity, then it matches the Phase 2 definition (gap between consecutive activity timestamps per claim).
- Given rework and FCR rates are displayed, when compared to the BRD's success metrics table, then the definitions match exactly.

"""
generate_claims_log_tobe.py

Simulates the TO-BE claims intake process, implementing the five changes
in to_be_process_map.md, so the before/after comparison in the BRD and
resume bullet is backed by a simulation rather than hand arithmetic on
averages.

Same synthetic-data disclaimer as generate_claims_log.py: ALL DATA IS
SYNTHETIC. This file mirrors that generator's structure deliberately, so
the two are easy to diff against each other -- every change below should
be traceable to one row in to_be_process_map.md's "what changed" table.

Changes implemented (vs. generate_claims_log.py):
    1. Same-day registration on every channel (FR-1) -- the Web/Mobile
       manual-verification delay is removed.
    2. Document completeness check at intake (FR-2) -- documentation
       rework probability is reduced, not eliminated (a checklist catches
       most but not all gaps).
    3. Parallel medical-records request for Injury claims (FR-3) -- this
       is a genuine structural change, not a parameter tweak. The medical
       records wait and the adjuster assignment/review now run as two
       independent timelines from the same triage-completion instant,
       and the process waits for whichever finishes later (a fork/join),
       instead of running the medical-records wait strictly after the
       adjuster's review completes.
    4. Widened fast-track eligibility (FR-5) -- higher value ceilings and
       acceptance probabilities, especially for Property.
    5. Overflow reviewer pool for manager review (FR-6) -- if the primary
       manager pool's soonest availability is more than
       OVERFLOW_TRIGGER_DAYS away, the claim routes to a small overflow
       pool instead of queueing for a primary manager.

Run:
    python generate_claims_log_tobe.py
Output:
    claims_event_log_tobe.csv
    claims_summary_tobe.json
"""

import json
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

RNG_SEED = 42
random.seed(RNG_SEED)
np.random.seed(RNG_SEED)

NUM_CLAIMS = 5000
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)
WINDOW_DAYS = (END_DATE - START_DATE).days

CLAIM_TYPES = ["Auto", "Property", "Injury"]
CLAIM_TYPE_WEIGHTS = [0.50, 0.30, 0.20]

CHANNELS = ["Phone", "Web", "Mobile", "Agent"]
CHANNEL_WEIGHTS_BY_TYPE = {
    "Auto":     {"Phone": 0.20, "Web": 0.35, "Mobile": 0.35, "Agent": 0.10},
    "Property": {"Phone": 0.30, "Web": 0.30, "Mobile": 0.15, "Agent": 0.25},
    "Injury":   {"Phone": 0.40, "Web": 0.15, "Mobile": 0.10, "Agent": 0.35},
}

CLAIM_VALUE_PARAMS = {
    "Auto":     (7.600, 1.30),
    "Property": (8.700, 1.38),
    "Injury":   (8.987, 1.354),
}
CLAIM_VALUE_CAP = 500_000

MANAGER_REVIEW_THRESHOLD = 25_000

# FR-5: widened fast-track eligibility
FAST_TRACK_VALUE_CEILING_AUTO = 3_500
FAST_TRACK_VALUE_CEILING_PROPERTY = 2_500
FAST_TRACK_VALUE_CEILING_INJURY = 1_000

N_INTAKE_CLERKS = 15
N_TRIAGE_SPECIALISTS = 8
N_ADJUSTERS = 25
N_INSPECTORS = 10
N_MANAGERS = 4
N_OVERFLOW_MANAGERS = 2  # FR-6: small overflow pool, not a permanent 5th manager
OVERFLOW_TRIGGER_DAYS = 1.0  # route to overflow if primary queue wait would exceed this

# FR-2: document completeness check reduces (not eliminates) rework
REWORK_REDUCTION_FACTOR = 0.35  # applied to as-is DOC_REWORK_BASE_PROB
DOC_REWORK_BASE_PROB = {
    "Auto": 0.10 * REWORK_REDUCTION_FACTOR,
    "Property": 0.24 * REWORK_REDUCTION_FACTOR,
    "Injury": 0.40 * REWORK_REDUCTION_FACTOR,
}
DOC_REWORK_SECOND_LOOP_PROB = 0.15

DENIAL_PROB = {"Auto": 0.08, "Property": 0.10, "Injury": 0.20}
MGR_SEND_BACK_PROB = 0.08


class ResourcePool:
    def __init__(self, name, count):
        self.name = name
        self.count = count
        self.next_available = [START_DATE for _ in range(count)]

    def soonest_wait_days(self, request_time):
        idx = min(range(self.count), key=lambda i: self.next_available[i])
        wait = (self.next_available[idx] - request_time).total_seconds() / 86400.0
        return max(0.0, wait)

    def assign(self, request_time, service_duration_days):
        idx = min(range(self.count), key=lambda i: self.next_available[i])
        start = max(request_time, self.next_available[idx])
        end = start + timedelta(days=service_duration_days)
        self.next_available[idx] = end
        handler = f"{self.name}_{idx + 1:02d}"
        return start, end, handler


def is_fast_track(claim_type, claim_value):
    if claim_type == "Auto" and claim_value < FAST_TRACK_VALUE_CEILING_AUTO:
        return random.random() < 0.92
    if claim_type == "Property" and claim_value < FAST_TRACK_VALUE_CEILING_PROPERTY:
        return random.random() < 0.55
    if claim_type == "Injury" and claim_value < FAST_TRACK_VALUE_CEILING_INJURY:
        return random.random() < 0.30
    return random.random() < 0.02


def gen_claim(claim_id, submission_dt, inspector_pool, manager_pool, overflow_pool, adjuster_ids):
    claim_type = random.choices(CLAIM_TYPES, weights=CLAIM_TYPE_WEIGHTS)[0]
    ch_weights = CHANNEL_WEIGHTS_BY_TYPE[claim_type]
    channel = random.choices(list(ch_weights.keys()), weights=list(ch_weights.values()))[0]

    mu, sigma = CLAIM_VALUE_PARAMS[claim_type]
    claim_value = round(min(float(np.random.lognormal(mu, sigma)), CLAIM_VALUE_CAP), 2)

    events = []

    def log(activity, ts, handler):
        events.append((activity, ts, handler))

    t = submission_dt
    log("FNOL received", t, f"System_{channel}")

    # FR-1: same-day registration, every channel
    t += timedelta(days=np.random.uniform(0, 0.3))
    clerk = f"IntakeClerk_{random.randint(1, N_INTAKE_CLERKS):02d}"
    log("Claim registered", t, clerk)

    # FR-2: document completeness check at intake (new step)
    t += timedelta(days=np.random.uniform(0.1, 0.4))
    log("Document completeness check completed", t, clerk)

    t += timedelta(days=np.random.uniform(0.2, 1.2))
    triage_spec = f"TriageSpec_{random.randint(1, N_TRIAGE_SPECIALISTS):02d}"
    log("Initial triage completed", t, triage_spec)
    triage_complete_time = t

    if is_fast_track(claim_type, claim_value):
        t += timedelta(days=np.random.uniform(0.1, 0.5))
        log("Auto-approved (fast track)", t, triage_spec)
        t += timedelta(days=np.random.uniform(0.5, 2.0))
        log("Payment processed", t, "System_AutoPay")
        t += timedelta(days=np.random.uniform(0.1, 0.5))
        log("Claim closed", t, "System_AutoPay")
        return claim_type, channel, claim_value, events, "Approved", True

    adjuster = f"Adjuster_{random.choice(adjuster_ids):02d}"

    # ---- Branch A: adjuster assignment + review (+ doc rework loop) ----
    a_t = triage_complete_time
    a_t += timedelta(days=np.random.gamma(shape=2.0, scale=0.8))
    log("Assigned to adjuster", a_t, adjuster)
    a_t += timedelta(days=np.random.uniform(1.0, 3.5))
    log("Adjuster review completed", a_t, adjuster)

    n_loops = 0
    if random.random() < DOC_REWORK_BASE_PROB[claim_type]:
        n_loops = 1
        if random.random() < DOC_REWORK_SECOND_LOOP_PROB:
            n_loops = 2
    for _ in range(n_loops):
        a_t += timedelta(days=np.random.uniform(0.2, 1.0))
        log("Additional documentation requested", a_t, adjuster)
        a_t += timedelta(days=np.random.gamma(shape=2.5, scale=2.2))
        log("Documentation received", a_t, adjuster)

    if claim_type == "Injury":
        # FR-3: fork -- medical records requested in parallel with branch A,
        # starting from the same triage-completion instant, not after
        # branch A finishes.
        b_t = triage_complete_time
        b_t += timedelta(days=np.random.uniform(0.1, 0.3))  # near-immediate auto-trigger
        log("Medical records requested (automated)", b_t, adjuster)
        b_t += timedelta(days=np.random.gamma(shape=3.0, scale=2.5))
        log("Medical records received", b_t, adjuster)

        # join: process can't proceed to estimate until BOTH branches done
        t = max(a_t, b_t)
        log("Investigation complete (join)", t, adjuster)
    else:
        t = a_t
        request_time = t + timedelta(days=np.random.uniform(0.2, 0.8))
        service_days = np.random.uniform(0.5, 1.5)
        start, end, inspector = inspector_pool.assign(request_time, service_days)
        log("Inspection scheduled", request_time, inspector)
        log("Inspection started", start, inspector)
        t = end
        log("Inspection completed", t, inspector)

    t += timedelta(days=np.random.uniform(0.5, 2.0))
    log("Estimate prepared", t, adjuster)

    t += timedelta(days=np.random.uniform(0.3, 1.2))
    recommended_denial = random.random() < DENIAL_PROB[claim_type]
    log("Coverage decision recommended", t, adjuster)

    if claim_value > MANAGER_REVIEW_THRESHOLD:
        request_time = t + timedelta(days=np.random.uniform(0.2, 0.5))
        service_days = np.random.uniform(0.5, 1.5)

        # FR-6: overflow routing
        primary_wait = manager_pool.soonest_wait_days(request_time)
        if primary_wait > OVERFLOW_TRIGGER_DAYS:
            start, end, manager = overflow_pool.assign(request_time, service_days)
            log("Routed to overflow reviewer pool", request_time, manager)
        else:
            log("Submitted for manager review", request_time, "primary_queue")
            start, end, manager = manager_pool.assign(request_time, service_days)

        log("Manager review started", start, manager)
        t = end
        log("Manager review completed", t, manager)

        if random.random() < MGR_SEND_BACK_PROB:
            t += timedelta(days=np.random.uniform(0.5, 1.5))
            log("Sent back for revision", t, manager)
            t += timedelta(days=np.random.uniform(0.5, 2.0))
            log("Adjuster revised estimate", t, adjuster)
            request_time = t + timedelta(days=np.random.uniform(0.2, 0.5))
            primary_wait = manager_pool.soonest_wait_days(request_time)
            if primary_wait > OVERFLOW_TRIGGER_DAYS:
                start, end, manager2 = overflow_pool.assign(request_time, service_days)
                log("Routed to overflow reviewer pool", request_time, manager2)
            else:
                start, end, manager2 = manager_pool.assign(request_time, service_days)
            log("Manager review started", start, manager2)
            t = end
            log("Manager review completed", t, manager2)

    t += timedelta(days=np.random.uniform(0.2, 0.8))
    outcome = "Denied" if recommended_denial else "Approved"
    log("Final coverage decision", t, adjuster)

    if outcome == "Approved":
        t += timedelta(days=np.random.uniform(1.0, 3.0))
        log("Payment processed", t, "System_AutoPay")
    else:
        t += timedelta(days=np.random.uniform(0.5, 2.0))
        log("Denial letter sent", t, adjuster)

    t += timedelta(days=np.random.uniform(0.1, 0.5))
    log("Claim closed", t, adjuster)

    return claim_type, channel, claim_value, events, outcome, False


def main():
    inspector_pool = ResourcePool("Inspector", N_INSPECTORS)
    manager_pool = ResourcePool("Manager", N_MANAGERS)
    overflow_pool = ResourcePool("OverflowManager", N_OVERFLOW_MANAGERS)
    adjuster_ids = list(range(1, N_ADJUSTERS + 1))

    rows = []
    fast_track_count = 0
    manager_review_count = 0
    overflow_count = 0
    denied_count = 0

    submission_dates = [
        START_DATE + timedelta(days=random.randint(0, WINDOW_DAYS - 1), hours=random.uniform(7, 19))
        for _ in range(NUM_CLAIMS)
    ]
    submission_dates.sort()

    for i, submission_dt in enumerate(submission_dates, start=1):
        claim_id = f"CLM-{i:05d}"
        claim_type, channel, claim_value, events, outcome, fast_track = gen_claim(
            claim_id, submission_dt, inspector_pool, manager_pool, overflow_pool, adjuster_ids
        )

        if fast_track:
            fast_track_count += 1
        if claim_value > MANAGER_REVIEW_THRESHOLD:
            manager_review_count += 1
        if any(e[0] == "Routed to overflow reviewer pool" for e in events):
            overflow_count += 1
        if outcome == "Denied":
            denied_count += 1

        for activity, ts, handler in events:
            rows.append(
                {
                    "claim_id": claim_id,
                    "activity": activity,
                    "timestamp": ts,
                    "handler": handler,
                    "channel": channel,
                    "claim_type": claim_type,
                    "claim_value": claim_value,
                }
            )

    df = pd.DataFrame(rows).sort_values(["claim_id", "timestamp"]).reset_index(drop=True)

    summary = {
        "num_claims": NUM_CLAIMS,
        "num_events": len(df),
        "avg_events_per_claim": round(len(df) / NUM_CLAIMS, 2),
        "fast_track_pct": round(100 * fast_track_count / NUM_CLAIMS, 1),
        "manager_review_pct": round(100 * manager_review_count / NUM_CLAIMS, 1),
        "overflow_routed_pct_of_manager_reviews": round(
            100 * overflow_count / manager_review_count, 1
        ) if manager_review_count else 0,
        "denied_pct": round(100 * denied_count / NUM_CLAIMS, 1),
        "date_range": [df["timestamp"].min().isoformat(), df["timestamp"].max().isoformat()],
    }

    df.to_csv("claims_event_log_tobe.csv", index=False)
    with open("claims_summary_tobe.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

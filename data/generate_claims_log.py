"""
generate_claims_log.py

Synthetic event-log generator for the "Insurance Claims Intake Analysis &
Process Redesign" portfolio project.

ALL DATA PRODUCED BY THIS SCRIPT IS SYNTHETIC. No real claims, customers,
carriers, or company data are used or represented anywhere in this
generator or its output. Every timestamp, dollar amount, and handler ID
below is randomly generated.

Design summary
---------------
- ~5,000 claims across three types (Auto, Property, Injury), four intake
  channels (Phone, Web, Mobile, Agent), over a 24-month window
  (2024-01-01 through 2025-12-31).
- Built-in bottlenecks are not random noise bolted onto an otherwise clean
  process -- they emerge from the same mechanisms that create bottlenecks
  in real claims operations:
    1. A documentation rework loop, more likely for Property and Injury
       claims, with a heavy-tailed wait (customer/third-party turnaround
       -- largely outside the company's control).
    2. A resource-constrained inspector pool (Auto/Property claims must
       queue for one of only N_INSPECTORS inspectors).
    3. A resource-constrained manager pool (claims above
       MANAGER_REVIEW_THRESHOLD must queue for one of only N_MANAGERS
       managers before a coverage decision is finalized).
  Queueing for (2) and (3) is simulated with an actual resource calendar
  (see ResourcePool below), not sampled independently per claim -- so
  congestion emerges the way it would in a real operation: from claim
  volume outstripping a fixed headcount, not from a random delay column.
  Both resource-constrained steps log a "started" event in addition to
  "scheduled"/"submitted" and "completed", so queue wait (scheduled ->
  started) can be isolated from service time (started -> completed)
  rather than analyzed as one blended figure.
- Channel affects cycle time too: Phone/Agent submissions are entered
  directly by staff (same-day registration); Web/Mobile submissions sit
  in a manual verification queue first.

Run:
    python generate_claims_log.py
Output (written to the current working directory):
    claims_event_log.csv   -- one row per activity occurrence
    claims_summary.json    -- generation stats, used to sanity-check the
                               log and to source the numbers used in the
                               README and decision memo
"""

import json
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RNG_SEED = 42
random.seed(RNG_SEED)
np.random.seed(RNG_SEED)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
NUM_CLAIMS = 5000
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)  # 24-month window
WINDOW_DAYS = (END_DATE - START_DATE).days

CLAIM_TYPES = ["Auto", "Property", "Injury"]
CLAIM_TYPE_WEIGHTS = [0.50, 0.30, 0.20]

CHANNELS = ["Phone", "Web", "Mobile", "Agent"]
CHANNEL_WEIGHTS_BY_TYPE = {
    "Auto":     {"Phone": 0.20, "Web": 0.35, "Mobile": 0.35, "Agent": 0.10},
    "Property": {"Phone": 0.30, "Web": 0.30, "Mobile": 0.15, "Agent": 0.25},
    "Injury":   {"Phone": 0.40, "Web": 0.15, "Mobile": 0.10, "Agent": 0.35},
}

# Lognormal(mu, sigma) parameters per claim type, calibrated so roughly
# 3% of Auto, 15% of Property, and 20% of Injury claims land above the
# $25,000 manager-review threshold -- see claims_summary.json after a run
# for the actual simulated percentages.
CLAIM_VALUE_PARAMS = {
    "Auto":     (7.600, 1.30),   # median ~$1,998
    "Property": (8.700, 1.38),   # median ~$6,003
    "Injury":   (8.987, 1.354),  # median ~$8,001
}
CLAIM_VALUE_CAP = 500_000

MANAGER_REVIEW_THRESHOLD = 25_000
FAST_TRACK_VALUE_CEILING = 2_300

N_INTAKE_CLERKS = 15
N_TRIAGE_SPECIALISTS = 8
N_ADJUSTERS = 25
N_INSPECTORS = 10
N_MANAGERS = 4  # deliberately small -- this is the bottleneck

DOC_REWORK_BASE_PROB = {"Auto": 0.10, "Property": 0.24, "Injury": 0.40}
DOC_REWORK_SECOND_LOOP_PROB = 0.20  # given a first loop already happened

DENIAL_PROB = {"Auto": 0.08, "Property": 0.10, "Injury": 0.20}

MGR_SEND_BACK_PROB = 0.08  # manager sends the estimate back for revision


# ---------------------------------------------------------------------------
# Resource pool -- models a small fixed headcount as a next-available
# calendar, so wait time emerges from queueing under load rather than
# being sampled independently per claim.
# ---------------------------------------------------------------------------
class ResourcePool:
    def __init__(self, name, count):
        self.name = name
        self.count = count
        self.next_available = [START_DATE for _ in range(count)]

    def assign(self, request_time, service_duration_days):
        idx = min(range(self.count), key=lambda i: self.next_available[i])
        start = max(request_time, self.next_available[idx])
        end = start + timedelta(days=service_duration_days)
        self.next_available[idx] = end
        handler = f"{self.name}_{idx + 1:02d}"
        return start, end, handler


def is_fast_track(claim_type, claim_value):
    if claim_type == "Auto" and claim_value < FAST_TRACK_VALUE_CEILING:
        return random.random() < 0.90
    if claim_type == "Property" and claim_value < 1_200:
        return random.random() < 0.40
    if claim_type == "Injury" and claim_value < 600:
        return random.random() < 0.20
    return random.random() < 0.02


def gen_claim(claim_id, submission_dt, inspector_pool, manager_pool, adjuster_ids):
    claim_type = random.choices(CLAIM_TYPES, weights=CLAIM_TYPE_WEIGHTS)[0]
    ch_weights = CHANNEL_WEIGHTS_BY_TYPE[claim_type]
    channel = random.choices(list(ch_weights.keys()), weights=list(ch_weights.values()))[0]

    mu, sigma = CLAIM_VALUE_PARAMS[claim_type]
    claim_value = round(min(float(np.random.lognormal(mu, sigma)), CLAIM_VALUE_CAP), 2)

    events = []  # (activity, timestamp, handler)
    t = submission_dt

    def log(activity, ts, handler):
        events.append((activity, ts, handler))

    log("FNOL received", t, f"System_{channel}")

    # Channel-dependent registration delay: assisted entry (Phone/Agent)
    # is same-day; self-service (Web/Mobile) sits in a verification queue.
    if channel in ("Phone", "Agent"):
        reg_delay = np.random.uniform(0, 0.3)
    else:
        reg_delay = np.random.uniform(0.5, 2.5)
    t += timedelta(days=reg_delay)
    clerk = f"IntakeClerk_{random.randint(1, N_INTAKE_CLERKS):02d}"
    log("Claim registered", t, clerk)

    t += timedelta(days=np.random.uniform(0.2, 1.2))
    triage_spec = f"TriageSpec_{random.randint(1, N_TRIAGE_SPECIALISTS):02d}"
    log("Initial triage completed", t, triage_spec)

    if is_fast_track(claim_type, claim_value):
        t += timedelta(days=np.random.uniform(0.1, 0.5))
        log("Auto-approved (fast track)", t, triage_spec)
        t += timedelta(days=np.random.uniform(0.5, 2.0))
        log("Payment processed", t, "System_AutoPay")
        t += timedelta(days=np.random.uniform(0.1, 0.5))
        log("Claim closed", t, "System_AutoPay")
        return claim_type, channel, claim_value, events, "Approved", True

    # ---- full investigation path ----
    adjuster = f"Adjuster_{random.choice(adjuster_ids):02d}"

    # Handoff/queue wait for adjuster assignment -- right-skewed, since
    # most claims wait a little but some sit behind a caseload backlog.
    t += timedelta(days=np.random.gamma(shape=2.0, scale=0.8))
    log("Assigned to adjuster", t, adjuster)

    t += timedelta(days=np.random.uniform(1.0, 3.5))
    log("Adjuster review completed", t, adjuster)

    n_loops = 0
    if random.random() < DOC_REWORK_BASE_PROB[claim_type]:
        n_loops = 1
        if random.random() < DOC_REWORK_SECOND_LOOP_PROB:
            n_loops = 2
    for _ in range(n_loops):
        t += timedelta(days=np.random.uniform(0.2, 1.0))
        log("Additional documentation requested", t, adjuster)
        # Customer/third-party turnaround: outside internal control,
        # modeled with a wider, heavier-tailed wait than internal steps.
        t += timedelta(days=np.random.gamma(shape=2.5, scale=2.2))
        log("Documentation received", t, adjuster)

    if claim_type == "Injury":
        t += timedelta(days=np.random.uniform(0.2, 0.8))
        log("Medical records requested", t, adjuster)
        t += timedelta(days=np.random.gamma(shape=3.0, scale=2.5))
        log("Medical records received", t, adjuster)
    else:
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
        start, end, manager = manager_pool.assign(request_time, service_days)
        log("Submitted for manager review", request_time, manager)
        log("Manager review started", start, manager)
        t = end
        log("Manager review completed", t, manager)

        if random.random() < MGR_SEND_BACK_PROB:
            t += timedelta(days=np.random.uniform(0.5, 1.5))
            log("Sent back for revision", t, manager)
            t += timedelta(days=np.random.uniform(0.5, 2.0))
            log("Adjuster revised estimate", t, adjuster)
            request_time = t + timedelta(days=np.random.uniform(0.2, 0.5))
            start, end, manager2 = manager_pool.assign(request_time, service_days)
            log("Resubmitted for manager review", request_time, manager2)
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
    adjuster_ids = list(range(1, N_ADJUSTERS + 1))

    rows = []
    fast_track_count = 0
    manager_review_count = 0
    denied_count = 0

    # Draw all submission timestamps first and process claims in
    # chronological order -- resource pools (inspectors, managers) must
    # see requests in true arrival order, or a claim submitted early can
    # get queued behind one submitted much later purely because of
    # generation order, producing an artificial backlog that has nothing
    # to do with the process being modeled.
    submission_dates = [
        START_DATE + timedelta(days=random.randint(0, WINDOW_DAYS - 1), hours=random.uniform(7, 19))
        for _ in range(NUM_CLAIMS)
    ]
    submission_dates.sort()

    for i, submission_dt in enumerate(submission_dates, start=1):
        claim_id = f"CLM-{i:05d}"

        claim_type, channel, claim_value, events, outcome, fast_track = gen_claim(
            claim_id, submission_dt, inspector_pool, manager_pool, adjuster_ids
        )

        if fast_track:
            fast_track_count += 1
        if claim_value > MANAGER_REVIEW_THRESHOLD:
            manager_review_count += 1
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
        "denied_pct": round(100 * denied_count / NUM_CLAIMS, 1),
        "events_by_claim_type": df.drop_duplicates("claim_id")["claim_type"]
        .value_counts(normalize=True)
        .round(3)
        .to_dict(),
        "date_range": [df["timestamp"].min().isoformat(), df["timestamp"].max().isoformat()],
    }

    df.to_csv("claims_event_log.csv", index=False)
    with open("claims_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

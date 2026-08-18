"""
analysis_rework_fcr_segments.py

Phase 2, parts 2-3: rework loop frequency, first-contact resolution (FCR),
and cycle time segmented by channel and claim type.

Definitions used here:
- Rework: a claim needed at least one "Additional documentation requested"
  round trip and/or was "Sent back for revision" by a manager. Both are
  round trips back to someone outside the step that "should" have
  finished the claim -- the customer/third party in the first case, the
  adjuster in the second.
- FCR (first-contact resolution): a claim resolved with ZERO such round
  trips -- either because it fast-tracked entirely, or because the full
  investigation path went through cleanly on the first pass. This is
  broader than "fast-track rate": it also credits standard-path claims
  that never had to loop back to anyone.
- Cycle time here is END-TO-END: FNOL received -> Claim closed, per
  claim, not the per-activity gap used in analysis_cycle_time.py.
"""

import duckdb

con = duckdb.connect()
CSV = "claims_event_log.csv"

# ---------------------------------------------------------------------------
# Rework frequency + FCR, by claim type
# ---------------------------------------------------------------------------
REWORK_FCR_SQL = f"""
WITH claim_flags AS (
    SELECT
        claim_id,
        ANY_VALUE(claim_type) AS claim_type,
        ANY_VALUE(channel) AS channel,
        SUM(CASE WHEN activity = 'Additional documentation requested' THEN 1 ELSE 0 END) AS doc_requests,
        SUM(CASE WHEN activity = 'Sent back for revision' THEN 1 ELSE 0 END) AS sendbacks,
        SUM(CASE WHEN activity = 'Auto-approved (fast track)' THEN 1 ELSE 0 END) AS fast_track
    FROM read_csv_auto('{CSV}')
    GROUP BY claim_id
)
SELECT
    claim_type,
    COUNT(*) AS n_claims,
    ROUND(100.0 * SUM(CASE WHEN fast_track > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS fast_track_pct,
    ROUND(100.0 * SUM(CASE WHEN doc_requests > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS doc_rework_pct,
    ROUND(100.0 * SUM(CASE WHEN sendbacks > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS mgr_sendback_pct,
    ROUND(100.0 * SUM(CASE WHEN doc_requests = 0 AND sendbacks = 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS fcr_pct
FROM claim_flags
GROUP BY claim_type
ORDER BY claim_type
"""
rework_by_type = con.execute(REWORK_FCR_SQL).fetchdf()

REWORK_FCR_OVERALL_SQL = f"""
WITH claim_flags AS (
    SELECT
        claim_id,
        SUM(CASE WHEN activity = 'Additional documentation requested' THEN 1 ELSE 0 END) AS doc_requests,
        SUM(CASE WHEN activity = 'Sent back for revision' THEN 1 ELSE 0 END) AS sendbacks,
        SUM(CASE WHEN activity = 'Auto-approved (fast track)' THEN 1 ELSE 0 END) AS fast_track
    FROM read_csv_auto('{CSV}')
    GROUP BY claim_id
)
SELECT
    'ALL' AS claim_type,
    COUNT(*) AS n_claims,
    ROUND(100.0 * SUM(CASE WHEN fast_track > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS fast_track_pct,
    ROUND(100.0 * SUM(CASE WHEN doc_requests > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS doc_rework_pct,
    ROUND(100.0 * SUM(CASE WHEN sendbacks > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS mgr_sendback_pct,
    ROUND(100.0 * SUM(CASE WHEN doc_requests = 0 AND sendbacks = 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS fcr_pct
FROM claim_flags
"""
rework_overall = con.execute(REWORK_FCR_OVERALL_SQL).fetchdf()

print("=== Rework frequency & FCR by claim type ===")
print(rework_by_type.to_string(index=False))
print()
print("=== Overall (all claim types) ===")
print(rework_overall.to_string(index=False))
print()

rework_by_type.to_csv("rework_fcr_by_claim_type.csv", index=False)

# ---------------------------------------------------------------------------
# End-to-end cycle time by claim type x channel
# ---------------------------------------------------------------------------
SEGMENT_SQL = f"""
WITH claim_meta AS (
    SELECT
        claim_id,
        ANY_VALUE(claim_type) AS claim_type,
        ANY_VALUE(channel) AS channel,
        MIN(timestamp) AS start_ts,
        MAX(timestamp) AS end_ts,
        SUM(CASE WHEN activity = 'Auto-approved (fast track)' THEN 1 ELSE 0 END) AS fast_track
    FROM read_csv_auto('{CSV}')
    GROUP BY claim_id
)
SELECT
    claim_type,
    channel,
    COUNT(*) AS n_claims,
    ROUND(AVG(EXTRACT(EPOCH FROM (end_ts - start_ts)) / 86400.0), 2) AS avg_days,
    ROUND(MEDIAN(EXTRACT(EPOCH FROM (end_ts - start_ts)) / 86400.0), 2) AS median_days
FROM claim_meta
WHERE fast_track = 0
GROUP BY claim_type, channel
ORDER BY claim_type, channel
"""
segments = con.execute(SEGMENT_SQL).fetchdf()
print("=== End-to-end cycle time by claim type x channel (standard/full-investigation claims only) ===")
print(segments.to_string(index=False))
segments.to_csv("cycle_time_by_segment.csv", index=False)

FAST_TRACK_ONLY_SQL = f"""
WITH claim_meta AS (
    SELECT
        claim_id,
        MIN(timestamp) AS start_ts,
        MAX(timestamp) AS end_ts,
        SUM(CASE WHEN activity = 'Auto-approved (fast track)' THEN 1 ELSE 0 END) AS fast_track
    FROM read_csv_auto('{CSV}')
    GROUP BY claim_id
)
SELECT
    COUNT(*) AS n_claims,
    ROUND(AVG(EXTRACT(EPOCH FROM (end_ts - start_ts)) / 86400.0), 2) AS avg_days,
    ROUND(MEDIAN(EXTRACT(EPOCH FROM (end_ts - start_ts)) / 86400.0), 2) AS median_days
FROM claim_meta
WHERE fast_track > 0
"""
fast_track_only = con.execute(FAST_TRACK_ONLY_SQL).fetchdf()
print()
print("=== Fast-track claims, for contrast (all channels/types pooled) ===")
print(fast_track_only.to_string(index=False))

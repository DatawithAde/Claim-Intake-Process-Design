"""
analysis_cycle_time.py

Phase 2, part 1: cycle time by activity.

Definition: for each claim, the "cycle time" attributed to an activity is
the elapsed time between the PREVIOUS activity's completion timestamp and
this activity's completion timestamp. Because the event log records a
single completion timestamp per activity (not separate start/complete
pairs), this figure is a blend of queue time + processing time for that
step -- it answers "how much total elapsed time does reaching this
activity cost," not "how long does the activity itself take once started."
Two named steps in the log (Assigned to adjuster, Submitted for manager
review) exist specifically so handoff/queue time can be isolated
separately -- that's analysis_handoff_delay.py, not this file.

Uses DuckDB as the SQL layer: it queries the CSV directly with no server
or load step, which keeps the repo simple and the analysis reproducible
from a single `pip install duckdb`.
"""

import duckdb

con = duckdb.connect()

CYCLE_TIME_SQL = """
WITH ordered AS (
    SELECT
        claim_id,
        activity,
        timestamp,
        LAG(timestamp) OVER (PARTITION BY claim_id ORDER BY timestamp) AS prev_timestamp
    FROM read_csv_auto('claims_event_log.csv')
)
SELECT
    activity,
    COUNT(*) AS n_occurrences,
    ROUND(AVG(EXTRACT(EPOCH FROM (timestamp - prev_timestamp)) / 86400.0), 2) AS avg_days,
    ROUND(MEDIAN(EXTRACT(EPOCH FROM (timestamp - prev_timestamp)) / 86400.0), 2) AS median_days,
    ROUND(QUANTILE_CONT(EXTRACT(EPOCH FROM (timestamp - prev_timestamp)) / 86400.0, 0.9), 2) AS p90_days
FROM ordered
WHERE prev_timestamp IS NOT NULL
GROUP BY activity
ORDER BY avg_days DESC
"""

df = con.execute(CYCLE_TIME_SQL).fetchdf()

# Share of total elapsed time: for each claim, sum the gap-to-each-activity
# values, then see what fraction of that total each activity accounts for
# on average. This is the number that will back the "N bottlenecks driving
# X% of total cycle time" line in the resume bullet.
total_avg_days = df["avg_days"].sum()
df["pct_of_avg_total_cycle_time"] = round(100 * df["avg_days"] / total_avg_days, 1)

pd_display = df.to_string(index=False)
print(pd_display)

df.to_csv("cycle_time_by_activity.csv", index=False)
print(f"\nTotal average cycle time across all steps: {round(total_avg_days, 2)} days")

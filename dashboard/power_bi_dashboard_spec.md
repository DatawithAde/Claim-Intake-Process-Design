# Power BI dashboard spec — claims intake operations

Built to be pasted directly into Power BI Desktop against `data/claims_dashboard_data.csv` (the as-is and to-be event logs, unioned with a `scenario` column so the dashboard can toggle between them — this makes it double as the before/after visualization, not just a post-implementation monitor).

## Data model

Load `claims_dashboard_data.csv` as a table named **Events** (this is the flat event log: claim_id, activity, timestamp, handler, channel, claim_type, claim_value, scenario).

Then build a **Claims** table with one row per (claim_id, scenario) using the Power Query step below — this is the table most visuals and measures should point at, since grouping every visual off the raw event log recomputes the same aggregation repeatedly.

**Relationship:** `Claims[claim_id + scenario]` (composite or concatenated key) → `Events[claim_id + scenario]`, one-to-many.

### Power Query M — derive Claims from Events

```m
let
    Source = Events,
    GroupedByClaim = Table.Group(Source, {"claim_id", "scenario"}, {
        {"claim_type", each List.First([claim_type]), type text},
        {"channel", each List.First([channel]), type text},
        {"claim_value", each List.First([claim_value]), type number},
        {"submission_date", each List.Min([timestamp]), type datetime},
        {"closed_date", each List.Max([timestamp]), type datetime},
        {"fast_track", each List.Count(List.Select([activity], each Text.StartsWith(_, "Auto-approved"))) > 0, type logical},
        {"doc_rework", each List.Count(List.Select([activity], each _ = "Additional documentation requested")) > 0, type logical},
        {"mgr_sendback", each List.Count(List.Select([activity], each _ = "Sent back for revision")) > 0, type logical},
        {"manager_review", each List.Count(List.Select([activity], each _ = "Manager review started")) > 0, type logical},
        {"overflow_routed", each List.Count(List.Select([activity], each _ = "Routed to overflow reviewer pool")) > 0, type logical},
        {"outcome", each if List.Count(List.Select([activity], each _ = "Denial letter sent")) > 0 then "Denied" else "Approved", type text}
    }),
    AddCycleTime = Table.AddColumn(GroupedByClaim, "cycle_time_days", each Duration.TotalDays([closed_date] - [submission_date]), type number),
    AddFCR = Table.AddColumn(AddCycleTime, "fcr", each not [doc_rework] and not [mgr_sendback], type logical),
    AddKey = Table.AddColumn(AddFCR, "claim_scenario_key", each [claim_id] & "|" & [scenario], type text)
in
    AddKey
```

Add the matching key column to **Events** too (`claim_id & "|" & scenario`) so the relationship has something to join on.

### Calculated column on Events — gap since previous activity

Needed for cycle-time-by-activity and queue-wait measures. Add as a calculated column, not a measure (row context needed):

```dax
Prev Timestamp =
CALCULATE(
    MAX(Events[timestamp]),
    FILTER(
        Events,
        Events[claim_scenario_key] = EARLIER(Events[claim_scenario_key])
            && Events[timestamp] < EARLIER(Events[timestamp])
    )
)

Days Since Prev Activity = DATEDIFF(Events[Prev Timestamp], Events[timestamp], SECOND) / 86400.0
```

## DAX measures

```dax
Claim Count = COUNTROWS(Claims)

Avg Cycle Time (Days) = AVERAGE(Claims[cycle_time_days])

Median Cycle Time (Days) = MEDIAN(Claims[cycle_time_days])

FCR Rate = DIVIDE(CALCULATE(COUNTROWS(Claims), Claims[fcr] = TRUE), [Claim Count])

Fast Track Rate = DIVIDE(CALCULATE(COUNTROWS(Claims), Claims[fast_track] = TRUE), [Claim Count])

Doc Rework Rate = DIVIDE(CALCULATE(COUNTROWS(Claims), Claims[doc_rework] = TRUE), [Claim Count])

Manager Review Rate = DIVIDE(CALCULATE(COUNTROWS(Claims), Claims[manager_review] = TRUE), [Claim Count])

Overflow Routed Rate =
DIVIDE(
    CALCULATE(COUNTROWS(Claims), Claims[overflow_routed] = TRUE),
    CALCULATE(COUNTROWS(Claims), Claims[manager_review] = TRUE)
)

Denial Rate = DIVIDE(CALCULATE(COUNTROWS(Claims), Claims[outcome] = "Denied"), [Claim Count])

Avg Cycle Time by Activity =
CALCULATE(
    AVERAGE(Events[Days Since Prev Activity]),
    NOT ISBLANK(Events[Prev Timestamp])
)

Mgr Queue Wait (Days) =
CALCULATE(
    AVERAGE(Events[Days Since Prev Activity]),
    Events[activity] = "Manager review started"
)

Mgr Queue Wait P90 =
CALCULATE(
    PERCENTILE.INC(Events[Days Since Prev Activity], 0.9),
    Events[activity] = "Manager review started"
)
```

### Caveat: the chronological-gap measure breaks under parallel branches

`Avg Cycle Time by Activity` (and `Days Since Prev Activity` generally) assumes the previous row in a claim's timestamp-sorted event list is the thing that actually caused the wait. That's true everywhere in the as-is process, and everywhere in the to-be process **except** the Injury fork/join: once the medical-records request and the adjuster-review branch run concurrently, their events interleave in time, so the row immediately before "Medical records received" is sometimes an adjuster-branch event, not "Medical records requested." Naively charting `Avg Cycle Time by Activity` for that step in the To-Be scenario shows ~4.1 days — which looks like the wait itself shrank. It didn't: the actual request-to-receipt wait is ~7.3 days, essentially unchanged. What changed is that it now overlaps with other work instead of stacking after it, which is exactly what the claim-level cycle time already captures correctly.

Use a direct paired measure for this specific step instead of the chronological-gap one:

```dax
Med Records Requested TS =
LOOKUPVALUE(Events[timestamp], Events[claim_scenario_key], Claims[claim_scenario_key], Events[activity], "Medical records requested (automated)")

Med Records Received TS =
LOOKUPVALUE(Events[timestamp], Events[claim_scenario_key], Claims[claim_scenario_key], Events[activity], "Medical records received")

Medical Records Wait (Days) = DATEDIFF([Med Records Requested TS], [Med Records Received TS], SECOND) / 86400.0
```

(as calculated columns on **Claims**, then a measure `AVERAGE(Claims[Medical Records Wait (Days)])`). Use this pairing pattern for any future step that becomes parallel — the chronological-gap measure stays valid for every sequential step, it's specifically fork/join steps that need a direct pair instead.

## Page layout

**Page 1 — Executive overview**
KPI cards: Avg Cycle Time, FCR Rate, Fast Track Rate, Doc Rework Rate — each as a small-multiple or side-by-side card pair split by `scenario`, so As-Is vs. To-Be reads at a glance. Scenario slicer at top; Claim Type and Channel slicers alongside.

**Page 2 — Cycle time deep dive**
Horizontal bar chart: `Avg Cycle Time by Activity`, activity on Y axis sorted descending, split by scenario. This is the chart that shows documentation waits dropping out of the top of the list in the To-Be view. Exclude "Medical records received" from this chart (or footnote it) and show `Medical Records Wait (Days)` as a separate card instead — see the caveat above for why the two scenarios aren't comparable on the same chronological-gap measure for that specific step.

**Page 3 — Rework & first-contact resolution**
FCR Rate and Doc Rework Rate by Claim Type (clustered bar, both scenarios), plus a table breaking out fast-track rate by claim type — this is where Property's fast-track widening shows up visibly.

**Page 4 — Manager review queue monitor**
`Mgr Queue Wait (Days)` and `Mgr Queue Wait P90` as cards, split by scenario. Below: a histogram of `Days Since Prev Activity` filtered to `Manager review started`, so the queue-wait distribution — not just its average — is visible. `Overflow Routed Rate` as a card on the To-Be side only (no equivalent in As-Is).

## Data files

- `data/claims_dashboard_data.csv` — the unioned as-is/to-be event log described above, ready to import as the Events table.

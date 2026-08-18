# Pain point analysis — claims intake

**Data source:** synthetic event log, 5,000 claims / 57,781 events. See `as_is_process_map.md` for the process this analysis is mapped against, and `analysis/` for the underlying SQL/Python.

## Headline numbers

| Metric | Value |
|---|---|
| Average cycle time, all claims (blended) | **12.48 days** |
| Average cycle time, full-investigation claims only (71.8% of volume) | 15.95 days |
| Average cycle time, fast-track claims (28.2% of volume) | 3.62 days |
| Overall first-contact resolution (FCR) | 82.8% |

"Blended" is the number to cite as the current-state baseline — it's what a redesign should be measured against.

## Pain point 1 — Injury claims are the process's weak point on every metric

- FCR 59.8% (worst of the three claim types, vs. 94.9% for Auto)
- Documentation rework rate 38.4% (worst; more than 7x Auto's 4.9%)
- Average cycle time 20.97 days — about 44% longer than Property (14.55) and 55% longer than Auto (13.56)
- Root cause: dependency on third-party medical records. Waiting on those records averages **7.44 days** (p90: 13.5 days) — the single largest cycle-time driver anywhere in the process, ahead of every internal step including manager review.
- This is an external-dependency problem, not an internal-speed problem. More adjuster headcount would not move this number; the process doesn't control how fast a provider's records office responds.

## Pain point 2 — the documentation rework loop, concentrated in Property and Injury

- 16.4% of all claims (22.8% of full-investigation claims) require at least one additional-documentation round trip
- Average wait once requested: 5.52 days (p90: 10.43 days) — the second-largest cycle-time driver in the process
- Property (21.2% rework rate) and Injury (38.4%) drive nearly all of this; Auto's rate is low (4.9%)
- Likely cause, based on what triggers this step in the process: claims arriving without complete supporting documentation at intake, discovered only once an adjuster reviews them

## Pain point 3 — manager review is real, but narrower than it looks at first glance

- Only 9.6% of claims trigger manager review (claim value over $25,000)
- Average queue wait: 1.28 days — but the **median is 0.0 days**. Most reviews start the moment they're submitted; four managers is enough capacity most of the time.
- The tail is where the problem lives: **p90 queue wait is 4.91 days**, meaning roughly 1 in 10 manager-review claims (about 1% of all claims) hits real congestion, almost certainly during periods when several high-value claims land close together.
- Implication: this reads as a periodic-load problem, not a permanent capacity shortfall. A surge/overflow reviewer arrangement or a review-priority queue is a better-targeted fix than adding a fifth full-time manager.

## Pain point 4 — channel is a real, modest, and comparatively cheap lever

- Phone/Agent-submitted claims run 0.7–1.3 days faster than Web/Mobile-submitted claims, consistently across all three claim types (not just in aggregate)
- Driven by the registration step: staff-assisted entry (Phone/Agent) completes same-day; self-service submissions (Web/Mobile) sit in a manual verification queue for up to 2.5 days before the claim is even registered
- Smallest of the four levers in absolute terms, but likely the cheapest to close — real-time field validation on the self-service intake forms could remove most of this gap without adding staff

## What the data says is *not* a pain point

Worth stating explicitly, since it runs against the initial assumption behind this analysis:

- **Inspector capacity** is not currently a bottleneck at this claim volume — queue wait median is 0 days, p90 2.54 days.
- **Denial rate** (9.0% overall, scaling sensibly with claim-type risk) doesn't show up as a process-speed issue — it's an underwriting outcome, not an intake-process delay.

## Ranked priority for the redesign

1. **Injury medical-records dependency** — largest single driver (~22% of average full-path cycle time)
2. **Documentation rework loop**, concentrated in Property/Injury (~17% of average full-path cycle time)
3. **Manager review surge handling** — small population, but a real tail risk worth a targeted fix
4. **Channel-driven registration delay** — smallest lever, cheapest to pull

*Note on the "% of cycle time" figures above:* these are computed from the average elapsed time attributable to each activity across all claims where it occurs, expressed as a share of the sum of all such averages. It's a reasonable proxy for relative weight, not a per-claim decomposition (claims don't all take the same path), so treat these as directional rather than exact.

This ranking is what the to-be process map and BRD requirements are built against next.

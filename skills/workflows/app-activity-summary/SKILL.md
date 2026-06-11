---
name: app-activity-summary
metadata:
  category: workflows
description: Answer "how is the app doing this week or month?" — the weekly or monthly digest pattern with Total Sends, Total App Opens, Net Opt-in Change, and current Opted-in Device Count. Mirrors the dashboard's App Metrics + Devices Engagement Reports view. Use when asked for an app-health snapshot over a date range.
---

# Workflow: App Activity Summary

## Purpose

Answer rolled-up app-health questions like "how is the app doing this week?", "give me a monthly digest", "what was our opt-in delta last month?". Produces the same numbers an AM would see at the top of the Engagement Reports view in the dashboard.

## Prerequisites

- OAuth credentials with the **`rpt`** scope
- A date range (defaults to **Last 7 days** — matches the dashboard's Unique App Opens default)

## Skills Required

- [Reports reference](../../api/reports/SKILL.md)

## Protocol

### Step 1: Resolve timezone

One-shot ask per session per the [Reports reference Date / Time Protocol](../../api/reports/SKILL.md#date--time-protocol). Default to UTC and announce if the user declines.

### Step 2: Resolve range

If the user said "this week", "last week", "this month", "last month", "today", "yesterday" — convert to absolute UTC start / end using the timezone from Step 1.

If no range stated, default to **Last 7 days** ending today.

### Step 3: Decide precision

Per the [Reports reference Precision Rules](../../api/reports/SKILL.md#precision-rules):

- DAILY for ranges ≤ 180 days.
- MONTHLY for ranges > 180 days.
- HOURLY only when range ≤ 72 hours **and** the user explicitly asks for sub-day resolution.

Announce the chosen precision before fetching if the budget is in question.

### Step 4: Pre-flight budget check

Estimate `buckets × dimensions` across the five endpoints below. If it exceeds 500, propose narrowing the range to the user before any call.

### Step 5: Fetch

In parallel where the harness supports it:

```
GET /api/reports/sends?start=&end=&precision={DAILY|MONTHLY}
GET /api/reports/opens?start=&end=&precision={DAILY|MONTHLY}
GET /api/reports/optins?start=&end=&precision={DAILY|MONTHLY}
GET /api/reports/optouts?start=&end=&precision={DAILY|MONTHLY}
GET /api/reports/devices
```

If the user asked for a "last week" / "this month" style range **and** the budget permits a second pass, also fetch the equal-length prior period for the % change footer.

### Step 6: Aggregate

For each of `sends`, `opens`, `optins`, `optouts`: sum the per-bucket counts across the range.

For `devices`: take the point-in-time `opted_in`, `opted_out`, `uninstalled`, `unique_devices` values.

Net Opt-in Change = `sum(optins) − sum(optouts)`.

### Step 7: Format the answer per the output contract

## Headline Metrics

- **Total Sends** in range (sum of `/api/reports/sends`)
- **Total App Opens** in range (sum of `/api/reports/opens`)
- **Net Opt-in Change** = `sum(optins) − sum(optouts)`
- **Current Opted-in Device Count** (point-in-time from `/api/reports/devices`)
- Optional **per-day mini-table** when range ≥ 7 days, showing each day's Sends + App Opens
- **% change vs prior period** for each metric when budget allows

## Output Footer

Per the [Reports reference Output Contract](../../api/reports/SKILL.md#output-contract):

- Headline metrics (above)
- **Range echoed in user timezone:** e.g. "Range: 2026-05-21 to 2026-05-28, America/Los_Angeles."
- **Freshness caveat:** "App opens are continuously updated; opt-in / opt-out are eventual within ~30 min. Devices snapshot is daily."
- "Skipped prior-period comparison to stay within budget" if applicable.

## Dashboard-Only Metrics

If the user asks for **Average Time In App**, do not fabricate a proxy. Answer:

> "Average Time In App is in the Engagement Reports dashboard but not in the Reports API. View it at https://go.airship.com/reports/engagement."

See [Reports reference Dashboard-Only Metrics](../../api/reports/SKILL.md#dashboard-only-metrics).

## Errors

- **401** → check the `rpt` scope first; see [Reports reference Error Guidance](../../api/reports/SKILL.md#error-guidance).
- **400** → check date range / precision combination. Some endpoints reject sub-day precision for long ranges.

## Example Invocations

- "How is the app doing this week?"
- "Weekly app activity digest in Pacific time."
- "April vs March opt-ins."
- "Last 30 days, monthly."

## Example Answer Shape

```
Weekly App Activity (2026-05-21 to 2026-05-28, America/Los_Angeles)

Total Sends:               12,840  (+6.2% vs prior week)
Total App Opens:           48,201  (+1.8% vs prior week)
Net Opt-in Change:           +312  (1,047 in, 735 out)
Opted-in Devices (current):  68,544

Per-day breakdown:
  2026-05-21  Sends 1,820  Opens 6,732
  2026-05-22  Sends 1,901  Opens 7,011
  ...

Freshness: App opens are continuously updated. Opt-in/out eventual within ~30 min.
```

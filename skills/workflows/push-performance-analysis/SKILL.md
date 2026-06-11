---
name: push-performance-analysis
metadata:
  category: workflows
description: Answer "how did this push or campaign do?" with dashboard-aligned metrics — Sends, Direct Opens, Direct Open Rate, Influenced Opens, Influenced Open Rate, and per-platform breakdown. Discovers the push by name or send-time hint when no push_id is given. Handles A/B variant breakdown automatically.
---

# Workflow: Push Performance Analysis

## Purpose

Answer single-push performance questions like "how did the welcome push do?", "performance for push abc-123 with per-platform breakdown", or "compare the variants of yesterday's A/B test". Produces the same numbers an AM would see in the Messages Reports view of the dashboard.

## Prerequisites

- OAuth credentials with the **`rpt`** scope (see [Reports reference](../../api/reports/SKILL.md#authentication))
- A `push_id`, **or** a human description plus a send-time hint

## Skills Required

- [Reports reference](../../api/reports/SKILL.md) — endpoint catalog, vocabulary, output contract, all the rules

## Protocol

### Step 1: Resolve the push

If the user provided a `push_id`, skip to Step 2.

Otherwise, run the [Reports reference Required Discovery Flow](../../api/reports/SKILL.md#required-discovery-flow): query `/api/reports/activity/details` with the user's hint, present a candidate table on multi-match, ask the user to pick. **Never silent first-match.**

Capture the `experiment: bool` flag from the chosen activity-log row and carry it forward.

### Step 2: Fetch per-push detail

```
GET /api/reports/perpush/detail/{push_id}
```

Returns: `sends`, `alerting_sends`, `silent_sends`, `direct_responses`, `influenced_responses`, `rich_sends`, `rich_responses`, `rich_deletions`, `platforms` (iOS / Android / Amazon / web breakdown).

This is the primary data source for the answer.

### Step 3: A/B branching (lazy)

Use the `experiment` flag from Step 1:

- `experiment: false` → skip experiment endpoints. Go to Step 4.
- `experiment: true` → call `/api/reports/experiment/overview/{push_id}`, then fetch each variant via `/api/reports/experiment/detail/{push_id}/{variant_id}`.
- If `push_id` was supplied directly (no activity-log discovery), call `experiment/overview` once. If `variants` is non-empty, fetch per-variant detail; otherwise treat as non-experiment.

See [Reports reference A/B Test Branching](../../api/reports/SKILL.md#ab-test-branching).

### Step 4: Optional time-series

Only if the user asked for shape over time (e.g. "show me the open curve", "when did most opens land?").

```
GET /api/reports/perpush/series/{push_id}?start=<ISO>&end=<ISO>&precision=HOURLY
```

**Budget guard.** `perpush/series` only confirmed-supports `HOURLY`, and 30 days of HOURLY × 4 platforms × 3 metrics ≈ 8,640 numbers — over the hard cap. Refuse if the window exceeds 14 days and ask the user to narrow. Default a 7-day window when not stated. See [Reports reference Precision Rules](../../api/reports/SKILL.md#precision-rules).

### Step 5: Format the answer per the output contract

## Headline Metrics

Use **dashboard labels** (API field name in parens for traceability):

- **Sends** (`sends`)
- **Direct Opens** (`direct_responses`)
- **Direct Open Rate** = `direct_responses / sends` (formatted as a percentage)
- **Influenced Opens** (`influenced_responses`)
- **Influenced Open Rate** = `influenced_responses / sends`

Always include the per-platform breakdown when platforms differ meaningfully (e.g. iOS vs Android). Suppress platforms with zero sends.

For A/B tests, present per-variant rows of the same metrics plus the `control` block from `experiment/overview`.

## Output Footer

Per the [Reports reference Output Contract](../../api/reports/SKILL.md#output-contract):

- Headline metrics (above)
- Per-platform breakdown (when meaningful)
- **Timezone used**
- **Freshness caveat:** "Delivery stats settle in ~30 min. Opens continue to grow as users engage."
- "Results truncated after N pages" if applicable (rare for this workflow)

## Errors

- **401** → check the `rpt` scope first; see [Reports reference Error Guidance](../../api/reports/SKILL.md#error-guidance).
- **404 on `/perpush/detail/{push_id}`** → wrong push_id, push not yet processed (~30 min lag), or push from a different `app_key`.
- **400 on `/perpush/series/{push_id}`** → missing `start`/`end` or DAILY rejected; retry with HOURLY.

## Example Invocations

- "How did the welcome push do?"
- "Performance for push 3b47b010-5a0b-11f1-8ff2-000000a1ace1 with per-platform breakdown"
- "Compare variants of yesterday's A/B test"
- "Show me the open curve for our last campaign"

## Example Answer Shape

```
Welcome Push (push_id 3b47b010..., sent 2026-05-27 14:30 UTC)

Sends: 370 (iOS 297, Android 73)
Direct Opens: 0 (Direct Open Rate: 0.0%)
Influenced Opens: 0 (Influenced Open Rate: 0.0%)

Timezone: America/Los_Angeles
Freshness: Delivery stats settle in ~30 min. Opens continue to grow.
```

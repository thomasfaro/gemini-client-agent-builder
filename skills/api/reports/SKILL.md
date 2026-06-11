---
name: reports
metadata:
  category: api
description: Read-only access to Airship Reports for delivery stats, send history, app activity, and A/B test outcomes. Use when answering "how did this push do?", "how is the app doing this week?", or any insight question that maps to /api/reports/*.
---

# Skill: Airship Reports

## Overview

This skill gives AMs, PMs, and developers natural-language access to Airship's Reports API. Use it whenever the user asks an insight question: "how did our latest push do?", "how is the app doing this week?", "did the A/B test win?", "what's our opt-in delta this month?". All answers stay aligned with the labels AMs see in the Airship dashboard Engagement Reports view.

This is a **read-only** skill. It does not send pushes, modify segments, or change anything. It only queries `/api/reports/*` and presents the results.

## API Endpoints

All endpoints are `GET` against the Go API base (`https://api.asnapius.com` for US, `https://api.asnapieu.com` for EU). All require the OAuth `rpt` scope and the `X-UA-Appkey` header (auto-injected by `call_airship_api`).

| Path | Answers | Accepts `precision` | Freshness |
|---|---|---|---|
| `/api/reports/activity/details?start=&end=&limit=` | Recent push activity log (discovery entry point). Each row has `push_id`, `timestamp`, `type`, **`experiment` (bool)**, `details.delivery`, `details.interaction`. `start` and `end` required, `limit` defaults to 100, follow `next_page`. | — | near-real-time |
| `/api/reports/sends?start=&end=&precision=` | Push send counts over time | DAILY, MONTHLY | ~5 min |
| `/api/reports/opens?start=&end=&precision=` | App-open counts over time | DAILY, MONTHLY | continuously updating |
| `/api/reports/devices` | Opted-in vs total unique device counts (point-in-time) | — | daily |
| `/api/reports/optins?start=&end=&precision=` | Opt-in event counts over time | DAILY, MONTHLY | ~30 min |
| `/api/reports/optouts?start=&end=&precision=` | Opt-out event counts over time | DAILY, MONTHLY | ~30 min |
| `/api/reports/responses/{push_id}` | Smaller per-push response summary | — | ~30 min |
| `/api/reports/perpush/detail/{push_id}` | Full push stats: `sends`, `alerting_sends`, `silent_sends`, `direct_responses`, `influenced_responses`, `rich_sends/responses/deletions`, `platforms` | — | ~30 min |
| `/api/reports/perpush/series/{push_id}?start=&end=&precision=HOURLY` | Push response time-series. OpenAPI lists `start`/`end` as optional with a 12-hour default and accepts HOURLY/DAILY/MONTHLY, but the live server returned 400 against goat without them and against DAILY. **In practice: always pass `start`, `end`, and `precision=HOURLY`.** | HOURLY (observed) | continuously updating |
| `/api/reports/perpush/pushbody/{push_id}` | Push body payload as sent | — | immediate |
| `/api/reports/pergroup/detail/{group_id}` | Aggregate stats for a group push | — | ~30 min |
| `/api/reports/pergroup/series/{group_id}?start=&end=&precision=` | Group push time-series. Likely requires `start` and `end` (same family as perpush/series). | HOURLY | continuously updating |
| `/api/reports/experiment/overview/{push_id}` | A/B summary: `variants[]`, `control`. **Returns 200 with `variants: []` for non-experiment pushes** — not 404. | — | ~30 min |
| `/api/reports/experiment/detail/{push_id}/{variant_id}` | Single A/B variant stats | — | ~30 min |
| `/api/reports/events?start=&end=&precision=` | Custom event counts and values summary | DAILY, MONTHLY | ~30 min |
| `/api/reports/events/summary/perpush/{push_id}` | Events attributed to a push | — | ~30 min |
| `/api/reports/events/summary/pergroup/{group_id}` | Events attributed to a group | — | ~30 min |

Real example responses for the most-used endpoints live in `examples/`.

## Authentication

OAuth bearer + `X-UA-Appkey` (auto-injected by `call_airship_api`). **Requires the `rpt` scope.**

If the OAuth credential was created before the Reports scope existed, customers must:

1. Open the Airship dashboard.
2. Project dropdown → **Settings** → **OAuth**.
3. Edit the existing credential.
4. Enable the **Reports** scope.
5. **Restart the MCP client** so the cached OAuth token is replaced.

## Required Discovery Flow

When the user references a push by anything other than a UUID ("the welcome push", "Tuesday's campaign", "our last A/B test"), do not ask them for the push_id. Discover it.

1. Call `/api/reports/activity/details` with a date window covering the user's hint. Default window: last 14 days.
2. If **0 matches**, widen the window once to 90 days. If still 0, ask the user for the `push_id` directly.
3. If **1 match**, proceed with that `push_id`. Also capture the row's `experiment` boolean for use in A/B branching below.
4. If **>1 matches**, present a candidate table and ask the user to pick. **Never silent first-match.**

Candidate table format:

| # | push_id | sent (UTC) | type | sends | experiment |
|---|---|---|---|---|---|
| 1 | abc-123 | 2026-05-27 14:30 | PUSH | 1,204 | false |
| 2 | def-456 | 2026-05-26 09:00 | PUSH | 982 | true |

Ask "Which one?" and use the user's response.

## Date / Time Protocol

- All API timestamps and ranges are UTC.
- On the first reports question of a session, ask the user once: **"What timezone should I report in? I'll use it for all reports questions today."** If the user declines, defaults to UTC.
- Every answer echoes the timezone used in one line, e.g. "Range: 2026-05-21 to 2026-05-28, America/Los_Angeles."
- Convert the user's relative times ("yesterday", "last week", "this month") to absolute UTC ranges before calling the API. Announce the converted range in the answer.
- Default range when none stated: **Last 7 days** (matches the dashboard default for Unique App Opens).

## Precision Rules

Strongly preferred defaults, with mandatory pre-flight announcement when the budget is in question:

- **DAILY default** for ranges ≤ 180 days where the endpoint supports it.
- **HOURLY** only when the requested range is ≤ 72 hours, or when the endpoint only supports HOURLY (`perpush/series`).
- **MONTHLY** for ranges > 180 days.
- **Endpoints that do not accept `precision`** are immune from this rule (see catalog).

**Estimated-points budget:** 500 (buckets × dimensions per call). If a proposed query would exceed 500, the model announces the chosen lower precision before fetching:

> "I'll use DAILY because hourly over 60 days would be ~1,440 points across platforms. Say 'force hourly' if you want it anyway."

**Hard refuse-cap: 2,000 points.** Even with "force hourly", the model refuses and asks the user to narrow the range.

### `perpush/series` is the budget hot spot

A 30-day HOURLY series for a single push returns ~720 buckets × 4 platforms × 3 metrics ≈ 8,640 numbers. The skill must:

- Only call `perpush/series` when the user explicitly asks for a time-series shape.
- Default to a ≤ 7-day window for `perpush/series`.
- Refuse and propose a narrower range if the window exceeds 14 days (it would exceed the hard cap).

## Pagination Protocol

Two regimes.

**Aggregate endpoints** (`sends`, `opens`, `optins`, `optouts`, `devices`, `events`, `perpush/detail`, `experiment/overview`, etc.): pagination is governed by precision alone — no `next_page` loop.

**Activity log and series endpoints** (`activity/details`, `perpush/series`, `pergroup/series`): may return `next_page`. The model estimates page count before iterating:

- If estimated pages ≤ 10: follow `next_page` until exhausted.
- If estimated > 10: propose narrowing the date range or switching to an aggregate endpoint **before** any call.
- If the user insists, hard truncate at 10 pages and the answer must include: **"Results truncated after 10 pages."** Never silent undercount.

## Freshness and Eventual Consistency

The Freshness column of the catalog tells the model what to caveat in answers:

- **near-real-time** (activity/details): treat numbers as current.
- **~5 min** (sends): mention if the user is asking about something sent in the last hour.
- **~30 min** (perpush/detail, responses, optins, optouts, experiment endpoints, events): delivery stats settle in this window.
- **continuously updating** (opens, perpush/series): **never describe as "stabilized" or "final."** Always frame as "as of right now; continues to grow."
- **daily** (devices): refreshed once per day.

**Do not poll.** If the user pushes back ("I really need to know now"), report current numbers with the live-data caveat. **Do not retry-loop the endpoint.** Recommend re-asking in the appropriate window.

## A/B Test Branching

Validated against the Goat app on 2026-05-28:

- **Primary signal:** the `experiment: bool` field on each `/api/reports/activity/details` row. Capture this during discovery and propagate it.
- **Secondary signal:** `variants: []` in `/api/reports/experiment/overview/{push_id}` indicates not-an-experiment. The endpoint returns **200** with an empty `variants` array and a zeroed `control` block for non-experiment pushes. It does **not** 404.

Flow:

- Activity-log row has `experiment: false` → skip experiment endpoints. Use `/api/reports/perpush/detail/{push_id}` only.
- Activity-log row has `experiment: true` → call `/api/reports/experiment/overview/{push_id}`, then iterate variants via `/api/reports/experiment/detail/{push_id}/{variant_id}` for per-variant detail.
- `push_id` supplied directly (no activity-log discovery) → call `/api/reports/experiment/overview/{push_id}` once. If `variants` is non-empty, proceed with per-variant fetches; otherwise fall through to `/perpush/detail`.

## Error Guidance

Diagnostic order. Do not auto-attribute to a single cause.

**401 on any `/api/reports/*`:**

1. Check the OAuth credential has the `rpt` scope (dashboard Settings → OAuth → edit credential → enable Reports).
2. If scope is enabled, **restart the MCP client** to refresh the cached token.
3. If still failing, verify `client_id`, `client_secret`, and `AIRSHIP_REGION` match the dashboard project.

**404 on `/perpush/*` or `/pergroup/*`:**

- Wrong `push_id` / `group_id`.
- Push not yet processed (just-sent pushes appear in activity-log immediately but per-push stats lag ~30 min).
- Push belongs to a different `app_key` than the one in the MCP credentials.

**400 on `/perpush/series/{push_id}`:**

- Missing `start` or `end` query parameters.
- DAILY precision may be rejected — retry with HOURLY.

**429:** back off; do not retry-loop. Recommend the user re-ask in a few minutes.

## Output Contract

Every metric or insight answer ends with this footer (in order):

1. **Headline metric(s)** — the canonical numbers per the workflow definition.
2. **2-3 supporting metrics** (per-platform, prior-period delta, etc., where meaningful).
3. **Timezone used.**
4. **Freshness caveat** appropriate to the endpoint(s) called.
5. **"Results truncated"** disclosure if pagination was capped.

The footer **does not apply** to existence / metadata / discovery answers ("Is this push an A/B test?", "What's the push_id for the welcome campaign?"). Discovery answers should be concise.

## Vocabulary

The skill answers in **dashboard labels** so AMs see the same words they read in the Airship dashboard. API field names appear in parentheses when developer traceability matters.

| Dashboard label | API field |
|---|---|
| Total Sends | `sends` |
| Total App Opens | `opens` |
| Direct Opens | `direct_responses` |
| Direct Open Rate | `direct_responses / sends` |
| Influenced Opens | `influenced_responses` |
| Influenced Open Rate | `influenced_responses / sends` |
| Opted-in | `opted_in` (devices report) |
| Opted-out | `opted_out` (devices report) |
| Uninstalled | `uninstalled` (devices report) |
| Unique Devices | `unique_devices` |
| Opt-in Opens | `opt_in_opens` |
| Opt-out Opens | `opt_out_opens` |

## % Change vs Prior Period

For well-defined ranges ("last week", "this month"), **strongly preferred** to also fetch the equal-length prior period and show the delta. Mirrors the dashboard's "% change" display.

Skipped when the prior-period fetch would push total points over the 500 budget. In that case the answer says explicitly: "Skipped prior-period comparison to stay within budget. Ask again with a narrower range if you want the delta."

## Dashboard-Only Metrics

Some dashboard metrics are not exposed via the Reports API:

- **Average Time In App** — Engagement Reports App Metrics view only.

If the user asks for one of these, answer:

> "That metric is in the Engagement Reports dashboard but not in the Reports API. View it at https://go.airship.com/reports/engagement."

Do not fabricate a proxy unless the user explicitly asks for one.

## Interpretation Caveats

One factual clarification about what the API actually measures. Surface it when the user is interpreting a delivery shortfall, comparing platforms, or asking what "Sends" means. Do not append to every answer.

> **"Sends" is platform-accepted, not user-displayed.** Airship's `sends` field counts notifications submitted to APNs / FCM. The platforms then apply iOS Focus / Notification Summary / Reduce Interruptions and Android's Notification Organiser before anything reaches a user's lock screen. The Reports API does not expose an "actually displayed" count — the gap between accepted and displayed is real but unmeasurable from these endpoints.

## Field Reference (high-traffic endpoints)

Authoritative definitions from `extdocs/specs/go/spec/reports.yaml`. The full schema lives there; the most-used fields are summarized inline here so the model does not need to dereference docs for routine answers.

### `/api/reports/perpush/detail/{push_id}` response fields

| Field | Type | Meaning |
|---|---|---|
| `push_id` | uuid | Identifier of the push being reported on |
| `app_key` | string | App key for the push |
| `created` | date-time | When the push was created |
| `sends` | integer | Total pushes sent (= alerting + silent + rich) |
| `alerting_sends` | integer | Visible / user-facing pushes sent |
| `silent_sends` | integer | Background / non-alerting pushes sent |
| `direct_responses` | integer | Direct opens — user tapped the notification (SDK-measured) |
| `influenced_responses` | integer | Opens within the attribution window after receiving but not tapping |
| `rich_sends`, `rich_responses`, `rich_deletions` | integer | Message Center counts |
| `platforms.{ios,android,amazon,web}` | object | Same metrics broken out per platform |

### `/api/reports/activity/details` response fields

| Field | Type | Meaning |
|---|---|---|
| `app_key`, `start`, `end`, `limit`, `next_page` | wrapper | Standard listing wrapper (default `limit` 100, follow `next_page` for more) |
| `activities[]` | array | One entry per push delivery in the window |
| `activities[].push_id` | uuid | Identifier of the push |
| `activities[].timestamp` | date-time | When the push was sent |
| `activities[].type` | enum `PUSH \| GROUP` | `GROUP` = group / automation / push-to-local-time; `PUSH` = everything else |
| `activities[].experiment` | bool | **Primary A/B detection signal** |
| `activities[].details.interaction.app.direct` | integer | Direct opens for this push |
| `activities[].details.interaction.app.influenced` | integer | Influenced opens (`-1` means not measured) |
| `activities[].details.interaction.app.indirect` | integer | Indirect opens (open after a different attribution event) |
| `activities[].details.interaction.app.rich_read` | integer | Message Center reads (`-1` means not measured) |
| `activities[].details.delivery.app.alerting` | integer | Alerting pushes delivered |
| `activities[].details.delivery.app.silent` | integer | Silent pushes delivered |
| `activities[].details.delivery.app.rich` | integer | Rich (Message Center) pushes delivered |
| `activities[].details.delivery.web.total` | integer | Web pushes delivered |

`-1` in interaction fields means "not measured for this push type" — do not report it as zero.

### `/api/reports/experiment/overview/{push_id}` response fields

| Field | Type | Meaning |
|---|---|---|
| `experiment_id` | string | Identifier of the experiment |
| `sends`, `direct_responses`, `influenced_responses` | integer | Aggregate counts across variants |
| `web_clicks`, `web_sessions` | integer | Web variant counts |
| `variants[]` | array | Per-variant detail. **Empty for non-experiment pushes** — endpoint still returns 200. |
| `control` | object | Holdout group: `audience_pct`, `sends`, `responses`, `response_rate_pct`, and a nested response breakdown |

## When You Need More Detail

If the model needs information that is not in this skill — for example an unfamiliar response field, the full error code catalog, or a precise default-value reference — consult the canonical sources. Use them only when needed; default to the skill content for routine answers.

**Online (works in every harness, including Claude Desktop):**

- OpenAPI for the Reports endpoints: https://www.airship.com/docs/developer/rest-api/ua/operations/reports/
- Engagement Reports user guide (dashboard terminology AMs see): https://www.airship.com/docs/guides/reports/engagement/
- Messages Reports user guide: https://www.airship.com/docs/guides/reports/messages/

**Local (works when the harness has filesystem access — Claude Code, Cursor, Windsurf — and the user's workspace follows the side-by-side Airship layout with `extdocs` checked out next to `agent-tools-dev`):**

- `../extdocs/specs/go/spec/reports.yaml` — the authoritative Reports OpenAPI spec (~2,100 lines, organized by path)
- `../extdocs/specs/go/examples/reports.yaml` — canonical example payloads
- `../extdocs/content/guides/reports/engagement.md` — dashboard Engagement Reports guide
- `../extdocs/content/guides/reports/message.md` — dashboard Message Reports guide
- `../extdocs/content/guides/reports/activity-log.md` — Activity Log dashboard guide

When to consult each:

- Unknown response field, or you want the precise enum values for a parameter → `extdocs/specs/go/spec/reports.yaml` (search for the path or schema name).
- User asked for a metric you cannot find in any endpoint → `extdocs/content/guides/reports/engagement.md` to confirm whether it is dashboard-only.
- User used a label you do not recognize ("Sequence Performance", "Goals", "NPS") → the matching guide under `extdocs/content/guides/reports/`.

Skip the consultation when the catalog and field reference above already answer the question.

## Examples

See `examples/` for real responses captured from the Goat internal test app on 2026-05-28:

- `activity-details-response.json` — discovery entry point, 100 rows with `experiment` flags
- `perpush-detail-response.json` — `sends`, `alerting_sends`, `silent_sends`, `direct_responses`, `influenced_responses`, `platforms` (iOS/Android/Amazon/web)
- `perpush-series-response.json` — HOURLY series, 30 days, 720 buckets × 4 platforms (illustrates budget concern)
- `experiment-overview-response.json` — non-experiment push (200 with `variants: []`, zeroed `control`)
- `sends-response.json`, `opens-response.json`, `optins-response.json`, `optouts-response.json` — DAILY aggregate arrays
- `devices-response.json` — point-in-time opted-in vs installed

Files include `_status_code` so the model can see the HTTP code that produced each example.

## Workflows Using This Skill

- [Push Performance Analysis](../../workflows/push-performance-analysis/SKILL.md) — "how did this push do?"
- [App Activity Summary](../../workflows/app-activity-summary/SKILL.md) — "how is the app doing this week?"

## Related Documentation

- [Reports API Reference](https://www.airship.com/docs/developer/rest-api/ua/operations/reports/)
- [Engagement Reports dashboard guide](https://www.airship.com/docs/guides/reports/engagement/)
- [Authentication Guide](../../AUTHENTICATION.md)

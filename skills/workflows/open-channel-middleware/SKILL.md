---
name: open-channel-middleware
description: Build a proof-of-concept middleware server that bridges a custom delivery platform (e.g., WhatsApp, Slack) to Airship Open Channels. Generates working code for GCP Cloud Run or AWS Lambda that handles inbound channel registration, Airship webhook validation, and push payload delivery. Use when a customer or technical resource needs to stand up an Open Channels integration quickly.
---

# Open Channel Middleware Workflow

This workflow guides an agent through building a complete proof-of-concept middleware server for Airship Open Channels. The resulting server handles all three Open Channels integration points: channel registration, webhook validation, and push delivery.

## Overview

Open Channels let Airship deliver notifications to any platform with a webhook — WhatsApp, Slack, smart devices, custom apps, etc. Because there is no Airship SDK on these platforms, a middleware server is required to:

1. **Register channels** — Accept new delivery addresses from your system and register them with Airship.
2. **Validate the webhook** — Respond to Airship's validation handshake during dashboard setup.
3. **Receive and deliver pushes** — Accept Airship's push payloads and route them to the actual delivery mechanism.

```
Your System ──POST /register──► Middleware ──POST /api/channels/open──► Airship
                                     ▲
Airship ──GET  /airship/validate──►  │
Airship ──POST /airship/push    ──►  │
                                     └──► Your delivery mechanism (WhatsApp API, Slack, etc.)
```

## Prerequisites

- Airship project with API access (app key + master secret)
- Airship dashboard access to configure the Open Channel and retrieve the validation code
- GCP project (for Cloud Run) or AWS account (for Lambda) with deployment access
- Node.js 18+ (examples below use Node.js; Python equivalents noted where useful)

## Skills Required

- [Open Channel Registration](../../api/open-channel-registration/SKILL.md)
- [Named Users](../../api/named-users/SKILL.md) (optional, for named user association)
- [Tags](../../api/tags/SKILL.md) (optional, for post-registration tagging)

---

## Phase 1: Discovery

Before generating any code, ask the customer these questions. Answers shape the generated output.

1. **Platform name** — What will you name this open channel platform? This becomes the `open_platform_name` in Airship (e.g., `whatsapp`, `slack`, `alexa`). Lowercase, no spaces.

2. **Address concept** — What does the delivery address represent? (e.g., phone number, Slack user ID, device serial number). This shapes the inbound registration contract and documentation.

3. **Deployment target** — Where will this middleware run? GCP Cloud Run and AWS Lambda are common starting points and both have full implementations below, but any environment that can serve HTTP works — container platforms, VMs, existing Node.js/Python services, etc.

4. **Language preference** — Node.js or Python? (Node.js shown below; Python structure noted at end.)

5. **Inbound auth** — How should callers authenticate to the `/register` endpoint, and what value will they use? Options:
   - **API key** (recommended for PoC): Callers supply a secret in the `X-API-Key` header. You'll need an actual value for this — either provide one or the agent can generate a random one for you. This becomes the `INBOUND_API_KEY` environment variable.
   - **No auth** (dev/testing only): Skip authentication entirely — remove the check before going anywhere near production.

6. **Named user association** — Should registration automatically associate the channel with a named user? If yes, what field in the inbound request body carries the named user ID?

7. **Delivery stub** — For this PoC, the push delivery handler can be a stub that logs payloads (you wire up the real delivery SDK later). Or do you have a specific delivery API in mind?

---

## Phase 2: Environment Variables

All sensitive values are injected via environment variables — never hardcoded.

| Variable | Required | Description |
|---|---|---|
| `AIRSHIP_APP_KEY` | Yes | Your Airship project app key |
| `AIRSHIP_MASTER_SECRET` | Yes (or OAuth) | Your Airship master secret — used for Basic auth |
| `AIRSHIP_CLIENT_ID` | Yes (or master secret) | OAuth client ID — preferred over master secret |
| `AIRSHIP_CLIENT_SECRET` | Yes (or master secret) | OAuth client secret |
| `AIRSHIP_OPEN_PLATFORM_NAME` | Yes | The `open_platform_name` configured in the dashboard |
| `AIRSHIP_VALIDATION_CODE` | Yes | The 36-character UUID from the Airship dashboard (after saving the open channel config) |
| `AIRSHIP_WEBHOOK_SECRET` | Yes (if using Signature Hash auth) | The secret key configured in the dashboard for `X-UA-SIGNATURE` verification |
| `INBOUND_API_KEY` | Recommended | API key callers must supply in `X-API-Key` to reach `/register` |

For Cloud Run: store secrets in GCP Secret Manager and expose as env vars in the Cloud Run service configuration.
For Lambda: store secrets in AWS Secrets Manager or SSM Parameter Store and inject as Lambda environment variables.

---

## Phase 3: Cloud Run Implementation (Node.js/Express)

The complete Cloud Run reference implementation (`package.json`, `src/index.js`, `Dockerfile`, `.env.example`, and deploy steps) is in [references/cloudrun-nodejs.md](references/cloudrun-nodejs.md).

---

## Phase 4: Lambda Implementation (Node.js)

The complete AWS Lambda reference implementation (`src/handler.js`, `template.yaml`, and deploy steps) is in [references/lambda-nodejs.md](references/lambda-nodejs.md).

---

## Phase 5: Airship Dashboard Setup

Do this **after** deploying the server (the dashboard requires a live URL).

1. In the Airship dashboard, select the dropdown next to your project name → **Settings**.
2. Under **Channels**, select **Open Channels**.
3. Click **+ Configure new Open Channel** and complete the form:
   - **Display Name**: Human-friendly name (e.g., "WhatsApp PoC")
   - **Name**: Your `open_platform_name` value (e.g., `whatsapp`) — must match `AIRSHIP_OPEN_PLATFORM_NAME` exactly.
   - **Webhook URL**: Your deployed service URL + `/airship` as the root (e.g., `https://your-service.run.app/airship`). Airship will call `/airship/validate` and `/airship/push` relative to this.
   - **Authentication**: Select **Signature Hash** and enter a secret key → set this as `AIRSHIP_WEBHOOK_SECRET` in your environment.
4. Click **Save**. A **Validation Code** UUID appears — set this as `AIRSHIP_VALIDATION_CODE` in your environment and redeploy/update the service.
5. Check the **Enabled** box and click **Update**. Airship will call `GET /airship/validate` — it must return the validation code UUID.

> **Note**: Airship re-validates the endpoint every time you update the configuration. The channel must be enabled for pushes to be delivered.

---

## Phase 6: End-to-End Test

### Step 1 — Verify validation endpoint

```bash
curl https://your-service/airship/validate
# Expected: {"confirmation_code":"<your-uuid>"}
```

### Step 2 — Register a channel

```bash
curl -X POST https://your-service/register \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_inbound_api_key" \
  -d '{
    "address": "+15035556789",
    "opt_in": true,
    "named_user_id": "user_001",
    "tags": ["test"]
  }'
# Expected: {"ok":true,"channel_id":"<uuid>"}
```

### Step 3 — Send a push via Airship API

```bash
curl -X POST https://api.asnapius.com/api/push \
  -H "Authorization: Basic <base64(app_key:master_secret)>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/vnd.urbanairship+json; version=3" \
  -d '{
    "audience": { "open_channel": "<channel_id from step 2>" },
    "device_types": ["open::whatsapp"],
    "notification": { "alert": "Hello from Airship!" }
  }'
```

### Step 4 — Verify delivery log

Check your service logs for the delivery log entry:
- Cloud Run: `gcloud run services logs read open-channel-middleware`
- Lambda: CloudWatch Logs → `/aws/lambda/open-channel-middleware`

Expected log output:
```json
{
  "send_id": "<uuid>",
  "address": "+15035556789",
  "alert": "Hello from Airship!"
}
```

---

## Python Notes

If the customer prefers Python, the same structure applies using **FastAPI** (Cloud Run) or the standard Lambda handler pattern.

Key equivalents:
- Gzip decompression: `import gzip; body = gzip.decompress(raw_bytes)`
- HMAC-SHA256: `import hmac, hashlib; hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()`
- Constant-time compare: `hmac.compare_digest(a, b)`
- Airship API calls: `httpx.AsyncClient` or `requests`

---

## Production Considerations

This workflow produces a **proof of concept**. Before going to production, consider:

- **Async delivery**: The push delivery handler should return 200 immediately and process sends asynchronously (Cloud Tasks, SQS, etc.) to avoid Airship retry storms on slow downstream APIs.
- **Idempotency**: Use `send_id` for deduplication — Airship may retry delivery on non-2xx responses.
- **Batching**: Airship delivers up to 1,000 send objects per request. Batch your downstream API calls accordingly.
- **Monitoring**: Add structured logging and alerting on 502 errors from Airship registration.
- **Secrets rotation**: Use Secret Manager / Secrets Manager with automatic rotation rather than static env vars.

## Related Skills

- [Open Channel Registration](../../api/open-channel-registration/SKILL.md)
- [Named Users](../../api/named-users/SKILL.md)
- [Tags](../../api/tags/SKILL.md)
- [Push Notification](../../api/push-notification/SKILL.md)

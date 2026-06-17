# Cloud Run Implementation (Node.js/Express)

Complete reference implementation for the open-channel middleware on Google Cloud Run. See [the workflow](../SKILL.md) for the overall steps.

### File Structure

```
open-channel-middleware/
├── src/
│   └── index.js        # Main server
├── package.json
├── Dockerfile
└── .env.example
```

### `package.json`

```json
{
  "name": "open-channel-middleware",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "node src/index.js",
    "dev": "node --watch src/index.js"
  },
  "dependencies": {
    "express": "^4.19.0"
  }
}
```

### `src/index.js`

```javascript
import express from 'express';
import { createHmac, timingSafeEqual } from 'crypto';
import { gunzip } from 'zlib';
import { promisify } from 'util';

const gunzipAsync = promisify(gunzip);
const app = express();

const {
  AIRSHIP_APP_KEY,
  AIRSHIP_MASTER_SECRET,
  AIRSHIP_CLIENT_ID,
  AIRSHIP_CLIENT_SECRET,
  AIRSHIP_OPEN_PLATFORM_NAME,
  AIRSHIP_VALIDATION_CODE,
  AIRSHIP_WEBHOOK_SECRET,
  INBOUND_API_KEY,
  PORT = '8080',
} = process.env;

const AIRSHIP_BASE_URL = 'https://api.asnapius.com'; // US; use https://api.asnapieu.com for EU
// Basic auth — used when AIRSHIP_MASTER_SECRET is provided
const AIRSHIP_AUTH = AIRSHIP_MASTER_SECRET
  ? Buffer.from(`${AIRSHIP_APP_KEY}:${AIRSHIP_MASTER_SECRET}`).toString('base64')
  : null;

// OAuth token cache — used when AIRSHIP_CLIENT_ID + AIRSHIP_CLIENT_SECRET are provided
let _tokenCache = { token: null, expiresAt: 0 };

async function getOAuthToken() {
  if (_tokenCache.token && Date.now() < _tokenCache.expiresAt) {
    return _tokenCache.token;
  }
  const res = await fetch('https://oauth2.asnapius.com/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      Accept: 'application/json',
    },
    body: new URLSearchParams({
      grant_type: 'client_credentials',
      client_id: AIRSHIP_CLIENT_ID,
      client_secret: AIRSHIP_CLIENT_SECRET,
      scope: 'chn nu',
    }),
  });
  if (!res.ok) throw new Error(`OAuth token request failed: ${res.status}`);
  const data = await res.json();
  _tokenCache = { token: data.access_token, expiresAt: Date.now() + (data.expires_in - 60) * 1000 };
  return _tokenCache.token;
}

// Returns the Authorization header value — Bearer (OAuth) if client creds present, else Basic
async function getAuthHeader() {
  if (AIRSHIP_CLIENT_ID && AIRSHIP_CLIENT_SECRET) {
    return `Bearer ${await getOAuthToken()}`;
  }
  return `Basic ${AIRSHIP_AUTH}`;
}

// ─── Raw body middleware ──────────────────────────────────────────────────────
// Must read raw bytes before any parsing — needed for gzip decompression
// and Airship signature verification (signature is over the compressed bytes).
app.use((req, res, next) => {
  const chunks = [];
  req.on('data', chunk => chunks.push(chunk));
  req.on('end', async () => {
    try {
      req.rawBody = Buffer.concat(chunks);
      const isGzip = req.headers['content-encoding'] === 'gzip';
      const bodyBytes = isGzip ? await gunzipAsync(req.rawBody) : req.rawBody;
      req.body = JSON.parse(bodyBytes.toString('utf8'));
    } catch {
      req.body = {};
    }
    next();
  });
});

// ─── Auth: inbound registration requests ─────────────────────────────────────
function requireInboundApiKey(req, res, next) {
  if (!INBOUND_API_KEY) return next(); // skip if not configured (dev only)
  if (req.headers['x-api-key'] !== INBOUND_API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

// ─── Auth: Airship webhook signature ─────────────────────────────────────────
// Signature = HMAC-SHA256(secret_key, "{X-UA-TIMESTAMP}:{raw_body_bytes}")
// The signature covers the raw (compressed) bytes, not the decompressed body.
function verifyAirshipSignature(req, res, next) {
  if (!AIRSHIP_WEBHOOK_SECRET) return next(); // skip if not configured (dev only)

  const timestamp = req.headers['x-ua-timestamp'];
  const signature = req.headers['x-ua-signature'];

  if (!timestamp || !signature) {
    return res.status(401).json({ error: 'Missing Airship signature headers' });
  }

  // Reject requests older than 5 minutes (replay attack prevention)
  const age = Math.abs(Date.now() / 1000 - parseInt(timestamp, 10));
  if (age > 300) {
    return res.status(401).json({ error: 'Request timestamp too old' });
  }

  const message = Buffer.from(`${timestamp}:${req.rawBody.toString('utf8')}`);
  const expected = createHmac('sha256', AIRSHIP_WEBHOOK_SECRET).update(message).digest('hex');

  // Constant-time comparison to prevent timing attacks
  try {
    const match = timingSafeEqual(Buffer.from(signature, 'hex'), Buffer.from(expected, 'hex'));
    if (!match) return res.status(401).json({ error: 'Invalid signature' });
  } catch {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  next();
}

// ─── Airship API helpers ──────────────────────────────────────────────────────
async function registerOpenChannel({ address, optIn = true, identifiers, tags, timezone, localeCountry, localeLanguage }) {
  const channel = {
    type: 'open',
    opt_in: optIn,
    address,
    open: {
      open_platform_name: AIRSHIP_OPEN_PLATFORM_NAME,
      ...(identifiers && { identifiers }),
    },
    ...(tags?.length && { tags }),
    ...(timezone && { timezone }),
    ...(localeCountry && { locale_country: localeCountry }),
    ...(localeLanguage && { locale_language: localeLanguage }),
  };

  const res = await fetch(`${AIRSHIP_BASE_URL}/api/channels/open`, {
    method: 'POST',
    headers: {
      Authorization: await getAuthHeader(),
      'Content-Type': 'application/json',
      Accept: 'application/vnd.urbanairship+json; version=3',
    },
    body: JSON.stringify({ channel }),
  });

  return { status: res.status, data: await res.json() };
}

async function associateNamedUser(channelId, namedUserId) {
  const res = await fetch(`${AIRSHIP_BASE_URL}/api/named_users/associate`, {
    method: 'POST',
    headers: {
      Authorization: await getAuthHeader(),
      'Content-Type': 'application/json',
      Accept: 'application/vnd.urbanairship+json; version=3',
    },
    body: JSON.stringify({ channel_id: channelId, named_user_id: namedUserId }),
  });

  return { status: res.status, data: await res.json() };
}

// ─── Route 1: Inbound channel registration ───────────────────────────────────
// Called by your system when a new user/address should be registered.
//
// Request body:
//   address      (required) — the delivery address, e.g. a phone number
//   opt_in       (optional, default true) — consent status
//   named_user_id (optional) — associate channel with this named user
//   identifiers  (optional) — string:string map stored on the channel
//   tags         (optional) — array of strings for segmentation
//   timezone     (optional) — IANA timezone string
//   locale_country (optional) — ISO 3166 two-letter code
//   locale_language (optional) — ISO 639-1 two-letter code
app.post('/register', requireInboundApiKey, async (req, res) => {
  const { address, opt_in, named_user_id, identifiers, tags, timezone, locale_country, locale_language } = req.body;

  if (!address) {
    return res.status(400).json({ error: '`address` is required' });
  }

  const { status, data } = await registerOpenChannel({
    address,
    optIn: opt_in ?? true,
    identifiers,
    tags,
    timezone,
    localeCountry: locale_country,
    localeLanguage: locale_language,
  });

  if (status !== 200 && status !== 201) {
    console.error('Airship registration failed', { status, data });
    return res.status(502).json({ error: 'Channel registration failed', details: data });
  }

  const channelId = data.channel_id;

  if (named_user_id && channelId) {
    const assoc = await associateNamedUser(channelId, named_user_id);
    if (assoc.status !== 200 && assoc.status !== 201) {
      console.warn('Named user association failed', assoc.data);
      // Non-fatal — channel was registered; return partial success
      return res.status(207).json({ ok: true, channel_id: channelId, named_user_association: 'failed' });
    }
  }

  res.status(status === 201 ? 201 : 200).json({ ok: true, channel_id: channelId });
});

// ─── Route 2: Airship webhook validation ─────────────────────────────────────
// Airship GETs this endpoint when you enable the open channel in the dashboard.
// Must return the exact confirmation_code UUID shown in the dashboard.
app.get('/airship/validate', (req, res) => {
  res.json({ confirmation_code: AIRSHIP_VALIDATION_CODE });
});

// ─── Route 3: Airship push delivery ──────────────────────────────────────────
// Airship POSTs here when a push is sent to this open channel platform.
// Body is gzip-compressed JSON (handled by raw body middleware above).
// Must return 200 quickly — Airship will retry on non-2xx.
//
// TODO: Replace the stub delivery logic with your platform's SDK/API call.
app.post('/airship/push', verifyAirshipSignature, (req, res) => {
  // Acknowledge immediately — do heavy work async or in a queue in production
  res.sendStatus(200);

  const { values = [] } = req.body;

  for (const send of values) {
    const { send_id, target, payload } = send;
    const { address, channel_id, identifiers } = target;
    const { alert, title, extra } = payload;

    console.log('Delivering push', {
      send_id,
      address,
      channel_id,
      alert,
      title,
      extra,
      identifiers,
    });

    // TODO: call your delivery mechanism here
    // Example for WhatsApp via Meta Cloud API:
    // await sendWhatsAppMessage({ to: address, text: alert });
  }
});

// ─── Health check ─────────────────────────────────────────────────────────────
app.get('/health', (req, res) => res.json({ ok: true }));

app.listen(PORT, () => {
  console.log(`open-channel-middleware listening on port ${PORT}`);
  console.log(`Platform: ${AIRSHIP_OPEN_PLATFORM_NAME}`);
});
```

### `Dockerfile`

```dockerfile
FROM node:22-slim
WORKDIR /app
COPY package.json .
RUN npm install --omit=dev
COPY src/ src/
ENV PORT=8080
EXPOSE 8080
CMD ["node", "src/index.js"]
```

### `.env.example`

```
AIRSHIP_APP_KEY=your_app_key
# Auth option 1: Basic (app key + master secret)
AIRSHIP_MASTER_SECRET=your_master_secret
# Auth option 2: OAuth client credentials (preferred)
AIRSHIP_CLIENT_ID=your_oauth_client_id
AIRSHIP_CLIENT_SECRET=your_oauth_client_secret
AIRSHIP_OPEN_PLATFORM_NAME=whatsapp
AIRSHIP_VALIDATION_CODE=          # fill in after step 4 below
AIRSHIP_WEBHOOK_SECRET=           # fill in after step 4 below
INBOUND_API_KEY=your_inbound_api_key
```

### Deploying to Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/open-channel-middleware

# Deploy (inject secrets from Secret Manager)
gcloud run deploy open-channel-middleware \
  --image gcr.io/PROJECT_ID/open-channel-middleware \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets="AIRSHIP_APP_KEY=airship-app-key:latest,AIRSHIP_MASTER_SECRET=airship-master-secret:latest,AIRSHIP_WEBHOOK_SECRET=airship-webhook-secret:latest,INBOUND_API_KEY=inbound-api-key:latest" \
  --set-env-vars="AIRSHIP_OPEN_PLATFORM_NAME=whatsapp,AIRSHIP_VALIDATION_CODE=<uuid-from-dashboard>"
```

After deployment, note the Cloud Run service URL — you'll need it for the Airship dashboard.


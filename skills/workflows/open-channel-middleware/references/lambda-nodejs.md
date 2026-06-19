# AWS Lambda Implementation (Node.js)

Complete reference implementation for the open-channel middleware on AWS Lambda. See [the workflow](../SKILL.md) for the overall steps.


Lambda receives API Gateway proxy events. The key differences from Cloud Run:
- No persistent HTTP server — each invocation is a function call.
- API Gateway may base64-encode the body — handle both cases.
- Return a structured response object instead of calling `res.send()`.

### File Structure

```
open-channel-middleware/
├── src/
│   └── handler.js      # Lambda handler
├── package.json
└── template.yaml       # AWS SAM template (optional)
```

### `src/handler.js`

```javascript
import { createHmac, timingSafeEqual } from 'crypto';
import { gunzipSync } from 'zlib';

const {
  AIRSHIP_APP_KEY,
  AIRSHIP_MASTER_SECRET,
  AIRSHIP_CLIENT_ID,
  AIRSHIP_CLIENT_SECRET,
  AIRSHIP_OPEN_PLATFORM_NAME,
  AIRSHIP_VALIDATION_CODE,
  AIRSHIP_WEBHOOK_SECRET,
  INBOUND_API_KEY,
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

function ok(body, statusCode = 200) {
  return { statusCode, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

function err(message, statusCode = 400) {
  return { statusCode, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: message }) };
}

function parseBody(event) {
  // API Gateway sends binary bodies as base64 when isBase64Encoded is true
  let rawBytes = event.isBase64Encoded
    ? Buffer.from(event.body ?? '', 'base64')
    : Buffer.from(event.body ?? '', 'utf8');

  const headers = Object.fromEntries(
    Object.entries(event.headers ?? {}).map(([k, v]) => [k.toLowerCase(), v])
  );

  if (headers['content-encoding'] === 'gzip') {
    rawBytes = gunzipSync(rawBytes);
  }

  return {
    rawBytes,
    body: JSON.parse(rawBytes.toString('utf8')),
    headers,
  };
}

function verifyAirshipSignature(headers, rawBytes) {
  if (!AIRSHIP_WEBHOOK_SECRET) return true;

  const timestamp = headers['x-ua-timestamp'];
  const signature = headers['x-ua-signature'];

  if (!timestamp || !signature) return false;

  const age = Math.abs(Date.now() / 1000 - parseInt(timestamp, 10));
  if (age > 300) return false;

  const message = Buffer.from(`${timestamp}:${rawBytes.toString('utf8')}`);
  const expected = createHmac('sha256', AIRSHIP_WEBHOOK_SECRET).update(message).digest('hex');

  try {
    return timingSafeEqual(Buffer.from(signature, 'hex'), Buffer.from(expected, 'hex'));
  } catch {
    return false;
  }
}

async function handleRegistration(body) {
  const { address, opt_in, named_user_id, identifiers, tags, timezone, locale_country, locale_language } = body;

  if (!address) return err('`address` is required');

  const channel = {
    type: 'open',
    opt_in: opt_in ?? true,
    address,
    open: {
      open_platform_name: AIRSHIP_OPEN_PLATFORM_NAME,
      ...(identifiers && { identifiers }),
    },
    ...(tags?.length && { tags }),
    ...(timezone && { timezone }),
    ...(locale_country && { locale_country }),
    ...(locale_language && { locale_language }),
  };

  const regRes = await fetch(`${AIRSHIP_BASE_URL}/api/channels/open`, {
    method: 'POST',
    headers: {
      Authorization: await getAuthHeader(),
      'Content-Type': 'application/json',
      Accept: 'application/vnd.urbanairship+json; version=3',
    },
    body: JSON.stringify({ channel }),
  });

  const regData = await regRes.json();
  if (!regRes.ok) return { statusCode: 502, body: JSON.stringify({ error: 'Registration failed', details: regData }) };

  const channelId = regData.channel_id;

  if (named_user_id && channelId) {
    const assocRes = await fetch(`${AIRSHIP_BASE_URL}/api/named_users/associate`, {
      method: 'POST',
      headers: {
        Authorization: await getAuthHeader(),
        'Content-Type': 'application/json',
        Accept: 'application/vnd.urbanairship+json; version=3',
      },
      body: JSON.stringify({ channel_id: channelId, named_user_id }),
    });

    if (!assocRes.ok) {
      return ok({ ok: true, channel_id: channelId, named_user_association: 'failed' }, 207);
    }
  }

  return ok({ ok: true, channel_id: channelId }, regRes.status === 201 ? 201 : 200);
}

function handlePushDelivery(body) {
  const { values = [] } = body;

  for (const send of values) {
    const { send_id, target, payload } = send;
    console.log('Delivering push', { send_id, address: target.address, alert: payload.alert });

    // TODO: call your delivery mechanism here
    // await sendWhatsAppMessage({ to: target.address, text: payload.alert });
  }

  return { statusCode: 200, body: '' };
}

export const handler = async (event) => {
  const method = (event.httpMethod || event.requestContext?.http?.method || '').toUpperCase();
  const path = event.path || event.rawPath || '/';
  const headers = Object.fromEntries(
    Object.entries(event.headers ?? {}).map(([k, v]) => [k.toLowerCase(), v])
  );

  // Health check
  if (method === 'GET' && path === '/health') {
    return ok({ ok: true });
  }

  // Airship validation handshake
  if (method === 'GET' && path === '/airship/validate') {
    return ok({ confirmation_code: AIRSHIP_VALIDATION_CODE });
  }

  // Inbound channel registration
  if (method === 'POST' && path === '/register') {
    if (INBOUND_API_KEY && headers['x-api-key'] !== INBOUND_API_KEY) {
      return err('Unauthorized', 401);
    }
    const { body } = parseBody(event);
    return handleRegistration(body);
  }

  // Airship push delivery
  if (method === 'POST' && path === '/airship/push') {
    const { rawBytes, body } = parseBody(event);
    if (!verifyAirshipSignature(headers, rawBytes)) {
      return err('Invalid signature', 401);
    }
    return handlePushDelivery(body);
  }

  return { statusCode: 404, body: 'Not Found' };
};
```

### `template.yaml` (AWS SAM)

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Runtime: nodejs22.x
    Timeout: 30
    Environment:
      Variables:
        AIRSHIP_APP_KEY: !Sub '{{resolve:ssm:/open-channel/airship-app-key}}'
        AIRSHIP_MASTER_SECRET: !Sub '{{resolve:ssm:/open-channel/airship-master-secret}}'
        AIRSHIP_WEBHOOK_SECRET: !Sub '{{resolve:ssm:/open-channel/airship-webhook-secret}}'
        INBOUND_API_KEY: !Sub '{{resolve:ssm:/open-channel/inbound-api-key}}'
        AIRSHIP_OPEN_PLATFORM_NAME: whatsapp
        AIRSHIP_VALIDATION_CODE: FILL_IN_AFTER_DASHBOARD_SETUP

Resources:
  OpenChannelMiddleware:
    Type: AWS::Serverless::Function
    Properties:
      Handler: src/handler.handler
      Events:
        ApiGateway:
          Type: HttpApi
          Properties:
            Path: /{proxy+}
            Method: ANY
```

```bash
# Deploy
sam build && sam deploy --guided
```

After deployment, note the API Gateway endpoint URL — you'll need it for the Airship dashboard.


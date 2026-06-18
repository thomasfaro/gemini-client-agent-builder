# Gemini Client Intelligence Agent — Prompt Builder

Single-page tool that generates the system prompt (and conversation starters) for a
Gemini Enterprise **Client Intelligence Agent** with orchestrator + specialized
research subagents (`research_comms`, `research_meetings_docs`, `research_support_eng`,
`research_commercial`, `research_web`, `report_writer`, `email_delivery`).

Scans internal Airship sources (Gmail, Calendar, Drive, Slack, Zendesk, Jira,
Salesforce) plus public web context for a given client.

## Project layout

```
gemini-client-agent-prompt-builder/
├── gemini-client-agent-prompt-builder.html   # UI + builder logic (source of truth)
├── gemini-client-agent-prompt-locales.js     # en / fr / de strings
├── build-share-bundle.js                     # bundles locales into share/index.html
├── share/
│   └── index.html                            # self-contained shareable bundle
└── README.md
```

## Development

Open `gemini-client-agent-prompt-builder.html` in a browser (loads `gemini-client-agent-prompt-locales.js`
from the same folder). Edit the HTML or locales, then rebuild the shareable bundle:

```bash
cd agent-tools/gemini-client-agent-prompt-builder
node build-share-bundle.js
```

## Share / distribute

`share/index.html` is fully self-contained — no other files required.

- **Open:** double-click `share/index.html` (runs offline in any modern browser).
- **Share:** send `share/index.html` alone, or zip this folder.

## Related

- **ADK alternative:** `../../client-intelligence-agent/` at the workspace root (code-first
  agent with the same config fields). Export the generated prompt into
  `client-intelligence-agent/prompts/orchestrator.md`.

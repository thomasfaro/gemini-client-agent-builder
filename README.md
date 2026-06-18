# Gemini Client Intelligence Agent — Prompt Builder

A single-page web tool that generates the full system prompt (and conversation
starters) for a **Gemini Enterprise** "Client Intelligence Agent" built as an
**orchestrator + specialized subagents** flow:

- `research_comms` (Gmail + Slack)
- `research_meetings_docs` (Calendar + Drive)
- `research_support_eng` (Zendesk + Jira)
- `research_commercial` (Salesforce)
- `research_web` (Google Search)
- `report_writer` (synthesis + formatting, no connectors)
- `email_delivery` (scheduled email send)

It scans internal sources for a given client to act as a single source of truth
for the account team, with inline clickable source links and alerting.

## Use it

**Hosted (GitHub Pages):** https://thomasfaro.github.io/gemini-client-agent-builder/

Fill in the client identity fields, pick the connectors and output language
(EN / FR / DE), then copy the generated prompt into Gemini Agent Designer.

## Run locally

Just open `index.html` in any modern browser — it is fully self-contained and
works offline. No server or install required.

## Develop

The source of truth is split for maintainability:

- `gemini-client-agent-prompt-builder.html` — UI + builder logic
- `gemini-client-agent-prompt-locales.js` — en / fr / de strings

When developing, open `gemini-client-agent-prompt-builder.html` (it loads the
locales file from the same folder). After editing either file, rebuild the
self-contained page:

```bash
node build-share-bundle.js
```

This regenerates the root `index.html` (the file GitHub Pages serves) with the
locales inlined.

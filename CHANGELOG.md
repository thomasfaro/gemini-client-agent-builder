# Airship Agent Tools Changelog

[All Releases](https://github.com/urbanairship/agent-tools/releases)

## Version 1.0.0 - May 20, 2026
Initial public release of the Airship Agent Tools MCP server and skill bundle.

### Changes
- Added the `airship-mcp` MCP server with tools for push notifications, channel and segment management, build verification, SDK migration, and skill discovery.
- Added the `call_airship_api` tool for executing arbitrary authenticated Airship API requests as the runtime for skill-driven workflows.
- Added Claude Code plugin packaging via `.claude-plugin/` so all skills are available as `/airship:<skill-name>` slash commands.
- Added MCPB manifest for one-click installation in Claude Desktop, including `user_config` for OAuth credentials.
- Added skill content for the Push API, Message Center, RTDS, Wallet, and end-to-end workflows.

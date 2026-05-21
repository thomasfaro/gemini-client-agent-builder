# Airship Agent Tools Changelog

[All Releases](https://github.com/urbanairship/agent-tools/releases)

## Version 1.1.0 - May 21, 2026
Security and process improvements from the Anthropic MCP Directory review, plus versioning and release tooling.

### Changes
- Added a `privacy_policies` declaration in the MCPB manifest.
- Marked the OAuth `client_id` as `sensitive` so Claude Desktop stores it in the system keychain.
- Constrained `project_path` arguments on `install_skills` and `verify_build` to the user's home directory, overridable with `AIRSHIP_MCP_PROJECT_ROOTS`.
- Reduced HTTP error logging in the migration fetcher to status code and repo path instead of full exception strings.
- Fixed the broadcast audience guard in `send_custom_push` and `call_airship_api` to walk `or`, `and`, and `not` composers so structurally valid bypasses can no longer reach the push endpoint.
- Added `CHANGELOG.md`, `DEV_README.md`, and `scripts/update-version.sh` to formalize the release process.

## Version 1.0.0 - April 16, 2026
Initial public release of the Airship Agent Tools MCP server and skill bundle.

### Changes
- Added the `airship-mcp` MCP server with tools for push notifications, channel and segment management, build verification, SDK migration, and skill discovery.
- Added the `call_airship_api` tool for executing arbitrary authenticated Airship API requests as the runtime for skill-driven workflows.
- Added Claude Code plugin packaging via `.claude-plugin/` so all skills are available as `/airship:<skill-name>` slash commands.
- Added MCPB manifest for one-click installation in Claude Desktop, including `user_config` for OAuth credentials.
- Added skill content for the Push API, Message Center, RTDS, Wallet, and end-to-end workflows.

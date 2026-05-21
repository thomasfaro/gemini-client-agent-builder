# Airship Agent Tools - Developer Guide

Internal-facing notes for working on this repo and performing releases.

## Repository layout

`agent-tools-dev` (this repo) is the development repo. `agent-tools` is the public repo. Day-to-day work happens on `agent-tools-dev/main`. Releases are tagged here and pushed to the public repo.

## One-time setup

Add the public mirror as a remote:

```bash
git remote add public git@github.com:urbanairship/agent-tools.git
```

After that you should see:

```bash
$ git remote -v
origin  git@github.com:urbanairship/agent-tools-dev.git (fetch)
origin  git@github.com:urbanairship/agent-tools-dev.git (push)
public  git@github.com:urbanairship/agent-tools.git     (fetch)
public  git@github.com:urbanairship/agent-tools.git     (push)
```

## Release process

Versioning follows SemVer. The canonical version lives in `manifest.json` and is mirrored into `pyproject.toml` by the bump script.

1. **Bump the version.**

   ```bash
   scripts/update-version.sh 1.1.0
   ```

2. **Update `CHANGELOG.md`.** Add a new `## Version X.Y.Z - Month Day, Year` section above the previous entry, with a one-line summary and a `### Changes` bulleted list. Match the format already in the file.

3. **Commit.**

   ```bash
   git commit -am "Release 1.1.0"
   git push origin main
   ```

4. **Sync main to the public mirror.**

   ```bash
   git push public main
   ```

5. **Tag and push the tag to both remotes.**

   ```bash
   git tag -a v1.1.0 -m "version 1.1.0"
   git push origin v1.1.0
   git push public v1.1.0
   ```

6. **Build the MCPB bundle.**

   ```bash
   mcpb pack
   ```

   This produces `airship-mcp.mcpb` at the repo root. The bundle is a build artifact and is gitignored.

7. **Create a GitHub Release** on `urbanairship/agent-tools` for the tag, paste the CHANGELOG entry as the release body, and attach `airship-mcp.mcpb`.

8. **Submit (or re-submit) the bundle** to the Anthropic MCP Directory if the release is meant for distribution there.

## Local development

```bash
uv sync
uv run airship-mcp
```

Required environment for tools that hit the Airship API:

- `AIRSHIP_APP_KEY`
- `AIRSHIP_CLIENT_ID`
- `AIRSHIP_CLIENT_SECRET`
- `AIRSHIP_REGION` (optional, defaults to `us`)

See `.env.example`.

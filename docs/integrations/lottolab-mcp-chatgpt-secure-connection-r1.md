# LottoLab read-only MCP → ChatGPT Secure MCP Tunnel

This runbook connects the existing LottoLab read-only MCP server to ChatGPT
through OpenAI's Secure MCP Tunnel. It does not add a second MCP server, HTTP
proxy, public database endpoint, or write-capable tool.

## Contract and boundary

- Local MCP transport: newline-delimited JSON-RPC over stdio.
- Local startup command:

  ```sh
  uv run --no-sync --project "$REPO_ROOT" python "$REPO_ROOT/tools/lottolab_mcp_stdio.py"
  ```

- Local network listener: none. The MCP server does not bind a host or port.
- Tunnel direction: `tunnel-client` makes outbound HTTPS requests to OpenAI;
  the private MCP process is started inside the same local trust boundary.
- Tunnel destination: the checked-in LottoLab launcher above. The launcher
  delegates to `lottolab.interfaces.mcp.server:serve_stdio`.
- Data access: the existing Storage Authority Registry/Resolver only. The MCP
  input schema contains no database path, filesystem path, SQL, or execution
  command.
- Public payloads: private locations are sanitized by the existing MCP server.

OpenAI's current Secure MCP Tunnel guide describes this stdio/HTTP setup,
outbound-only path, `tunnel_id`, `CONTROL_PLANE_API_KEY`, and the
`init`/`doctor`/`run` commands:
<https://developers.openai.com/api/docs/guides/secure-mcp-tunnels>.

## One-time owner/platform setup

The following values are account-scoped and must be created or supplied by an
Owner or Platform organization administrator. Never commit the runtime API
key, put it in a tracked `.env` file, or paste it into an MCP response.

1. In OpenAI Platform tunnel settings, create or select a tunnel and record its
   `tunnel_id`.
2. Ensure the operator has Tunnels Read + Use. Creating or editing a tunnel
   additionally requires Tunnels Read + Manage.
3. Associate the tunnel with the ChatGPT workspace that will create the app.
   A tunnel associated only with a personal Platform organization may not
   appear in an Enterprise/Edu workspace.
4. Install the latest `tunnel-client` release using the download link in
   Platform tunnel settings or the latest public release. Keep the local
   install outside this repository.
5. Load the runtime API key into the current shell from an OS/user secret
   manager. Do not echo it or save it in this repository:

   ```sh
   export CONTROL_PLANE_API_KEY='<loaded from an OS/user secret manager>'
   export LOTTOLAB_TUNNEL_ID='tunnel_<owner-created-id>'
   ```

The placeholder values above are not valid credentials. Replace them only in
the local shell or the tunnel-client's user-level configuration.

## Start

Run from the repository root. `REPO_ROOT` is used only to construct the local
stdio command and is never sent as MCP result data.

```sh
REPO_ROOT="$(git rev-parse --show-toplevel)"
MCP_COMMAND="uv run --no-sync --project $REPO_ROOT python $REPO_ROOT/tools/lottolab_mcp_stdio.py"

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile lottolab-readonly \
  --tunnel-id "$LOTTOLAB_TUNNEL_ID" \
  --mcp-command "$MCP_COMMAND"

tunnel-client doctor --profile lottolab-readonly --explain
tunnel-client run --profile lottolab-readonly
```

Keep `tunnel-client run` running while ChatGPT creates the app or scans tools.
Do not add `--mcp-server-url` for this R1 server: it is stdio-only and has no
local HTTP endpoint.

## Status, stop, and restart

Status is local and read-only:

```sh
tunnel-client doctor --profile lottolab-readonly --explain
pgrep -x tunnel-client
```

The Secure MCP Tunnel client also provides loopback-only `/healthz`, `/readyz`,
`/metrics`, and `/ui` surfaces when it reports a local admin URL. Keep those
surfaces loopback-only; use them only from the same machine.

Stop the foreground `tunnel-client run` with `Ctrl-C`. For a separately managed
process, stop only the PID owned by this profile using the platform's normal
termination path; do not use a broad process-name kill and do not force-kill a
process that has not been identified.

Restart by running the Start procedure again and repeating `doctor` before
using ChatGPT. No always-on daemon or launch-at-login service is installed by
this R1 task.

## ChatGPT app handoff

The current OpenAI ChatGPT workflow is web-only and requires Developer Mode
access. Depending on the workspace, use either Workspace Settings → Apps →
Create or Settings → Apps → Create after the relevant admin enables Developer
Mode.

Use these values:

| Field | Value |
| --- | --- |
| App name | `LottoLab Read-Only` |
| Connection | `Tunnel` |
| Tunnel | Select the associated tunnel, or enter the owner-created `tunnel_id` if the UI requests it |
| Authentication | Tunnel control-plane authentication is handled by `tunnel-client`; do not enter a database credential or local path |
| Other metadata | None beyond the fields shown by the current ChatGPT UI |

The app does not need a local MCP URL. ChatGPT reaches the OpenAI-hosted
tunnel endpoint; the local server remains stdio-only.

Owner steps:

1. Enable Developer Mode if the workspace requires it.
2. Open Settings or Workspace Settings → Apps → Create.
3. Choose `Tunnel`, select the associated tunnel, and enter `LottoLab Read-Only`.
4. Click **Scan Tools** and wait for discovery.
5. Compare the scanned list with the server inventory below.
6. Create the development app and enable it.
7. Open a new normal ChatGPT web chat and select the app for the message.
8. Run the acceptance queries below.

Custom apps are not used by Agent mode. Deep research supports custom apps for
read/fetch actions only. The primary acceptance target is a normal ChatGPT web
chat with this app explicitly selected.

## Tool-scan acceptance checklist

`SERVER_DISCOVERED_TOOLS` must equal `CHATGPT_SCANNED_TOOLS`:

1. `list_lottery_types`
2. `list_historical_runs`
3. `get_strategy_window_ranking`
4. `get_strategy_replay_summary`
5. `get_strategy_match_summary`
6. `get_strategies_by_match_threshold`
7. `get_strategy_best_prize`
8. `get_draw`

No other tool is expected. In particular, no tool may accept arbitrary SQL,
filesystem paths, database paths, prediction execution, replay execution, or
write operations.

## End-to-end acceptance queries

Use the actual tool surface; do not ask ChatGPT to invent a ranking query when
the returned evidence says that ranking is unavailable.

- Availability: `查詢目前 LottoLab 可以讀取哪些彩種與 evidence。`
- BIG_LOTTO: `查詢大樂透目前可用的歷史資料摘要。`
- POWER_LOTTO: `查詢威力彩目前 canonical historical evidence。`
- DAILY_539: `查詢今彩539目前 canonical historical evidence。`
- Fail closed: ask for an unsupported lottery type and confirm an
  `INVALID_LOTTERY_TYPE` error.
- Authority safety: request an unresolved authority and confirm
  `AUTHORITY_UNRESOLVED`, `EVIDENCE_UNAVAILABLE`, or `STORAGE_UNAVAILABLE` as
  appropriate; no alternate database may be selected.
- Path redaction: provide an invalid strategy identifier containing a private
  path and confirm that the response contains no private absolute path.

## Operational security checks

Before calling the connection ready, confirm:

- no public database port or filesystem service exists;
- the MCP server has no HTTP listener and no router port-forwarding is used;
- the tunnel profile points only at the checked-in launcher;
- `SERVER_DISCOVERED_TOOLS` contains exactly the eight read-only tools above;
- no runtime API key, tunnel credential, OAuth secret, or local absolute path
  appears in Git, committed files, logs intended for publication, or MCP
  payloads;
- invalid requests remain sanitized and fail closed after remote invocation.

## Current implementation verification

The MCP implementation is pinned at commit
`8121f1b2c445d1d959ac91c25cfd38f2a4246bd7` / tree
`776677d971db9613e8daee9cf434c79718e7e2fb`. This document and
`tools/lottolab_mcp_stdio.py` are deployment-support additions; they do not
change the query service, authority resolver, or tool definitions.

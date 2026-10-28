# Usage and recovery

[Back to project](../README.md)

Run commands from the repository root.

## Run the bridge

From the cloned repository:

```powershell
python src/bridge.py init
python src/bridge.py submit --url https://www.python.org/robots.txt --filename robots.txt --task-id example-001
python src/bridge.py status example-001
python src/bridge.py list
python src/bridge.py stop
python src/bridge.py start
```

`init` creates a dedicated Codex thread and sends one short initial turn so it has durable history. It uses your existing Codex authentication; it does not copy credentials. This initial turn can consume quota. `submit` persists the task and requests a detached worker immediately. Acknowledging submission does not mean execution has succeeded. An exclusive OS lock allows only one worker per state directory.

Default state directory: `~/.hame-codex-bridge`. Use `python src/bridge.py --home PATH <command>` to choose another local state directory. Downloads go inside that directory's `downloads/` folder. Keep that directory private to the local user. `stop` finishes the current operation before exiting. After an OS reboot, run `start` or submit another task; no startup service or recurring scheduler is installed.

Downloads require HTTPS URLs without embedded credentials, query strings or fragments. Redirects and overwrites are rejected. Use the final authorized URL and a new filename. Default size limit is 64 MiB; configure `--max-bytes` up to 8 GiB. Provide `--sha256 HEX` from a trusted source when available. Without an expected hash, `verified` means transfer and local-file checks passed, not that the content's authenticity was established. Downloads are never executed.

## Notification policy

The default `notify_on` is `["failed", "needs_attention"]`. A successful task is `completed` with notification `suppressed`; no Codex connection or turn is opened for it. Inspect local state when you want the result.

To request a success callback too:

```powershell
python src/bridge.py submit --url https://www.python.org/robots.txt --filename other-robots.txt --task-id example-002 --notify-on completed failed needs_attention
```

`--notify-on` without values suppresses all callbacks. Policies are persisted with each task. Reusing a task ID with identical arguments and policy is idempotent; changing either is rejected.

Callbacks go to the dedicated bridge conversation, **not automatically to whichever desktop chat submitted the task**. The bridge owns a separate App Server process over stdio. Another active writer or an exhausted Codex quota can block a callback. Immediate display of the dedicated thread in the desktop application is not guaranteed.

## MCP integration

Register with absolute paths appropriate for your installation:

```text
codex mcp add hame_bridge -- /absolute/path/to/python /absolute/path/to/src/bridge.py mcp
```

On Windows, quote absolute paths containing spaces. Restart/reload the client if it already cached the tool catalog. The tool is `delegate_download`:

```json
{
  "url": "https://www.python.org/robots.txt",
  "filename": "robots.txt",
  "task_id": "example-003",
  "notify_on": ["failed", "needs_attention"]
}
```

Optional arguments: `sha256`, `max_bytes`, `notify_on`. Initialize the same state directory with `init` before using MCP. Authorize the URL and destination before delegation; this tool downloads content and does not install software.

## Persistence and recovery

SQLite uses WAL and synchronous=FULL. Execution state and notification state are stored separately. Queued tasks survive restart. Interrupted running tasks become `needs_attention`, rather than being executed again blindly. Partials are preserved for inspection. Once callback sending starts, uncertain delivery requires reconciliation; there is no automatic resend loop.

```powershell
python src/bridge.py reconcile example-001
```

Reconciliation reads the dedicated thread's history without starting a turn. It marks a matching delivered task as notified. If no match is found, it does not resend. `notified` means App Server accepted `turn/start`; the separate `callback.status` shows whether the Codex response completed, failed or became unknown. This is not an exactly-once transactional messaging system.

Local files and stdio are the ingress boundary; no network listener is opened by the bridge. Anyone able to modify source or the state directory under your account can control that queue. Tool outputs and task content are untrusted data. Callbacks use a read-only sandbox and reject interactive server approval requests. Error evidence is limited to avoid leaking response bodies and credentials.

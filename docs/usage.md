# Usage and recovery

[Back to project](../README.md)

Run commands from the repository root.

The CLI entry point is `src/bridge.py`. MCP exposes `delegate_task` for text analysis, summarization, classification and drafting, and `delegate_download` for HTTPS transfers. Both share the queue and per-task callback selection. Arbitrary program execution and general file modification are not implemented.

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

Callbacks go to `reply_to_thread_id` when the caller supplies the target Codex thread and the App Server can resume it. The MCP host does not automatically include the calling conversation's thread ID in tool arguments. To reply in that same conversation, the caller must pass its ID in `reply_to_thread_id`. Otherwise, the callback goes to the dedicated bridge conversation; the initial tool response now reports `callback_target` and `same_conversation` so this fallback is visible immediately. Another active writer or an exhausted Codex quota can still block a callback. Each callback begins with the literal `*Mica*:` marker. It labels the source; it does not give the model a custom personality.

For text analysis, `delegate_task` also accepts `"wait_for_result": true`. This waits up to about ten minutes and returns the final result as the MCP tool response in the requesting conversation, prefixed with `*Mica*:`. No Codex callback turn or conversation ID is needed, and callbacks are suppressed for this mode. Use it when the response needs to appear in the active conversation; use the asynchronous mode for work that should return later. If the wait times out, the queued task may still be running; inspect its local state before retrying with the same task ID.

The Codex executable is resolved afresh before every App Server connection: `HAME_CODEX_EXECUTABLE` takes precedence, followed by the current `PATH`, then the last saved path if that file still exists. If Codex was moved or updated, restart the MCP host to refresh its environment. If `codex` is not on `PATH`, set `HAME_CODEX_EXECUTABLE` to the full path of the current executable in the MCP server environment. When no valid executable is found, the bridge clears its stale saved value and returns an actionable error instead of repeatedly launching a dead path.

## MCP integration

Register with absolute paths appropriate for your installation:

```text
codex mcp add hame_bridge -- /absolute/path/to/python /absolute/path/to/src/bridge.py mcp
```

On Windows, quote absolute paths containing spaces. Restart/reload the client if it already cached the tool catalog. Use `delegate_task` for text analysis:

```json
{
  "kind": "analyze",
  "task": "Summarize the supplied notes and list open questions",
  "input_text": "Notes go here",
  "task_id": "analysis-001",
  "wait_for_result": true
}
```

Use `delegate_download` for HTTPS transfers:

```json
{
  "url": "https://www.python.org/robots.txt",
  "filename": "robots.txt",
  "task_id": "example-003",
  "notify_on": ["failed", "needs_attention"]
}
```

Optional callback fields for either tool: `notify_on`, `reply_to_thread_id`. Download options: `sha256`, `max_bytes`. Initialize the same state directory with `init` before using MCP. The target thread ID is persisted with the task and covered by task idempotency.

Do not omit `reply_to_thread_id` when the result must return to the conversation that submitted the task. This bridge cannot infer that ID from standard MCP tool arguments. The tool response explicitly labels the dedicated-conversation fallback when no target ID was supplied.

## Persistence and recovery

SQLite uses WAL and synchronous=FULL. Execution state and notification state are stored separately. Queued tasks survive restart. Interrupted running tasks become `needs_attention`, rather than being executed again blindly. Partials are preserved for inspection. Once callback sending starts, uncertain delivery requires reconciliation; there is no automatic resend loop.

```powershell
python src/bridge.py reconcile example-001
```

Reconciliation reads the dedicated thread's history without starting a turn. It marks a matching delivered task as notified. If no match is found, it does not resend. `notified` means App Server accepted `turn/start`; the separate `callback.status` shows whether the Codex response completed, failed or became unknown. This is not an exactly-once transactional messaging system.

Local files and stdio are the ingress boundary; no network listener is opened by the bridge. Anyone able to modify source or the state directory under your account can control that queue. Tool outputs and task content are untrusted data. Callbacks use a read-only sandbox and reject interactive server approval requests. Error evidence is limited to avoid leaking response bodies and credentials.

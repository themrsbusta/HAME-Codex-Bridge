# HAME-Codex Bridge

A small, local, source-only bridge between HAME and Codex App Server. It accepts authorized HTTPS download tasks, stores them in SQLite, runs them in an independent worker, and optionally reports results to a dedicated Codex conversation.

Successful routine tasks stay local by default. Only failures and tasks needing attention trigger Codex. Queue monitoring uses conventional Python code, not continuous model inference. Initial conversation setup and requested callbacks can still use Codex quota; no fixed savings are guaranteed.

## How HAME and llama.cpp fit together

```text
Codex / CLI / MCP client
          |
          v
HAME-Codex Bridge ---- SQLite queue and verified download executor
          |
          | local HTTP: /v1/chat/completions
          v
        HAME
          |
          | backend managed by HAME
          v
      llama.cpp ---- GGUF model (CPU or compatible GPU backend)

Selected results -> Codex App Server over local JSON-RPC/stdio
```

llama.cpp is the inference engine: it loads GGUF weights and generates model output using the selected CPU/GPU backend. HAME runs above that engine and manages persistent session history, context budgeting, retrieval and context compaction. It is not a replacement model or a replacement for llama.cpp.

For the HAME 0.92 RC interface used here, a main model handles conversation, and a compiler model can compact accumulated context. In constrained mode, HAME alternates model use when compaction is needed; resident mode has different memory and backend requirements. Configure models, quantizations, context size and GPU layers for your actual hardware. GPU support depends on the installed llama.cpp build and drivers; the bridge itself does not choose devices or load models.

HAME can use llama.cpp server or CLI backends. This bridge talks to HAME's HTTP gateway in either case; it does not directly call llama.cpp's experimental tools API. HAME's chat endpoint does not execute generic shell commands. The bridge's Python executor performs only the structured download action submitted by the caller.

## Requirements

- Python 3.11 or newer; no third-party Python packages.
- A separately installed HAME with a compatible llama.cpp build and your own GGUF models. HAME 0.92 RC is the locally tested interface.
- Codex CLI on PATH, authenticated by its normal login flow, with App Server support.
- A local filesystem supporting hard links for atomic download publication. Windows is the primary tested environment; POSIX locking is implemented but not validated on a real POSIX host.

This repository includes no HAME or llama.cpp binaries, model weights, personal prompts, runtime configuration, credentials, task databases or conversation histories. Install those dependencies separately from their official distributions. llama.cpp: <https://github.com/ggml-org/llama.cpp>. Follow the documentation shipped with your HAME distribution for its supported backend flags; do not assume flags are interchangeable between llama-cli and llama-server.

## Connect to HAME

1. Configure HAME using its own configurator or configuration file. Set the llama.cpp executable paths, main/compiler GGUF paths, supported devices and context/memory limits. Use the sample configuration and documentation shipped with your HAME version.
2. Start HAME bound to `127.0.0.1:8088`. This bridge does not start, modify, stop or reconfigure HAME. Run a single compatible instance and avoid loading additional models beyond available memory.
3. Check the gateway. A runtime response confirms HTTP connectivity, not model readiness:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8088/hame/runtime
   ```

4. Test actual inference through the gateway:

   ```powershell
   $body = @{session_id='bridge-smoke-test'; stream=$false; messages=@(@{role='user'; content='Reply only: OK'})} | ConvertTo-Json -Depth 6
   Invoke-RestMethod http://127.0.0.1:8088/v1/chat/completions -Method Post -ContentType 'application/json; charset=utf-8' -Body $body
   ```

5. For a different local port, set the environment variable **before starting the CLI, worker or MCP host**:

   ```powershell
   $env:HAME_BRIDGE_URL = 'http://127.0.0.1:8089'
   ```

The default is `http://127.0.0.1:8088`. Only literal loopback HTTP origins (`127.0.0.1` or `[::1]`) are allowed. Proxy forwarding is disabled for HAME requests. Existing workers inherit their environment at startup; stop and start them to change the endpoint.

The adapter sends `session_id`, `stream: false` and a user message to `/v1/chat/completions`, then reads `choices[0].message.content`. Each task uses an isolated session. The technical prompt requests exactly `{"action":"download"}`. Only that structured response is accepted; free-form output never becomes shell code. The source contains no custom persona or personal model template. A HAME instance may independently have its own prompts; those are outside this repository.

## Run the bridge

From the cloned repository:

```powershell
python bridge.py init
python bridge.py submit --url https://www.python.org/robots.txt --filename robots.txt --task-id example-001
python bridge.py status example-001
python bridge.py list
python bridge.py stop
python bridge.py start
```

`init` creates a dedicated Codex thread and sends one short initial turn so it has durable history. It uses your existing Codex authentication; it does not copy credentials. This initial turn can consume quota. `submit` persists the task and requests a detached worker immediately. Acknowledging submission does not mean execution has succeeded. An exclusive OS lock allows only one worker per state directory.

Default state directory: `~/.hame-codex-bridge`. Use `python bridge.py --home PATH <command>` to choose another local state directory. Downloads go inside that directory's `downloads/` folder. Keep that directory private to the local user. `stop` finishes the current operation before exiting. After an OS reboot, run `start` or submit another task; no startup service or recurring scheduler is installed.

Downloads require HTTPS URLs without embedded credentials, query strings or fragments. Redirects and overwrites are rejected. Use the final authorized URL and a new filename. Default size limit is 64 MiB; configure `--max-bytes` up to 8 GiB. Provide `--sha256 HEX` from a trusted source when available. Without an expected hash, `verified` means transfer and local-file checks passed, not that the content's authenticity was established. Downloads are never executed.

## Notification policy

The default `notify_on` is `["failed", "needs_attention"]`. A successful task is `completed` with notification `suppressed`; no Codex connection or turn is opened for it. Inspect local state when you want the result.

To request a success callback too:

```powershell
python bridge.py submit --url https://www.python.org/robots.txt --filename other-robots.txt --task-id example-002 --notify-on completed failed needs_attention
```

`--notify-on` without values suppresses all callbacks. Policies are persisted with each task. Reusing a task ID with identical arguments and policy is idempotent; changing either is rejected.

Callbacks go to the dedicated bridge conversation, **not automatically to whichever desktop chat submitted the task**. The bridge owns a separate App Server process over stdio. Another active writer or an exhausted Codex quota can block a callback. Immediate display of the dedicated thread in the desktop application is not guaranteed.

## MCP integration

Register with absolute paths appropriate for your installation:

```text
codex mcp add hame_bridge -- /absolute/path/to/python /absolute/path/to/bridge.py mcp
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
python bridge.py reconcile example-001
```

Reconciliation reads the dedicated thread's history without starting a turn. It marks a matching delivered task as notified. If no match is found, it does not resend. `notified` means App Server accepted `turn/start`; the separate `callback.status` shows whether the Codex response completed, failed or became unknown. This is not an exactly-once transactional messaging system.

Local files and stdio are the ingress boundary; no network listener is opened by the bridge. Anyone able to modify source or the state directory under your account can control that queue. Tool outputs and task content are untrusted data. Callbacks use a read-only sandbox and reject interactive server approval requests. Error evidence is limited to avoid leaking response bodies and credentials.

## Tests and compatibility

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

Tests use temporary state and mocked model/download/callback boundaries. They require no models, internet or Codex inference and do not consume Codex quota. The original integration was exercised locally with HAME 0.92 RC and Codex CLI 0.165.0-alpha.1.2; other versions must be checked against their installed protocol. Generate version-specific schemas with `codex app-server generate-json-schema --out schemas` when diagnosing compatibility.

Official App Server reference: <https://learn.chatgpt.com/docs/app-server>.

## Scope and license

Version 0.1 supports structured HTTPS download delegation. Arbitrary installation, shell execution, desktop application restarts and free-form autonomous planning are outside its scope. MIT license; see [LICENSE](LICENSE). Third-party runtimes and model weights have their own licenses.

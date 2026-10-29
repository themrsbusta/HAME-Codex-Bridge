# HAME-Codex Bridge

A small, local, source-only bridge between HAME and Codex App Server. It accepts authorized HTTPS download tasks, stores them in SQLite, runs them in an independent worker, and optionally reports results to a dedicated Codex conversation.

Successful routine tasks stay local by default. Only failures and tasks needing attention trigger Codex. Queue monitoring uses conventional Python code, not continuous model inference. Initial conversation setup and requested callbacks can still use Codex quota; no fixed savings are guaranteed.

## Repository layout

```text
src/
  bridge.py               CLI, MCP adapter and persistent worker
tests/
  test_bridge.py          Offline automated tests
docs/
  architecture.md         HAME and llama.cpp architecture
  setup.md                Dependencies and HAME connection
  usage.md                CLI, MCP, notifications and recovery
  testing.md              Test commands and compatibility
LICENSE
README.md
```

## Getting started

Configure and start HAME first using the [setup guide](docs/setup.md). From the repository root:

```powershell
python src/bridge.py init
python src/bridge.py submit --url https://www.python.org/robots.txt --filename robots.txt --task-id example-001
python src/bridge.py status example-001
```

Python 3.11+ and an authenticated Codex CLI are required. No third-party Python packages are needed. Initialization creates a dedicated Codex conversation and can consume quota. Text analysis and downloads are supported task types; both stay local on success by default.

`delegate_task` handles text analysis, summarization, classification, and drafting from the task and optional text supplied by the caller. `delegate_download` handles validated HTTPS transfers. Both share the queue, result storage, status and callback policy. The bridge does not execute arbitrary programs or modify arbitrary files; those actions require separately implemented task handlers.

For a text task that must report in the conversation that requested it, set `wait_for_result: true`. The MCP call waits for the local result and returns it in that conversation with the `*Mica*:` marker. This avoids a callback, the caller thread ID, and a second Codex turn. The wait is bounded to about ten minutes. Leave it unset for asynchronous work.

Callbacks can set `reply_to_thread_id` to the Codex thread that should receive the result. The MCP host does not expose the caller's thread ID automatically, so the caller must supply it for a callback to appear in the same conversation. The App Server must be able to resume that thread. If omitted, callbacks go to the bridge's dedicated conversation, and the submission response identifies that destination. Each callback message starts with the literal `*Mica*:` attribution marker and contains the task result; this does not change the analysis prompt or model personality.

The Codex CLI path is refreshed for each App Server connection. The bridge checks `HAME_CODEX_EXECUTABLE`, then the current `PATH`, then the last saved path if it still exists. After moving or updating Codex, restart the MCP host so the bridge receives its new environment; set `HAME_CODEX_EXECUTABLE` to the current executable path when Codex is not on `PATH`.

## Documentation

- [How HAME runs above llama.cpp](docs/architecture.md)
- [Installation and connection to HAME](docs/setup.md)
- [CLI, MCP integration, notifications and recovery](docs/usage.md)
- [Tests and compatibility](docs/testing.md)

## Run tests

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

Submit text analysis with `python src/bridge.py submit-task --task "Summarize these notes" --input-text "..." --task-id example-002`. The MCP tool `delegate_task` takes `kind: "analyze"`, `task`, optional `input_text`, and `task_id`.

Tests run offline without models or Codex inference.

## Scope and license

Version 0.1 supports structured HTTPS download delegation. Arbitrary installation, shell execution, desktop application restarts and free-form autonomous planning are outside its scope. MIT license; see [LICENSE](LICENSE). Third-party runtimes and model weights have their own licenses.

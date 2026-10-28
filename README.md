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

Python 3.11+ and an authenticated Codex CLI are required. No third-party Python packages are needed. Initialization creates a dedicated Codex conversation and can consume quota; successful routine downloads stay local by default.

## Documentation

- [How HAME runs above llama.cpp](docs/architecture.md)
- [Installation and connection to HAME](docs/setup.md)
- [CLI, MCP integration, notifications and recovery](docs/usage.md)
- [Tests and compatibility](docs/testing.md)

## Run tests

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests run offline without models or Codex inference.

## Scope and license

Version 0.1 supports structured HTTPS download delegation. Arbitrary installation, shell execution, desktop application restarts and free-form autonomous planning are outside its scope. MIT license; see [LICENSE](LICENSE). Third-party runtimes and model weights have their own licenses.

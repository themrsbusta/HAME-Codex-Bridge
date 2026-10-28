# Setup and HAME connection

[Back to project](../README.md)

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

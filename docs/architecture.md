# Architecture

[Back to project](../README.md)

The text task handler accepts summaries, classifications, drafting, and analysis requests. The download handler performs HTTPS transfers. Each result follows the task's notification policy. A supplied originating thread ID selects that conversation for the callback. Callback text uses the literal `*Mica*:` prefix as source attribution; it adds no persona instructions.

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

Selected results -> originating Codex thread when configured; otherwise the bridge thread
                    through Codex App Server over local JSON-RPC/stdio
```

llama.cpp is the inference engine: it loads GGUF weights and generates model output using the selected CPU/GPU backend. HAME runs above that engine and manages persistent session history, context budgeting, retrieval and context compaction. It is not a replacement model or a replacement for llama.cpp.

For the HAME 0.92 RC interface used here, a main model handles conversation, and a compiler model can compact accumulated context. In constrained mode, HAME alternates model use when compaction is needed; resident mode has different memory and backend requirements. Configure models, quantizations, context size and GPU layers for your actual hardware. GPU support depends on the installed llama.cpp build and drivers; the bridge itself does not choose devices or load models.

HAME can use llama.cpp server or CLI backends. This bridge talks to HAME's HTTP gateway in either case; it does not directly call llama.cpp's experimental tools API. HAME's chat endpoint does not execute generic shell commands. The bridge's Python executor performs only the structured download action submitted by the caller.

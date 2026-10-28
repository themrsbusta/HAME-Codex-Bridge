# Testing

[Back to project](../README.md)

Run commands from the repository root.

## Tests and compatibility

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests use temporary state and mocked model/download/callback boundaries. They require no models, internet or Codex inference and do not consume Codex quota. The original integration was exercised locally with HAME 0.92 RC and Codex CLI 0.165.0-alpha.1.2; other versions must be checked against their installed protocol. Generate version-specific schemas with `codex app-server generate-json-schema --out schemas` when diagnosing compatibility.

Official App Server reference: <https://learn.chatgpt.com/docs/app-server>.

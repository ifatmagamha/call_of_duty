# Crusoe project reference

This file contains only the Crusoe rules that apply to this repository. The full
workshop reference is external source material and must not be copied here with keys,
billing examples, or unrelated framework patterns.

## Endpoint and fixed models

- Base URL: `https://api.inference.crusoecloud.com/v1/`
- Image extraction: `google/gemma-4-31b-it`
- Audio transcription/extraction: `nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B`
- Situation briefing: `moonshotai/Kimi-K2.6`

## Request rules

- Use the OpenAI Python SDK through `app.infrastructure.crusoe.client.CrusoeClient`.
- Images use `image_url` with a base64 `data:image/...` URL; image content precedes text.
- Audio uses `audio_url` with `{"url": "data:audio/wav;base64,..."}` or MP3.
- Nemotron structured transcription disables thinking with
  `chat_template_kwargs.enable_thinking=false`.
- Kimi structured output disables thinking with
  `chat_template_kwargs.thinking=false`.
- Prefer Pydantic-generated `json_schema`; fall back to `json_object` only when the
  provider rejects schema mode. Validate the complete response and fail closed.
- Models never receive Neo4j credentials, generate Cypher, calculate authoritative
  risk, choose transfers, or mutate the graph.

## Errors and retries

- `400`: validate payload; schema rejection may use the controlled JSON fallback.
- `401/403`: check key validity, project access, expiry, and unsupported parameters.
- `404`: verify the exact model ID and base URL.
- `412`: transient model-server unavailability; retry with bounded backoff.
- `429`: verify the base URL first, then use bounded backoff for genuine rate limits.
- `5xx` and timeouts: safe unavailable response; never expose provider bodies or keys.

## Verification

From `backend` in PowerShell:

```powershell
..\.venv\Scripts\python.exe scripts\diagnose_system.py --crusoe
..\.venv\Scripts\python.exe -m pytest -q tests\contract
$env:RUN_CRUSOE_LIVE='1'
..\.venv\Scripts\python.exe -m pytest -q -m crusoe_live
```

Model listing proves access, contract tests prove request shape, and `crusoe_live`
proves real inference. See `docs/context/crusoe-managed-inference.md` for the full
Crusoe-to-Pydantic-to-Neo4j verification flow. Never commit a real API key.

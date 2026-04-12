Faster Whisper transcription service
======================

This is a standalone HTTP service that wraps the `faster-whisper` runtime and exposes
a LiteLLM/OpenAI-compatible transcription endpoint for Exocort.

Endpoint
--------

- `POST /v1/audio/transcriptions`

Expected request format:

- multipart/form-data
- fields:
  - `file`: audio file upload (required)
  - `model`: optional string. Ignored by the service, but accepted because LiteLLM sends it.
  - `language`: optional language code, e.g. `en`, `es`
  - `prompt`: optional initial transcription prompt
  - `response_format`: optional. If present, must be `json`
  - `temperature`: optional. Accepted and ignored.

Expected response format:

```json
{
  "text": "transcribed text here",
  "task": "transcribe",
  "language": "en",
  "duration": null
}
```

If no speech is detected, it returns HTTP `204`.
If another `response_format` is sent, the service returns HTTP `400`.

This is the format Exocort expects when calling transcription through LiteLLM-compatible endpoints.

Local configuration
-------------------

Service runtime settings are controlled through environment variables loaded from `.env`.
Copy `.env.example` to `.env` and adjust if needed.
Main keys: `FASTER_WHISPER_MODEL_PATH`, `FASTER_WHISPER_DEVICE`,
`FASTER_WHISPER_COMPUTE_TYPE`, `FASTER_WHISPER_BEAM_SIZE`,
`FASTER_WHISPER_LANGUAGE`,
`FASTER_WHISPER_HOST`, `FASTER_WHISPER_PORT`, `FASTER_WHISPER_RELOAD`,
`FASTER_WHISPER_LOG_LEVEL`.
Set `FASTER_WHISPER_LANGUAGE=auto` or leave it unset to let `faster-whisper` auto-detect the language.

Running the service
-------------------

From `services/faster_whisper`:

```bash
uv sync
uv run faster-whisper-service
```

Exocort example:

```yaml
processor:
  asr:
    enabled: true
    model: faster-whisper-local
    api_base: http://127.0.0.1:9000/v1
    api_key_env: ""
    expired_in: 0
```

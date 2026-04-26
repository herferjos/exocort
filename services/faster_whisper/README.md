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

Service runtime settings are loaded from `config.yaml`.
Use `example.yaml` as the base template.
Main keys: `model_size`, `model_path`, `device`, `compute_type`, `beam_size`, `language`,
`host`, `port`, `reload`, `log_level`.
Set `language: auto` or leave it empty to let `faster-whisper` auto-detect the language.
The service checks whether the configured `model_size` is already available inside `model_path`.
If it is not there yet, it downloads it into that directory before loading it.

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

Faster Whisper service
======================

This is a standalone HTTP service that wraps the `faster-whisper` runtime and exposes
an OpenAI-compatible transcription endpoint for the main `exocort` processor.

Endpoint
--------

- `POST /v1/audio/transcriptions`

Request:

- multipart/form-data
- fields:
  - `file`: audio file upload (required)
  - `model`: optional model name (ignored, the service uses its own configured model)
  - `language`: optional language code, e.g. `en`, `es`
  - `prompt`: optional initial transcription prompt

Response JSON:

```json
{ "text": "transcribed text here" }
```

This matches what the main app expects when `stt.json` uses:

- `"format": "openai"`
- `"endpoint_url": "http://127.0.0.1:9000/v1/audio/transcriptions"`

Local configuration
-------------------

Service runtime settings live in `config.py` / `config.toml` in this folder and are
NOT part of the main app config. Example `config.toml`:

```toml
model_path = "medium"
device = "cpu"
compute_type = "int8"
vad_filter = true
beam_size = 5
language = "en"
```

Running the service
-------------------

From the project root, install the service dependencies in a separate environment
or extras, then run:

```bash
python -m services.faster_whisper.app
```

Once running, point your STT config to it, for example:

```json
{
  "format": "openai",
  "endpoint_url": "http://127.0.0.1:9000/v1/audio/transcriptions",
  "model": "faster-whisper-local",
  "api_key": "",
  "steps": [],
  "output": "text"
}
```

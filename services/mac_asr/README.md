# Mac ASR Service

One job: **transcribe audio**. HTTP API that accepts an audio file and returns a LiteLLM/OpenAI-compatible transcription payload using macOS Speech framework.

## Endpoint

- **POST /v1/audio/transcriptions**
  Expected request format: `multipart/form-data`
  Accepted fields: `file` (required), `model`, `language`, `prompt`, `response_format`, `temperature`
  If `language` is omitted, the service resolves it from `MAC_ASR_LOCALE` and can auto-detect when configured.
  Expected JSON response format:

```json
{
  "text": "hola mundo",
  "task": "transcribe",
  "language": "es-ES",
  "duration": null
}
```

  If no speech is detected, it returns HTTP `204`.
  If another `response_format` is sent, the service returns HTTP `400`.
- **GET /health** — readiness and locale.

This is the ASR format Exocort expects when it sends audio through LiteLLM-compatible endpoints.

## Run

From `services/mac_asr`:

```bash
uv sync
uv run mac-asr-service
```

Config: copy `.env.example` to `.env` and adjust. Keys: `MAC_ASR_HOST`, `MAC_ASR_PORT`, `MAC_ASR_RELOAD`, `MAC_ASR_LOCALE`, `MAC_ASR_DEFAULT_LOCALE`, `MAC_ASR_TRANSCRIPTION_TIMEOUT_S`, `MAC_ASR_PROMPT_PERMISSION`, `MAC_ASR_LOG_LEVEL`, `MAC_ASR_DETECT_MODEL`, `MAC_ASR_DETECT_DEVICE`, `MAC_ASR_DETECT_COMPUTE_TYPE`, `MAC_ASR_DETECT_DISCARD_MIN_PROB`, `MAC_ASR_DETECT_DEFAULT_MIN_PROB`.
Set `MAC_ASR_LOCALE` to `auto` to enable language detection by default, or to a fixed locale like `es-ES` to force transcription in that locale.
`MAC_ASR_DEFAULT_LOCALE` is used whenever detection is enabled but its confidence is below 70%; it defaults to `es`.
The service maps bare language codes like `es` to a supported macOS locale before transcription, so you can use either `es` or `es-ES`.
`MAC_ASR_DETECT_DISCARD_MIN_PROB` defaults to `0.5`; below that the audio is discarded with `204`.
`MAC_ASR_DETECT_DEFAULT_MIN_PROB` defaults to `0.7`; between the two thresholds the service falls back to `MAC_ASR_DEFAULT_LOCALE`.

Language detection
------------------

If `MAC_ASR_LOCALE=auto` and the request omits `language` (or uses `auto`),
the service uses `faster-whisper` to detect the language and maps it to a supported
macOS locale before transcription. If the detected probability is below 50%, it discards
the audio and returns `204`. Between 50% and 70%, it falls back to `MAC_ASR_DEFAULT_LOCALE`
instead of trusting the prediction. The detection
model defaults to `tiny` but can be overridden via `MAC_ASR_DETECT_MODEL`.
`faster-whisper` bundles the FFmpeg runtime it needs, so you do not have to install
system `ffmpeg`, but the model weights add size.

## Permissions

macOS Speech Recognition must be allowed (e.g. **System Settings → Privacy & Security → Speech Recognition** for Terminal/Cursor).

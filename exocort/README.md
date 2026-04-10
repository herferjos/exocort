# Exocort capturers and processors

Minimal runner that boots the enabled capture and processing services defined in the YAML config.

1. Install dependencies with `uv sync` from the `exocort` directory.
2. Adjust the YAML file to configure `audio`, `screen`, and `processor` sections.
3. Run the CLI directly:
   ```bash
   uv run exocort
   ```
   The `exocort` command is the package entry point and starts the runner automatically.
If your config file lives somewhere else, pass it explicitly:
   ```bash
   uv run exocort --config /path/to/config.yaml
   ```

The processor watches the configured folder recursively with filesystem events, sends supported image files to OCR and audio files to transcription using LiteLLM-compatible endpoints, and stores a normalized JSON file in the configured output folder while preserving the relative directory structure.

Expected endpoint contracts
---------------------------

Transcription endpoints must expose `POST /v1/audio/transcriptions` and accept `multipart/form-data`
with at least `file`, `model`, and optionally `language`, `prompt`, `response_format`,
`temperature`. The processor stores only:

```json
{
  "text": "transcribed text"
}
```

OCR endpoints must expose `POST /v1/ocr` and accept `multipart/form-data` with at least
`file` and `model`. The processor stores only:

```json
{
  "text": "recognized text"
}
```

LiteLLM still requires the `model` value to include a real provider prefix (e.g., `openai/…`, `mistral/…`)
even when pointing at an adhoc API base; otherwise the SDK raises `LLM Provider NOT provided`.

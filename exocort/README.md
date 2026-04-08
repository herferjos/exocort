# Exocort capturers and processors

Minimal runner that boots the enabled capture and processing services defined in the TOML config.

1. Install dependencies with `uv sync` from the `exocort` directory.
2. Adjust the TOML file to set `capturer.path` and configure the `[capturer.audio]`, `[capturer.screen]`, and optional `[processor]` sections.
3. Run:
   ```bash
   uv run exocort --config exocort/config.toml
   ```
   or use the entry point `exocort` once the package is installed with `uv sync`.

The processor watches a folder recursively, sends supported image files to OCR and audio files to ASR using LiteLLM-compatible endpoints, and stores each response as JSON in the configured output folder while preserving the relative directory structure.

Expected endpoint contracts
---------------------------

ASR endpoints must expose `POST /v1/audio/transcriptions` and accept `multipart/form-data`
with at least `file`, `model`, and optionally `language`, `prompt`, `response_format`,
`temperature`. The expected JSON response is:

```json
{
  "text": "transcribed text",
  "task": "transcribe",
  "language": "en",
  "duration": null
}
```

OCR endpoints must expose `POST /v1/ocr` and accept `multipart/form-data` with at least
`file` and `model`. The expected JSON response follows the Mistral-style OCR schema used
by LiteLLM:

```json
{
  "pages": [
    {
      "index": 0,
      "markdown": "recognized text",
      "images": []
    }
  ],
  "model": "service-name",
  "usage_info": {
    "pages_processed": 1,
    "doc_size_bytes": 12345
  },
  "document_annotation": null,
  "object": "ocr"
}
```

LiteLLM still requires the `model` value to include a real provider prefix (e.g., `openai/…`, `mistral/…`)
even when pointing at an adhoc API base; otherwise the SDK raises `LLM Provider NOT provided`.

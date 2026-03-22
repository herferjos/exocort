# Mac OCR Service

One job: **OCR an image**. HTTP API that accepts an image file and returns text using macOS Vision.

## Endpoint

- **POST /ocr** — `file` (required). Returns `{ "text" }` only.
- **GET /health** — readiness.

## Run

From `services/mac_ocr`:

```bash
uv sync
uv run mac-ocr-service
```

Config: copy `.env.example` to `.env` and adjust. Keys: `MAC_OCR_HOST`, `MAC_OCR_PORT`, `MAC_OCR_LOG_LEVEL`.

# Mac OCR Service

One job: **OCR an image**. HTTP API that accepts either a direct image upload or an OpenAI-compatible chat-completions payload and returns text using macOS Vision.

## Endpoint

- **POST /ocr** — `file` (required). Legacy simple upload endpoint. Returns `{ "text" }`.
- **POST /v1/chat/completions** — OpenAI-compatible request body.
  Expects the minimal fields this project sends: `model` and `messages`.
  The `messages` array must include a `user` message containing an `image_url` item with a base64 `data:` URL.
  Returns a standard chat completion response with OCR text in `choices[0].message.content`.
- **GET /health** — readiness.

## Run

From `services/mac_ocr`:

```bash
uv sync
uv run mac-ocr-service
```

Config: copy `.env.example` to `.env` and adjust. Keys: `MAC_OCR_HOST`, `MAC_OCR_PORT`, `MAC_OCR_LOG_LEVEL`.

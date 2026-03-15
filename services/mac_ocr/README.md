# Mac OCR Service

Native macOS Vision OCR HTTP service. It receives uploaded image files, runs OCR, and returns structured text plus grouped line, row, and block data.

## Endpoints

- `GET /health`
- `GET /status`
- `POST /ocr`

The OCR endpoint expects multipart form data with a single `file` field.

Response:

```json
{
  "lines": [],
  "rows": [],
  "blocks": [],
  "text": "plain text",
  "structured_text": "plain text"
}
```

## Usage

From `services/mac_ocr`:

```bash
uv sync
uv run mac-ocr-service serve
```

Run OCR for one local image:

```bash
uv run mac-ocr-service ocr-file /path/to/image.png
```

Defaults:

- host: `127.0.0.1`
- port: `9091`

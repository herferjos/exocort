# Exocort — Data flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           capturer AGENTS (local)                            │
├─────────────────────────────────┬─────────────────────────────────────────┤
│  exocort-audio                   │  exocort-screen                          │
│  (mic)                          │  (screenshots at FPS)                    │
│                                  │                                          │
│  • VAD segments → WAV            │  • PNG screen + metadata               │
│  • Spool → upload when segment   │  • Upload every new screen               │
│    ends                          │                                          │
└──────────────┬───────────────────┴──────────────────┬──────────────────────┘
               │                                       │
               │  POST /api/audio                       │  POST /api/screen
               │  (file + segment_id, sample_rate, …)   │  (file + screen_id, width, …)
               ▼                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  COLLECTOR (exocort-collector)  —  :8000                                    │
│  Config: config.json                                                         │
│  • Receives audio/screen  →  for each endpoint: format adapter builds        │
│    request and parses response (default, openai, …)  →  forwards to URL     │
└──────────────┬──────────────────────────────────────┬──────────────────────┘
               │                                       │
               │  POST (file + form)                   │  POST (file + form)
               │  to each audio endpoint                │  to each screen endpoint
               ▼                                       ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│  Audio processing APIs       │    │  Image processing APIs       │
│  (e.g. ASR / transcription)   │    │  (e.g. OCR)                  │
│                               │    │                               │
│  Example:                     │    │  Example:                     │
│  mac_asr :9092               │    │  mac_ocr :9091                │
│  /v1/audio/transcriptions     │    │  /ocr                         │
└──────────────────────────────┘    └──────────────────────────────┘
               │
               │  .vault/raw/{YYYY-MM-DD}/*.json
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PROCESSOR (exocort-processor) — reads .vault/raw, writes flat stage data   │
│  .vault/processed/l1, .vault/processed/l2, .vault/processed/l3              │
│  Each stage keeps its own state.json inside its stage folder                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Summary

| Step | Component | Role |
|------|-----------|------|
| 1 | **exocort-audio** | capturers mic, segments with VAD, saves WAV to spool, then POSTs each segment to `COLLECTOR_AUDIO_URL` (default collector `/api/audio`). |
| 2 | **exocort-screen** | capturers screen at configured FPS, POSTs each new screen to `COLLECTOR_SCREEN_URL` (default collector `/api/screen`). |
| 3 | **exocort-collector** | Receives uploads on `/api/audio` and `/api/screen`; reads `config.json`; for each endpoint a **format adapter** (e.g. `default`, `openai`) builds the HTTP request and parses the response, so any ASR/OCR provider can be used without code changes. |
| 4 | **Processing APIs** | External services (ASR, OCR, etc.) receive the forwarded requests and return their results (collector does not store or process the responses). |
| 5 | **exocort-processor** | Reads raw vault events, enriches them into event records, builds a cleaned timeline with super-events, and writes inbox notes derived from those super-events. |

## Where is data stored?

| Data | Stored? | Location |
|------|--------|----------|
| **Audio segments (capturerr)** | Temporarily | `AUDIO_capturer_SPOOL_DIR` (default `./tmp/audio`). Each segment is a `.wav` + `.wav.meta.json`. **Deleted after successful upload** to the collector. |
| **Screen capturers (capturerr)** | No | Frames are sent in memory to the collector. `SCREEN_capturer_TMP_DIR` (default `./tmp/screen`) is available if frames are ever written to disk. |
| **Collector tmp** | Briefly | Incoming audio and screen are written to `COLLECTOR_TMP_DIR` (default `./tmp/collector`) under `audio/{date}/` and `screen/{date}/` with timestamped filenames. **Deleted after** forwarding and vault write. |
| **Collector vault** | Yes | API responses (transcription, OCR, etc.) are stored in `COLLECTOR_VAULT_DIR` (default `./.vault/raw`). Layout: `.vault/raw/{YYYY-MM-DD}/{timestamp}_audio_{id}.json` and `.vault/raw/{YYYY-MM-DD}/{timestamp}_screen_{id}.json`. Each JSON has `timestamp`, `type`, `id`, `meta` (form fields), and `responses` (per endpoint: `url`, `provider`, `status`, `raw`, and optionally `text`). |
| **Processor output** | Yes | `PROCESSOR_OUT_DIR` (default `./.vault/processed`). Layout is flat per stage: `.vault/processed/l1/*.json`, `.vault/processed/l2/*.json`, `.vault/processed/l3/*.json`. Each stage stores its cursor/state at `.vault/processed/<stage>/state.json`. |

Env: per-system temp dirs under `tmp/` — `AUDIO_capturer_SPOOL_DIR`, `SCREEN_capturer_TMP_DIR`, `COLLECTOR_TMP_DIR`; `COLLECTOR_VAULT_DIR`. `tmp/` and `.vault/` are in `.gitignore`.

## Config

- **capturer agents**: `.env` (or env) — `COLLECTOR_AUDIO_URL`, `COLLECTOR_SCREEN_URL` (collector-defined upload endpoints), plus capturer-specific vars.
- **Collector**: `config.json` — `audio` and `screen` are a single endpoint object each (url, method, timeout, headers, optional `format` and `body` for provider-specific adapters).
- **Processor**: `config.toml` includes a configurable pipeline under `[processor]`. See [processor-pipeline.md](/Users/joselu/Proyectos/exocort/docs/processor-pipeline.md) for the full schema and design guide.

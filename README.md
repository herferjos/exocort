# Exocort

Local capture pipeline: record microphone and system audio, capture the screen, send both to a collector that forwards to configurable processing APIs (ASR, OCR, etc.) and persists responses to a vault.

## Overview

Exocort is a modular system of **capture agents** and a **collector**:

| Component | Role |
|-----------|------|
| **exocort-audio** | Captures mic (and optional system loopback), segments speech with VAD, writes WAV to a temp spool, uploads each segment to the collector. |
| **exocort-screen** | Captures the primary display at a configurable FPS and uploads each new frame to the collector. |
| **exocort-collector** | HTTP server that receives audio and screen uploads, forwards them to endpoints defined in `config.json`, and writes API responses to a vault. |

Processing (transcription, OCR, etc.) is done by **external services**; the collector only routes requests and stores results. See [Data flow](docs/data-flow.md) for details.

## Requirements

- **Python 3.11+** (see `requires-python` in [pyproject.toml](pyproject.toml); [uv](https://docs.astral.sh/uv/) or system Python)
- **macOS** for screen capture and typical audio/ASR/OCR setups (other platforms may work for audio-only)

## Installation

The project uses **uv** for environments and dependencies. From the project root:

```bash
# Full install (runner + collector, audio, screen + dev tools).
uv sync --all-extras

# Or: minimal install for running tests only (project + pytest)
uv sync
```

Activate the environment (optional; you can also use `uv run` without activating):

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

Run the runner without activating:

```bash
uv run exocort
```

The lockfile `uv.lock` is the source of truth; after changing dependencies run `uv lock`.

## Configuration

### 1. Environment

Copy the example env and adjust:

```bash
cp .env.example .env
```

Important variables:

- **Runner**: `COLLECTOR_ENABLED`, `AUDIO_CAPTURE_ENABLED`, `SCREEN_CAPTURE_ENABLED` (each `1` or `0`) control which components the `exocort` runner starts.
- **Capture agents**: `COLLECTOR_AUDIO_URL`, `COLLECTOR_SCREEN_URL` (where to POST), plus `AUDIO_CAPTURE_*` / `SCREEN_CAPTURE_*` (see `.env.example`).
- **Collector**: `COLLECTOR_ENABLED`, `COLLECTOR_HOST`, `COLLECTOR_PORT`, `COLLECTOR_CONFIG`, `COLLECTOR_TMP_DIR`, `COLLECTOR_VAULT_DIR`.

Temp dirs are per-component under `tmp/` (e.g. `./tmp/audio`, `./tmp/screen`, `./tmp/collector`). `tmp/` and `vault/` are in `.gitignore`.

### 2. Collector endpoints

The collector forwards uploads according to `config.json`. Point `COLLECTOR_CONFIG` at it (default `config.json` in the working directory). Each endpoint can use a **format** adapter so request/response shape matches the provider (cloud or local).

```bash
# Option A: use a ready-made config (OpenAI cloud or local Mac ASR/OCR)
export COLLECTOR_CONFIG=config/config.openai.json    # or config/config.local_mac.json

# Option B: copy the example and edit
cp config/config.json.example config/config.json
# Edit config/config.json: set audio and screen to your single ASR/OCR endpoint each
```

Per-endpoint fields:

| Field | Description |
|-------|-------------|
| `url` | HTTP endpoint URL |
| `method`, `timeout`, `headers` | Optional; same as before |
| `format` | Adapter code: `default` (multipart file only) or `openai` (OpenAI-style STT/OCR) |
| `body` | Extra form/JSON keys sent with the request (e.g. `{"model": "whisper-1"}`) |

Example: one endpoint per type (e.g. OpenAI for audio, local for screen):

```json
{
  "audio": {
    "url": "https://api.openai.com/v1/audio/transcriptions",
    "format": "openai",
    "body": { "model": "whisper-1" }
  },
  "screen": {
    "url": "http://127.0.0.1:9091/ocr",
    "format": "default"
  }
}
```

See `config/config.json.example` for the full structure.

## Usage

### Single command (runner)

From the project root (where `.env` and `config/` live), run:

```bash
exocort
```

This starts only the components enabled in `.env`: collector (if `COLLECTOR_ENABLED=1`), audio capture (if `AUDIO_CAPTURE_ENABLED=1`), screen capture (if `SCREEN_CAPTURE_ENABLED=1`). The collector is started first; capture agents follow after a short delay. Ctrl+C stops all.

### Run components separately

Run each process in its own terminal if you prefer. The collector must be up before the capture agents.

**1. Start the collector**

```bash
exocort-collector
# Listens on COLLECTOR_HOST:COLLECTOR_PORT (default 127.0.0.1:8000)
```

**2. Start audio capture**

```bash
exocort-audio
# Reads COLLECTOR_AUDIO_URL and AUDIO_CAPTURE_* from .env
```

**3. Start screen capture**

```bash
exocort-screen
# Reads COLLECTOR_SCREEN_URL and SCREEN_CAPTURE_* from .env
```

Logging is controlled by `LOG_LEVEL` (default `INFO`).

## Project structure

```
exocort/
├── settings.py           # Env-based config (single source of truth)
├── capture/
│   ├── audio/            # VAD, device, spool upload, agent
│   └── screen/           # MSS capture, upload loop
├── collector/            # FastAPI app, forward, vault
config/
├── config.json.example   # Collector config template
├── config.openai.json    # OpenAI STT + vision OCR
├── config.local_mac.json # Local Mac ASR (:9092) + OCR (:9091)
docs/
├── data-flow.md          # Architecture and data locations
```

Entry points (see `pyproject.toml`): `exocort` (runner), `exocort-collector`, `exocort-audio`, `exocort-screen`, plus `exocort-processor` if used.

## Data locations

| Data | Location |
|------|----------|
| Audio segments (before upload) | `AUDIO_CAPTURE_SPOOL_DIR` (default `./tmp/audio`) — removed after successful upload |
| Collector temp files | `COLLECTOR_TMP_DIR` (default `./tmp/collector`) — removed after forward and vault write |
| Persisted API responses | `COLLECTOR_VAULT_DIR` (default `./vault`) — `vault/{date}/{timestamp}_audio_{id}.json` etc. |

See [docs/data-flow.md](docs/data-flow.md) for the full picture.

## Development

- **Tests**: From the project root, install with test (and optional collector/audio) deps then run pytest:
  - `pip install -e ".[test,collector]"` (or `uv pip install -e ".[test,collector]"` in your env)
  - `pytest tests/ -v`
  - Tests under `tests/` cover settings, collector config/vault/forward, audio VAD/device, and the runner. Audio tests are skipped if `sounddevice` is not installed.

## License

See repository for license information.

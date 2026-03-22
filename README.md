# Exocort

Local capturer pipeline: record microphone audio, capturer the screen, send both to a collector that forwards to configurable processing APIs (ASR, OCR, etc.) and persists responses to a vault.

## Overview

Exocort is a modular system of **capturer agents** and a **collector**:


| Component             | Role                                                                                                                                                                |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **exocort-audio**     | capturers mic, segments speech with VAD, writes WAV to a temp spool, uploads each segment to the collector.                                                          |
| **exocort-screen**    | capturers the primary display at a configurable FPS and uploads each new frame to the collector.                                                                     |
| **exocort-collector** | HTTP server that receives audio and screen uploads, forwards them to endpoints defined in `config/exocort.toml`, and writes API responses to a vault.               |
| **exocort-processor** | Reads the vault and compacts it into layered memory: L1 clean events, L2 grouped timeline entries, L3 Obsidian-style notes/user model, and optional L4 reflections. |


Processing (transcription, OCR, etc.) is done by **external services**; the collector only routes requests and stores results. See [Data flow](docs/data-flow.md) for details.

## Requirements

- **Python 3.11+** (see `requires-python` in [pyproject.toml](pyproject.toml); [uv](https://docs.astral.sh/uv/) or system Python)
- **macOS** for screen capturer and typical audio/ASR/OCR setups (other platforms may work for audio-only)

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

Everything is now defined in a single TOML file:

```bash
cp config/exocort.toml config/exocort.local.toml
# Edit config/exocort.local.toml
# Optional: point the app to it
export EXOCORT_CONFIG=config/exocort.local.toml
```

Recommended sections:

- `[runtime]`: turns collector/audio/screen/processor on or off.
- `[capturer.audio]` and `[capturer.screen]`: local capturer behaviour.
- `[collector]`: collector bind host/port, upload URLs used by agents, and local storage dirs.
- `[services.audio]`, `[services.screen]`, `[services.processor]`: upstream services with `url`, `method`, `timeout`, `format`, `headers`, and `body`.
- `[processor]`: memory pipeline settings and prompts in the same block.

Temp dirs are still per-component under `tmp/` and data is persisted in `vault/`, but their paths now also live in the same TOML.

Per-endpoint fields:


| Field                          | Description                                                                                                                                               |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `url`                          | HTTP endpoint URL                                                                                                                                         |
| `method`, `timeout`, `headers` | Optional; same as before                                                                                                                                  |
| `format`                       | Adapter code: `default` (multipart file only) or `openai` (OpenAI-style STT/OCR)                                                                          |
| `body`                         | Extra form/JSON keys sent with the request (e.g. `model`, `prompt`). The file is attached separately; use `prompt` to instruct transcription/description. |


Example: one endpoint per type (e.g. OpenAI for audio, local for screen):

```toml
[services.audio]
url = "https://api.openai.com/v1/audio/transcriptions"
format = "openai"
body = { model = "whisper-1" }

[services.screen]
url = "http://127.0.0.1:9091/ocr"
format = "default"
headers = {}
body = {}
```

See `config/exocort.toml` for the full structure.

## Usage

### Single command (runner)

From the project root, run:

```bash
exocort
```

This starts only the components enabled in `[runtime]` inside your TOML file. The collector is started first; the processor and capturer agents follow after a short delay. Ctrl+C stops all.

The processor reads the same shared file and expects `processor` plus `services.processor`. A ready-to-edit example lives at [config/exocort.toml](/Users/joselu/Proyectos/exocort/config/exocort.toml).

### Run components separately

Run each process in its own terminal if you prefer. The collector must be up before the capturer agents.

**1. Start the collector**

```bash
exocort-collector
# Listens on [collector] host/port (default 127.0.0.1:8000)
```

**2. Start audio capturer**

```bash
exocort-audio
# Reads [collector] and [capturer.audio] from the shared TOML
```

**3. Start screen capturer**

```bash
exocort-screen
# Reads [collector] and [capturer.screen] from the shared TOML
```

**4. Start the processor**

```bash
exocort-processor --watch
# Reads [processor] and [services.processor] from the shared TOML
```

Logging is controlled by `[runtime].log_level` (default `INFO`).

## Project structure

```
exocort/
├── settings.py           # Shared TOML-based settings accessors
├── app_config.py         # Shared config loader
├── capturer/
│   ├── audio/            # VAD, device, spool upload, agent
│   └── screen/           # MSS capturer, upload loop
├── collector/            # FastAPI app, forward, vault
├── processor/            # Vault processor
config/
├── exocort.toml          # Single shared config for runtime, capturer, collector and processor
├── config.openai.json    # Legacy JSON example
├── config.local.json     # Legacy JSON example
docs/
├── data-flow.md          # Architecture and data locations
├── architecture/         # Target semantic architecture spec (v2)
```

Entry points (see `pyproject.toml`): `exocort` (runner), `exocort-collector`, `exocort-audio`, `exocort-screen`, plus `exocort-processor` if used.

## Data locations


| Data                           | Location                                                                                                                                  |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Audio segments (before upload) | `[capturer.audio].spool_dir` (default `./tmp/audio`) — removed after successful upload                                                      |
| Collector temp files           | `[collector].tmp_dir` (default `./tmp/collector`) — removed after forward and vault write                                                  |
| Persisted API responses        | `[collector].vault_dir` (default `./vault`) — `vault/{date}/{timestamp}_audio_{id}.json` etc.                                             |
| Processor outputs              | `[processor].out_dir` (default `./out`) — `l1/`, `l2/`, `timeline/`, `notes/`, `user_model.json`, `reflections/`, plus `state/`          |


See [docs/data-flow.md](docs/data-flow.md) for the full picture.
The target processor redesign is documented in [docs/architecture/README.md](docs/architecture/README.md).

## Development

- **Tests**: From the project root, install with test (and optional collector/audio) deps then run pytest:
  - `pip install -e ".[test,collector]"` (or `uv pip install -e ".[test,collector]"` in your env)
  - `pytest tests/ -v`
  - Tests under `tests/` cover settings, collector config/vault/forward, audio VAD/device, and the runner. Audio tests are skipped if `sounddevice` is not installed.

## License

See repository for license information.

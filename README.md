# Exocort

Local capturer pipeline: record microphone audio and capture the screen, process both directly with LiteLLM, and persist results to a local vault.

## Overview

Exocort is a small system of two **capturer agents**:


| Component          | Role                                                                                   |
| ------------------ | -------------------------------------------------------------------------------------- |
| **exocort-audio**  | Captures mic input, segments speech with VAD, and transcribes each segment directly.   |
| **exocort-screen** | Captures the primary display, deduplicates frames, and extracts text directly.         |

Each capturer reads its own service config from `config.toml`, calls LiteLLM directly, and writes results to `vault/raw`.

## Requirements

- **Python 3.11+** (see `requires-python` in [pyproject.toml](pyproject.toml); [uv](https://docs.astral.sh/uv/) or system Python)
- **macOS** for screen capturer and typical audio/ASR/OCR setups (other platforms may work for audio-only)

## Installation

The project uses **uv** for environments and dependencies. From the project root:

```bash
# Full install (runner, audio, screen + dev tools).
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
cp config.toml config.local.toml
# Edit config.local.toml
# Optional: point the app to it
export EXOCORT_CONFIG=config.local.toml
```

Recommended sections:

- `[runtime]`: turns audio/screen on or off.
- `[capturer.audio]` and `[capturer.screen]`: local capturer behaviour.
- `[storage]`: local vault path.
- `[services.audio]`, `[services.screen]`: direct LiteLLM target config.

Audio still uses a local spool under `tmp/`. Persisted model outputs live under `vault/raw`.

Per-endpoint fields:


| Field                | Description                                                                                     |
| -------------------- | ----------------------------------------------------------------------------------------------- |
| `format`             | `transcription`, `chat`, or `responses`                                                         |
| `url`                | Full OpenAI-style endpoint URL. It must match the format path.                                  |
| `provider`           | LiteLLM provider prefix, e.g. `openai`                                                          |
| `model`              | Model name inside that provider                                                                  |
| `timeout`, `headers` | Optional request settings forwarded to LiteLLM                                                   |
| `body`               | Extra LiteLLM kwargs. `body.prompt` is used as the instruction for audio or screen processing.  |


Example: one endpoint per type (e.g. OpenAI for audio, local for screen):

```toml
[services.audio]
format = "transcription"
url = "https://api.openai.com/v1/audio/transcriptions"
provider = "openai"
model = "whisper-1"

[services.screen]
format = "responses"
url = "https://api.openai.com/v1/responses"
provider = "openai"
model = "gpt-4o-mini"
body = { prompt = "Extract all visible text from this screenshot." }
```

See `config.toml` for the full structure.

## Usage

### Single command (runner)

From the project root, run:

```bash
exocort
```

This starts only the components enabled in `[runtime]` inside your TOML file. Ctrl+C stops all.

### Run components separately

Run each process in its own terminal if you prefer.

**1. Start audio capturer**

```bash
exocort-audio
# Reads [capturer.audio] and [services.audio] from the shared TOML
```

**2. Start screen capturer**

```bash
exocort-screen
# Reads [capturer.screen] and [services.screen] from the shared TOML
```

Logging is controlled by `[runtime].log_level` (default `INFO`).

## Project structure

```
exocort/
├── settings.py           # Shared TOML-based settings accessors
├── config.py             # Shared config loader
├── llm.py                # Direct LiteLLM helpers
├── vault.py              # Local JSON persistence
├── capturer/
│   ├── audio/            # VAD, device, spool processing, agent
│   └── screen/           # MSS capture, dedup, OCR loop
docs/
├── data-flow.md          # Architecture and data locations
├── architecture/         # Target semantic architecture spec (v2)
```

Entry points (see `pyproject.toml`): `exocort` (runner), `exocort-audio`, `exocort-screen`.

## Data locations


| Data                        | Location                                                                                                              |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Audio segments (temporary)  | `[capturer.audio].spool_dir` (default `./tmp/audio`) — removed after successful processing                           |
| Persisted model responses   | `[storage].vault_dir` (default `./vault/raw`) — `.json` files with `id`, `timestamp`, `stream`, `model`, and `text` |


See [docs/data-flow.md](docs/data-flow.md) for the full picture.

## Development

- **Tests**: From the project root, install with test deps then run pytest:
  - `pip install -e ".[test]"` (or `uv sync --all-extras` / `uv run pytest`)
  - `pytest -v`
  - Service tests live under `services/*/tests`. Add project tests under `tests/` as needed.

## License

See repository for license information.

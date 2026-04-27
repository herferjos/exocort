# Exocort

<p align="center">
  <img src="./exocort-readme.png" alt="Exocort" width="256" />
</p>

Exocort is a local capture and processing platform designed to turn audio, screen content, and other work artifacts into useful text, normalized files, and durable notes inside a Markdown vault.

The core idea is simple: capture information with as little friction as possible, process it through specialized services, and leave the result in a clear, easy-to-audit file structure.

## What It Does

- Captures audio and screenshots locally.
- Processes OCR, transcription, and note generation through a lightweight backend.
- Integrates with specialized HTTP services for OCR, ASR, and chat completions.
- Keeps the workflow in the filesystem, using `tmp/` as the handoff area and `vault/` as the knowledge base.
- Provides a Tauri desktop interface for starting and stopping the backend from a UI.

## Architecture

The repository is split into three main layers:

- `backend/`: main orchestrator, capture, and processing.
- `services/`: isolated HTTP services for OCR, transcription, and chat models.
- `frontend/`: desktop launcher for controlling the backend and configuration profiles.

That separation is intentional. The backend coordinates, the services handle focused tasks, and the frontend makes operation easier without mixing responsibilities.

## Requirements

- Python 3.11 or 3.12.
- `uv` for Python dependency management.
- Node.js and `npm` if you want to use the frontend.
- macOS if you plan to use the native Speech Recognition or Vision-based OCR services.
- API keys for any providers you configure in `backend/*.yaml` or in the corresponding services.

## Quick Start

### 1. Start the main backend

From `backend/`:

```bash
uv sync
uv run exocort
```

If you want to use a specific configuration:

```bash
uv run exocort --config /path/to/config.yaml
```

### 2. Build the desktop frontend

From `frontend/`:

```bash
npm install
npm run tauri build
```

### 3. Start specialized services

Each service lives in its own folder and runs independently:

```bash
cd services/mac_asr
uv sync
uv run mac-asr-service
```

```bash
cd services/mac_ocr
uv sync
uv run mac-ocr-service
```

```bash
cd services/faster_whisper
uv sync
uv run faster-whisper-service
```

```bash
cd services/llama_cpp
uv sync
uv run llama-cpp-service
```

## Recommended Workflow

1. Configure `backend/config.yaml` or start from one of the profiles included in `backend/`.
2. Decide which capture sources are enabled and which processors you want to use.
3. Start the backend.
4. If you use OCR, ASR, or notes with local or remote providers, start the required services.
5. Review the results in `tmp/processed/` and the notes generated in `vault/`.

## Configuration

The project uses YAML files as its operational contract.

- `backend/example.yaml`: example base configuration.
- `backend/config.yaml`: active backend configuration.
- `backend/local.yaml`: local profile.
- `backend/openai.yaml`, `backend/gemini.yaml`, `backend/mistral.yaml`, `backend/anthropic.yaml`: provider profiles.

The services also include their own `example.yaml` and `config.yaml`.

## Important Directories

- `tmp/raw/`: captured inputs waiting to be processed.
- `tmp/processed/`: normalized outputs.
- `vault/`: notes and persistent knowledge.

These directories are part of the system design, so they should be treated as infrastructure rather than incidental output.

## Security and Permissions

- On macOS, speech recognition may require explicit **Speech Recognition** permission for Terminal or the app you use.
- If you configure external providers, make sure the required API environment variables are set before starting the processes.

## Additional Documentation

- [Backend](./backend/README.md)
- [Frontend](./frontend/README.md)
- [macOS transcription service](./services/mac_asr/README.md)
- [macOS OCR service](./services/mac_ocr/README.md)
- [Faster Whisper service](./services/faster_whisper/README.md)
- [Llama.cpp service](./services/llama_cpp/README.md)

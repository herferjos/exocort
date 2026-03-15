# Exocort

Unified root project with a local collector, capture agents, and an LLM processor that turns events into an Obsidian-style vault.

**Components**
- Collector: FastAPI service that ingests events and stores raw assets.
- Audio Capture: Local microphone capture with VAD, uploads segments to the collector.
- Screen Capture: Local screen snapshots, uploads PNG frames to the collector.
- Processor: Ingests events, runs STT/OCR/LLM, and generates notes.
- Extension: Chrome MV3 extension that sends page text and page views.

**Repository Layout**
- `src/` Python package modules (`collector`, `capture`, `processor`, `ai`, `settings`).
- `extension/` Chrome extension.
- `data/` Generated events and assets (ignored by git).
- `vault/` Generated notes (ignored by git).

## Installation

This project uses `uv` and optional dependency groups.

```bash
uv sync --extra collector --extra audio --extra screen --extra processor
```

## Configuration

Copy the example env file and set the config paths.

```bash
cp .env.example .env
```

Then create the JSON configs for each AI module and point the env vars to them.
The processor now talks to AI backends purely over HTTP using `format`-based
configs (no embedded local runtimes):

```bash
# Pick one example per module
cp config/examples/llm.openai.json config/llm.json
cp config/examples/stt.openai.json config/stt.json
cp config/examples/ocr.openai.json config/ocr.json
```

Other HTTP-based examples are available under `config/examples/`, such as:

- llm.anthropic.json
- llm.gemini-openai.json
- llm.ollama-openai.json
- stt.faster-whisper.json
- ocr.anthropic.json

The `.env` only contains the paths plus API keys:

```text
LLM_CONFIG_PATH=config/llm.json
STT_CONFIG_PATH=config/stt.json
OCR_CONFIG_PATH=config/ocr.json
OPENAI_API_KEY=
GEMINI_API_KEY=
```

### LLM config

Local GGUF (llama-cpp):

```json
{
  "provider": "llama_cpp",
  "model_path": "/path/to/model.gguf",
  "context_length": 4096,
  "n_gpu_layers": -1,
  "threads": 4,
  "batch_size": 512,
  "flash_attention": false,
  "use_mmap": true,
  "offload_kqv": false,
  "seed": null,
  "max_tokens": 4096,
  "temperature": 0.3,
  "max_retries": 3,
  "concurrency": 1
}
```

OpenAI:

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "base_url": "https://api.openai.com/v1",
  "api_key_env": "OPENAI_API_KEY",
  "max_tokens": 4096,
  "temperature": 0.3,
  "max_retries": 3,
  "concurrency": 1
}
```

Gemini:

```json
{
  "provider": "gemini",
  "model": "gemini-2.0-flash",
  "api_key_env": "GEMINI_API_KEY",
  "max_tokens": 4096,
  "temperature": 0.3,
  "max_retries": 3,
  "concurrency": 1
}
```

### LLM processor prompts (required)

The processor prompts now live in `llm.json` (no built-in defaults):

```json
{
  "processor_prompts": {
    "task_plan": {
      "system": "Custom system prompt for planning.",
      "user_template": "Timeline:\\n\\n{timeline}"
    },
    "extract_concept": {
      "system": "Custom system prompt for concept extraction.",
      "user_template": "TEXT:\\n\\n{text}"
    },
    "generate_questions": {
      "system": "Custom system prompt for questions.",
      "user_template": "CONCEPT: {concept_name}\\n\\nTEXT:\\n{text}"
    },
    "daily_render": {
      "system": "Custom daily summary prompt."
    },
    "page_render": {
      "system": "Custom page note prompt."
    }
  }
}
```

### STT config

Local Faster Whisper:

```json
{
  "provider": "faster_whisper",
  "model": "small",
  "language": "",
  "device": "cpu",
  "compute_type": "int8",
  "vad_filter": true
}
```

OpenAI:

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini-transcribe",
  "base_url": "https://api.openai.com/v1",
  "api_key_env": "OPENAI_API_KEY"
}
```

Gemini:

```json
{
  "provider": "gemini",
  "model": "gemini-3.1-flash-lite-preview",
  "api_key_env": "GEMINI_API_KEY"
}
```

Disable STT:

```json
{
  "provider": "none"
}
```

### OCR config

Local Paddle OCR:

```json
{
  "provider": "paddle",
  "languages": ["en", "es"]
}
```

OpenAI:

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "base_url": "https://api.openai.com/v1",
  "api_key_env": "OPENAI_API_KEY"
}
```

Gemini:

```json
{
  "provider": "gemini",
  "model": "gemini-3.1-flash-lite-preview",
  "api_key_env": "GEMINI_API_KEY"
}
```

Disable OCR:

```json
{
  "provider": "none"
}
```

### Multi-step OCR / STT (LLM-based)

Use `steps` + `output` to chain prompts and choose which responses to keep. You can reference previous outputs with `{prev}` or `{<step_id>}`.
For local llama-cpp-python, use provider `llama_cpp` with a `.gguf` model path.
If the model needs vision, add `clip_model_path` (aka `mmproj_path`) for the vision projection model and a `chat_template_path` if your model uses a custom template.
Relative `chat_template_path` entries are resolved from the `ocr.json` directory.

```json
{
  "provider": "llama_cpp",
  "model_path": "/Users/joselu/.cache/lm-studio/models/lmstudio-community/Qwen3.5-4B-GGUF/Qwen3.5-4B-Q4_K_M.gguf",
  "clip_model_path": "/Users/joselu/.cache/lm-studio/models/lmstudio-community/Qwen3.5-4B-GGUF/mmproj.gguf",
  "chat_template_path": "qwen3_5_vl_chat_template.jinja",
  "threads": 6,
  "flash_attention": true,
  "steps": [
    {
      "id": "ocr",
      "system_prompt": "Task:\\n1) OCR from full image including all layout text. Avoid early termination, give me full details.",
      "temperature": 0,
      "max_tokens": 2048,
      "response": { "type": "text" }
    },
    {
      "id": "interpretation",
      "user_prompt": "Now explains what the user is doing interpreting and base on what you extracted from OCR previously. Include web UI explanation.\\n\\nOCR:\\n{ocr}",
      "response": { "type": "text" }
    }
  ],
  "output": {
    "mode": "all",
    "steps": ["ocr", "interpretation"],
    "label_format": "{value}",
    "separator": "\\n\\n"
  }
}
```

## Running (Single Runner)

Run everything once, and enable/disable modules via `.env`:

```bash
uv run exocort
```

Runner behavior:
- Collector always starts.
- Audio capture starts only if `AUDIO_CAPTURE_ENABLED=1`.
- Screen capture starts only if `SCREEN_CAPTURE_ENABLED=1`.
- Processor runs once only if `PROCESSOR_ENABLED=1` (use `PROCESSOR_ARGS` to pass CLI flags).

Example:

```bash
AUDIO_CAPTURE_ENABLED=1 SCREEN_CAPTURE_ENABLED=1 uv run exocort
```

## Running (Per-Module)

You can still run each module directly if needed:

```bash
uv run exocort-collector
AUDIO_CAPTURE_ENABLED=1 uv run exocort-audio
SCREEN_CAPTURE_ENABLED=1 uv run exocort-screen
uv run exocort-processor --day 2026-03-10 --dry-run
```

## Extension Setup (Chrome)

```text
chrome://extensions → Developer mode → Load unpacked → select extension/
```

The extension sends `browser.page_view` and `browser.page_text` events to the local collector.

## Collector API

- `GET /healthz` → `{ ok: true }`
- `POST /events` → accepts a single event or `{ events: [...] }`
- `POST /audio` → multipart upload for audio segments
- `POST /frame` → multipart upload for screen frames

## Data Layout

- `data/events/YYYY-MM-DD.jsonl` One event per line.
- `data/content/YYYY-MM-DD/*.md` Extracted page text.
- `data/audio/YYYY-MM-DD/*` Raw audio segments.
- `data/frame/YYYY-MM-DD/*` Raw screen frames.
- `data/derived/YYYY-MM-DD/*.md` Derived STT/OCR text.
- `vault/` Generated notes and state DB.

## Testing

Install test dependencies:

```bash
uv sync --extra test
```

Run fast tests:

```bash
uv run pytest -m "unit or integration"
```

Run service tests:

```bash
uv run pytest -m "service"
```

Real checks are separate from the normal pytest suite:

```bash
checks/real/run_llm.sh --config config/llm.json --input /path/to/input.txt
checks/real/run_ocr.sh --config config/ocr.json --image /path/to/image.png
checks/real/run_stt.sh --config config/stt.json --audio /path/to/audio.wav
```

Reusable test-only configs live under:

- `tests/configs/llm/`
- `tests/configs/ocr/`
- `tests/configs/stt/`

Real checks can also read behavior from env config paths such as:

```bash
export LLM_CONFIG_PATH=tests/configs/llm/openai.json
export OCR_CONFIG_PATH=tests/configs/ocr/openai.json
export STT_CONFIG_PATH=checks/real/configs/stt/faster-whisper.json
```

Normal test-suite helper scripts are available under `scripts/testing/`:

```bash
scripts/testing/run_unit.sh
scripts/testing/run_integration.sh
scripts/testing/run_service.sh
```

Standalone real-check scripts live under `checks/real/`.
See `checks/real/README.md` for usage and examples.
Extra manual-check configs also live under `checks/real/configs/`.

Real-check outputs are written to `tmp/real-checks/`.

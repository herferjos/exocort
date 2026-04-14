# Exocort

Exocort is a local capture pipeline that watches folders, processes audio and images, and can also build notes with tool calls. The project now uses its own HTTP-based `bridge` layer instead of `litellm`.

## Quick Start

1. Install dependencies from the `exocort` directory:
   ```bash
   uv sync
   ```
2. Edit `config.yaml`, `example.yaml`, `local.yaml`, `openai.yaml`, `gemini.yaml`, `mistral.yaml`, or `anthropic.yaml`.
3. Run the CLI:
   ```bash
   uv run exocort
   ```

If your config lives elsewhere:
```bash
uv run exocort --config /path/to/config.yaml
```

## What `bridge` Does

`exocort.bridge` is the internal adapter that turns a simple config into the correct HTTP request for each provider.

It supports three modes:

- `asr`: audio to text
- `ocr`: image or document to text
- `response`: text to text, with optional tools

Each mode can use either a dedicated endpoint or a multimodal LLM path, depending on the provider:

- `format: asr`: dedicated transcription endpoint
- `format: ocr`: dedicated OCR endpoint
- `format: llm`: multimodal response endpoint

## How To Think About The Config

The important fields are:

- `provider`: `openai`, `gemini`, `anthropic`, or `mistral`
- `mode`: the job to do, usually implied by the section where it appears: `asr`, `ocr`, or `response`
- `format`: provider-specific path selector for `asr` and `ocr`
- `model`: the model name, without provider prefix
- `api_base`: base URL for the provider API
- `api_key_env`: name of the environment variable that stores the API key
- `timeout_s` and `retries`: HTTP behavior for the bridge
- `language`: optional language hint for `processor.asr`, `processor.ocr`, and `processor.notes`
- `prompt`: optional request prompt for `processor.asr`, `processor.ocr`, and `processor.notes`

If `provider` is omitted, the bridge tries to infer it from `model` or `api_base`. Using an explicit provider is clearer.

## Provider Guide

### OpenAI

- `api_base`: `https://api.openai.com/v1`
- `response`: use the Responses or chat-style flow for text and vision
- `ocr`: use `format: llm` with multimodal image input
- `asr`: use `format: asr` and the transcription endpoint

Example:
```yaml
processor:
  ocr:
    provider: openai
    model: gpt-4.1
    api_base: https://api.openai.com/v1
    format: llm
  asr:
    provider: openai
    model: gpt-4o-transcribe
    api_base: https://api.openai.com/v1
    format: asr
```

### Gemini

- `api_base`: `https://generativelanguage.googleapis.com/v1beta`
- `response`: use `generateContent`
- `ocr`: use `format: llm` with multimodal image or file input
- `asr`: use `format: llm`

Example:
```yaml
processor:
  ocr:
    provider: gemini
    model: gemini-3-flash-preview
    api_base: https://generativelanguage.googleapis.com/v1beta
    format: llm
  asr:
    provider: gemini
    model: gemini-3-flash-preview
    api_base: https://generativelanguage.googleapis.com/v1beta
    format: llm
```

Example preset: [`gemini.yaml`](/Users/herferjos/Projects/exocort/exocort/gemini.yaml)

### Anthropic

- `api_base`: `https://api.anthropic.com/v1`
- `response`: use the Messages API
- `ocr`: use `format: llm` with image input through Messages
- `asr`: unsupported in this bridge

Example:
```yaml
processor:
  ocr:
    provider: anthropic
    model: claude-sonnet-4-5
    api_base: https://api.anthropic.com/v1
    format: llm
```

Example preset: [`anthropic.yaml`](/Users/herferjos/Projects/exocort/exocort/anthropic.yaml)

### Mistral

- `api_base`: `https://api.mistral.ai/v1`
- `response`: use chat completions / multimodal chat
- `ocr`: use either `format: ocr` with the dedicated OCR endpoint or `format: llm` with multimodal chat
- `asr`: use either `format: asr` with transcription endpoints or `format: llm` with Voxtral-style multimodal input

Example:
```yaml
processor:
  ocr:
    provider: mistral
    model: mistral-ocr-latest
    api_base: https://api.mistral.ai/v1
    format: ocr
  asr:
    provider: mistral
    model: voxtral-mini-latest
    api_base: https://api.mistral.ai/v1
    format: asr
```

Example preset: [`mistral.yaml`](/Users/herferjos/Projects/exocort/exocort/mistral.yaml)

## Recommended Defaults

- Use `provider` explicitly.
- Use bare model names, not `provider/model`.
- Use `format: asr` for dedicated transcription endpoints.
- Use `format: ocr` for dedicated OCR endpoints.
- Use `format: llm` only when the provider really supports multimodal input for that mode.
- For OCR, prefer the dedicated OCR endpoint when the provider has one, and only use `format: llm` when you intentionally want the multimodal path.

## YAML Sections

- `capturer.audio`: audio capture settings and retention
- `capturer.screen`: screenshot capture settings and retention
- `processor.ocr`: OCR bridge config
- `processor.asr`: ASR bridge config
- `processor.content_filter`: filters for OCR/ASR text before writing the processed JSON
- `processor.notes`: notes agent config, including tools and model settings

## Retention

Each `expired_in` value is in seconds. Use `False` to keep files forever.

- `0`: delete immediately after successful processing
- `60`: keep for one minute after successful processing
- `False`: never auto-delete

## Output

The processor writes normalized JSON files under the configured processed folder and preserves the input directory structure.

For ASR and OCR, the important field is `text`. For notes, the bridge returns assistant text plus any tool calls, which the notes agent then executes against the vault.

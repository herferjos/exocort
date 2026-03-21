# Unified Config

## Decision

Exocort should replace `.env` plus fragmented `config/*.json` files with one typed user configuration file:

```text
config/exocort.yaml
```

Important runtime rule:

- each execution of Exocort uses one and only one YAML file
- that file is selected explicitly at launch time
- the application should not merge several user config YAML files implicitly
- if several YAML files exist in `config/`, they are alternative presets or versions, not cumulative layers

Examples:

- `config/exocort.local.yaml`
- `config/exocort.cloud.yaml`
- `config/exocort.mixed.yaml`

Only one of those is active in a given run.

This file becomes the single source of truth for:

- runner behavior
- capture configuration
- collector configuration
- OCR and ASR providers
- processor storage and scheduler settings
- processor stage definitions
- LLM provider registry
- prompt locations
- schema locations
- secrets references

## Why YAML

This is an architectural recommendation, not a hard platform limitation.

YAML is the recommended authoring format because:

- the future config is deeply nested
- human operators will edit it directly
- arrays and nested objects are more readable than equivalent JSON
- processor stage definitions and provider registries are easier to maintain in YAML

This is also practical from an implementation standpoint:

- Pydantic Settings officially supports `YamlConfigSettingsSource`, `JsonConfigSettingsSource`, and `TomlConfigSettingsSource`
- Pydantic Settings also supports custom source priority through `settings_customise_sources`
- Pydantic Settings supports secrets directories as a first-class source

Official references:

- Pydantic Settings overview: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Pydantic other config sources including YAML, JSON, and TOML: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Python `tomllib` in the standard library: https://docs.python.org/3/library/tomllib.html

Inference from those sources:

YAML is the best default authoring format for Exocort, while typed validation should be handled by Pydantic models and the app may still export JSON Schema for tooling.

## What Must Be Removed

The redesign should remove these as primary user configuration mechanisms:

- `.env`
- `.env.example`
- env-backed getters in [exocort/settings.py](/Users/joselu/Proyectos/exocort/exocort/settings.py)
- split user config files like [config/config.openai.json](/Users/joselu/Proyectos/exocort/config/config.openai.json) and [config/config.local.json](/Users/joselu/Proyectos/exocort/config/config.local.json)
- direct `os.environ` reads in Exocort runtime code

Environment variables may remain only as optional emergency overrides or for secrets integration if explicitly designed that way, but not as the default user-facing configuration path.

## Recommended File Layout

```text
config/
  exocort.yaml
  prompts/
    event_enrichment.md
    session_labeling.md
    process_consolidation.md
    note_generation.md
    knowledge_extraction.md
    user_model_consolidation.md
  schemas/
    normalized_event.schema.json
    atomic_event.schema.json
    session.schema.json
    process.schema.json
    note.schema.json
    knowledge_item.schema.json
  taxonomy/
    knowledge_types.yaml
    session_categories.yaml
    process_categories.yaml
  secrets/
    openai_api_key
    gemini_api_key
```

## Recommended Top-Level Structure

```yaml
config_version: 1

runtime:
  profile: default
  log_level: INFO
  timezone: Europe/Madrid

paths:
  project_root: .
  vault_root: ./vault
  graph_root: ./vault/graph
  tmp_root: ./tmp
  prompt_root: ./config/prompts
  schema_root: ./config/schemas
  taxonomy_root: ./config/taxonomy
  secrets_dir: ./config/secrets

runner:
  enabled_components:
    - collector
    - processor
    - audio_capture
    - screen_capture
  startup_order:
    - collector
    - processor
    - audio_capture
    - screen_capture

audio_capture:
  enabled: true
  spool_dir: ./tmp/audio
  request_timeout_s: 30
  max_upload_per_cycle: 5
  sample_rate: 8000
  target_sample_rate: 8000
  frame_ms: 20
  vad_mode: 2
  start_rms: 150
  continue_rms: 100
  start_trigger_ms: 120
  start_window_ms: 400
  end_silence_ms: 700
  pre_roll_ms: 300
  min_segment_ms: 500
  max_segment_ms: 30000
  input_device: null
  latency: null
  gain_db: 0.0

screen_capture:
  enabled: true
  fps: 0.5
  tmp_dir: ./tmp/screen
  request_timeout_s: 30
  prompt_permission: true
  dedup_window_s: 300
  dedup_threshold: 5

collector:
  enabled: true
  host: 127.0.0.1
  port: 8000
  tmp_dir: ./tmp/collector
  vault_dir: ./vault
  routes:
    audio:
      provider: openai_transcription
    screen:
      provider: openai_vision

providers:
  openai_transcription:
    kind: http
    api_style: openai
    base_url: https://api.openai.com/v1
    auth:
      secret_ref: openai_api_key
    request:
      endpoint: /audio/transcriptions
      method: POST
      timeout_s: 60
      format: openai
      body:
        model: whisper-1
        language: en
        prompt: Transcribe the attached audio.
  openai_vision:
    kind: http
    api_style: openai
    base_url: https://api.openai.com/v1
    auth:
      secret_ref: openai_api_key
    request:
      endpoint: /chat/completions
      method: POST
      timeout_s: 60
      format: openai
      body:
        model: gpt-4o-mini
  local_reasoner:
    kind: http
    api_style: openai_compatible
    base_url: http://127.0.0.1:9100/v1
    auth: {}

processor:
  enabled: true
  storage:
    root: ./vault/graph
    state_dir: ./vault/graph/state
    runs_dir: ./vault/graph/runs
    dead_letter_dir: ./vault/graph/dead_letter
  scheduler:
    poll_seconds: 2
    max_global_workers: 8
    lease_timeout_seconds: 120
  stages:
    normalize_events:
      enabled: true
      mode: deterministic
      concurrency: 4
      trigger:
        min_inputs: 1
        poll_seconds: 2
    event_enrichment:
      enabled: true
      mode: structured
      provider: local_reasoner
      model: qwen2.5-coder
      prompt_file: event_enrichment.md
      schema_file: atomic_event.schema.json
      concurrency: 4
      trigger:
        min_inputs: 1
        max_batch_size: 16
        poll_seconds: 2
    process_consolidation:
      enabled: true
      mode: agentic
      provider: openai_reasoning
      model: gpt-5.4
      prompt_file: process_consolidation.md
      schema_file: process.schema.json
      tools:
        - graph_lookup
        - evidence_fetch
      skills:
        - taxonomy-normalizer
      concurrency: 2
      max_agent_steps: 10
      trigger:
        min_inputs: 3
        stability_window_seconds: 120
        poll_seconds: 10
```

## Typed Config Model

Implementation should use typed models rather than ad hoc dictionary access.

Recommended approach:

- `AppConfig`
- `RuntimeConfig`
- `PathsConfig`
- `RunnerConfig`
- `AudioCaptureConfig`
- `ScreenCaptureConfig`
- `CollectorConfig`
- `ProviderConfig`
- `ProcessorConfig`
- `ProcessorStageConfig`
- `TriggerConfig`

Recommended library choice:

- `pydantic`
- `pydantic-settings`
- YAML parser only if needed by the chosen Pydantic source setup

## Secret Handling

Removing `.env` does not mean secrets should be hardcoded everywhere.

Recommended secret strategy:

1. allow inline values only for local throwaway prototypes
2. prefer `secret_ref` names resolved from a secrets directory
3. optionally allow future OS keychain integration

Recommended config shape:

```yaml
providers:
  openai_reasoning:
    auth:
      secret_ref: openai_api_key
```

And resolve from:

```text
config/secrets/openai_api_key
```

Why:

- Pydantic Settings officially supports secrets directories
- this removes `.env` from the critical path
- it keeps config readable without putting credentials everywhere

## Source Priority

Recommended priority order:

1. explicit CLI `--config` path
2. secrets directory referenced by that YAML
3. optional explicit runtime overrides used only in tests

Do not keep dotenv in the default chain.
Do not search for sibling YAML configs and do not auto-merge profiles.

## CLI Behavior

Every entrypoint should accept:

```bash
exocort --config ./config/exocort.yaml
exocort-collector --config ./config/exocort.yaml
exocort-audio --config ./config/exocort.yaml
exocort-screen --config ./config/exocort.yaml
exocort-processor --config ./config/exocort.yaml
```

The runner should pass the resolved config object to child components instead of relying on global module state.

This flag is not optional in the target design. The active YAML path is part of the invocation contract.

If multiple config variants exist, the operator chooses one explicitly:

```bash
exocort --config ./config/exocort.local.yaml
exocort --config ./config/exocort.cloud.yaml
exocort --config ./config/exocort.mixed.yaml
```

The system loads exactly that file and no other user config file.

## Migration Plan

### Phase 1

- add typed config models
- add YAML loading
- add schema validation
- add CLI `--config`

### Phase 2

- stop using `.env` in main Exocort runtime
- migrate runner, capture, collector, and processor to injected config
- keep temporary compatibility shims only inside migration code if needed

### Phase 3

- delete `.env.example`
- delete env-backed getters from `exocort/settings.py`
- delete split config ownership across `config/*.json`
- update tests and docs

## Acceptance Criteria

The unified config migration is complete when:

- a fresh install can run using only `config/exocort.yaml` plus secrets files
- each run selects exactly one YAML file through `--config`
- no main Exocort runtime module requires `.env`
- OCR, ASR, collector, and processor provider routing all come from the same typed config object
- prompts, schemas, taxonomies, and stage settings are all discoverable from one config tree

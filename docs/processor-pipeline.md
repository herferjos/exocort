# Processor Pipeline Configuration

This document describes the processor pipeline model defined in `config/exocort.toml`.

The processor is configured as a runtime pipeline composed of:

- global processor settings
- named prompt entries
- named collections
- ordered stages

Each stage reads artifacts from one collection, applies a transformation strategy, writes one or more outputs, and persists its own execution state.

## Runtime Model

At runtime, the processor performs the following loop:

1. Read pending inputs from a configured collection.
2. Apply the stage transformation.
3. Persist output artifacts.
4. Optionally archive processed inputs.
5. Advance the stage cursor in `state_dir`.

The engine supports two execution modes:

- `per_stage_worker`: one worker process per configured stage
- `single_loop`: one process iterates through all configured stages in order

## Top-Level Processor Settings

The `[processor]` section defines the runtime environment:

- `vault_dir`: root directory for raw capturer records
- `out_dir`: root directory for derived processor artifacts
- `state_dir`: root directory for stage cursors and state
- `poll_interval_seconds`: polling interval used in watch mode
- `execution_mode`: `per_stage_worker` or `single_loop`
- `max_concurrent_tasks`: shared concurrency limit for LLM-backed stages

## Prompt Registry

`[processor.prompts]` defines named prompts that stages may reference through `prompt_key`.

Example:

```toml
[processor.prompts]
normalize_event = "Normalize these raw records into structured events."
build_summary = "Group these events into concise summaries."
```

## Collections

Collections define logical storage locations used by the pipeline.

Example:

```toml
[processor.collections.raw]
base_dir = "vault"
path = "."

[processor.collections.events]
path = "events"

[processor.collections.summaries]
path = "summaries"
```

Collection fields:

- `path`: relative path inside the selected base directory
- `base_dir`: optional; `vault` uses `processor.vault_dir`, otherwise the runtime uses `processor.out_dir`
- `format`: optional metadata for collection usage, such as markdown-oriented projections

Recommended convention:

- use `base_dir = "vault"` for raw capturer input
- use the default output base for derived artifacts

## Stages

Each stage defines one transformation unit in the pipeline.

Typical fields:

- `name`: unique stage identifier
- `enabled`: enables or disables the stage
- `type`: runtime stage type
- `input_collection`: source collection name
- `outputs`: output definitions
- `state_key`: state file key
- `prompt_key`: prompt registry entry used by the stage
- `batch_size`: maximum number of items processed in one run
- `flush_threshold`: minimum pending items required before the stage runs
- `upstream_collections`: collections used to decide whether upstream data is still arriving
- `archive_collection`: destination collection for processed inputs
- `transform_adapter`: adapter implementation used by the runtime
- `transform_options`: additional adapter-specific configuration
- `concurrency`: optional per-stage concurrency hint

Example:

```toml
[[processor.stages]]
name = "normalize_raw"
enabled = true
type = "llm_map"
input_collection = "raw"
state_key = "normalize_raw"
prompt_key = "normalize_event"
batch_size = 5
flush_threshold = 5
archive_collection = "raw_archive"
transform_adapter = "llm_map"
outputs = [{ name = "items", collection = "events" }]
```

## Output Definitions

Each stage may emit one or more named outputs. These outputs are mapped to collections.

Recommended inline form:

```toml
outputs = [{ name = "items", collection = "events" }]
```

For multiple outputs:

```toml
outputs = [
  { name = "timeline_events", collection = "timeline_events", projection = "jsonl_day" },
  { name = "super_events", collection = "super_events" },
]
```

Output fields:

- `name`: logical output name returned by the adapter
- `collection`: destination collection
- `projection`: optional projection mode

Current projection modes:

- `none`
- `jsonl_day`
- `markdown_note`

## Artifact Model

JSON artifacts produced by the processor use a shared envelope plus a free-form payload.

Envelope fields:

- `kind`
- `stage`
- `item_id`
- `timestamp`
- `date`
- `source_ids`
- `source_paths`
- `trace`
- `payload`

`payload` contains the stage-specific business structure. This allows different pipelines to emit different domain models without changing the runtime contract.

Example:

```json
{
  "kind": "summary",
  "stage": "build_summaries",
  "item_id": "summary_2026_03_22_morning",
  "timestamp": "2026-03-22T09:30:00+00:00",
  "date": "2026-03-22",
  "source_ids": ["event_a", "event_b"],
  "source_paths": ["..."],
  "trace": {
    "adapter": "llm_reduce"
  },
  "payload": {
    "title": "Morning work block",
    "description": "Focused work on parser cleanup"
  }
}
```

## Stage Types

The runtime currently supports these stage types and adapters:

- `llm_map`
- `llm_reduce`
- `deterministic_map`
- `deterministic_reduce`
- `noop`

Compatibility adapters for the default pipeline are also available:

- `legacy_l1`
- `legacy_l2`
- `legacy_l3`

### `llm_map`

Use when the stage transforms individual items into individual outputs.

Typical use cases:

- raw event normalization
- enrichment
- classification

### `llm_reduce`

Use when the stage consumes a batch and emits grouped or aggregated outputs.

Typical use cases:

- clustering
- summarization
- timeline compaction

### `deterministic_map`

Use when the transformation does not require an LLM and can be expressed as a direct artifact mapping.

### `deterministic_reduce`

Use when multiple inputs must be combined into one deterministic output artifact.

### `noop`

Use when no transformation is required and the stage is only used for orchestration or archive flow.

## Transform Options

Generic adapters use `transform_options` to define how inputs and outputs should be interpreted.

Common fields:

- `input_mode`: `raw`, `payload`, or `envelope`
- `input_key`: key used in the request payload
- `result_key`: key expected in the adapter response
- `kind`: envelope kind for emitted artifacts
- `id_field`: payload field used as `item_id`
- `date_field`: payload field used as `date`
- `timestamp_field`: payload field used as `timestamp`
- `source_id_field`: payload field used to populate `source_ids`

Example:

```toml
[[processor.stages]]
name = "normalize_raw"
type = "llm_map"
input_collection = "raw"
transform_adapter = "llm_map"
outputs = [{ name = "items", collection = "events" }]

[processor.stages.transform_options]
input_mode = "raw"
input_key = "records"
result_key = "items"
kind = "event"
id_field = "event_id"
date_field = "date"
timestamp_field = "timestamp"
source_id_field = "source_raw_event_id"
```

## Design Guidelines

When designing a custom pipeline:

1. Define stable collection boundaries first.
2. Decide whether each transformation is item-based or batch-based.
3. Use `llm_map` for one-to-one transformations.
4. Use `llm_reduce` for grouped or aggregate outputs.
5. Keep `kind` values semantic and stable.
6. Keep business-specific structure inside `payload`.
7. Use archive collections when replay protection matters.
8. Introduce a new adapter in code if the configuration begins to encode too much custom logic.

## Default Pipeline

The default configuration shipped with the project expresses the current processor as a configurable pipeline:

- `l1`: raw vault records -> normalized events
- `l2`: normalized events -> timeline events and super events
- `l3`: super events -> note artifacts and markdown note projections

This default flow is now defined through configuration rather than hard-coded orchestration in the engine.

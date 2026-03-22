# Processor Pipeline Configuration

This document describes the processor pipeline model defined in `config.toml`.

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
4. Advance the stage cursor and save stage state in the stage folder under `.vault/processed/<stage>/state.json`.

The engine supports two execution modes:

- `per_stage_worker`: one worker process per configured stage
- `single_loop`: one process iterates through all configured stages in order

## Top-Level Processor Settings

The `[processor]` section defines the runtime environment:

- `vault_dir`: root directory for raw capturer records, typically `.vault/raw`
- `out_dir`: root directory for derived processor artifacts, typically `.vault/processed`
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
- keep stage output collections flat, one folder per stage, with no date subfolders

## Stages

Each stage defines one transformation unit in the pipeline.

Typical fields:

- `name`: unique stage identifier
- `enabled`: enables or disables the stage
- `type`: runtime stage type
- `input_collection`: source collection name
- `outputs`: output definitions
- `prompt_key`: prompt registry entry used by the stage
- `batch_size`: maximum number of items processed in one run
- `flush_threshold`: minimum pending items required before the stage runs
- `upstream_collections`: collections used to decide whether upstream data is still arriving
- `transform_adapter`: adapter implementation used by the runtime
- `transform_options`: additional adapter-specific configuration
- `concurrency`: optional per-stage concurrency hint

The runtime stores stage state under `out_dir/<stage name>/state.json`, so the stage name is the stable folder name for that stage.

Example:

```toml
[[processor.stages]]
name = "normalize_raw"
enabled = true
type = "llm_map"
input_collection = "raw"
prompt_key = "normalize_event"
batch_size = 5
flush_threshold = 5
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

JSON artifacts produced by the processor are flat objects.

Required fields:

- `id`
- `timestamp`
- `source_ids`

The rest of the JSON object is the stage-specific output from the LLM or adapter.

Example:

```json
{
  "id": "summary_2026_03_22_morning",
  "timestamp": "2026-03-22T09:30:00+00:00",
  "source_ids": ["event_a", "event_b"],
  "title": "Morning work block",
  "description": "Focused work on parser cleanup"
}
```

## Stage Types

The runtime currently supports these stage types and adapters:

- `llm_map`
- `llm_reduce`
- `noop`

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

### `noop`

Use when no transformation is required and the stage is only used for orchestration flow.

## Transform Options

Generic adapters use `transform_options` to define how inputs and outputs should be interpreted.

Common fields:

- `input_mode`: `raw`, `payload`, or `envelope`
- `input_projection`: optional projection applied before the adapter call, for example `record_text` or `field`
- `input_field`: dotted field path used when `input_projection = "field"`
- `input_projection = { ... }`: field map projection for building a smaller object per input item
- `input_key`: key used in the request payload
- `output_map_source`: source mode used by `output_map`; defaults to `raw`
- `output_map`: optional mapping table used to enrich persisted rows from the original input
- `result_key`: key expected in the adapter response
- `id_field`: payload field used as `id`
- `timestamp_field`: payload field used as `timestamp`

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
input_projection = "record_text"
input_key = "records"
output_map_source = "raw"

[processor.stages.transform_options.output_map]
id = "input:id"
timestamp = "input:timestamp"
source_ids = "input:id"
```

`output_map` also supports structured operations for generic post-processing, including:

- `slug`: derive ids from row or input fields
- `match_items`: join a reduce output row with matching batch items by id
- `min_path_from_matches` and `max_path_from_matches`: derive aggregate values such as batch start/end timestamps
- `date_from_path`: compute a `YYYY-MM-DD` date from any timestamp field

## Design Guidelines

When designing a custom pipeline:

1. Define stable collection boundaries first.
2. Decide whether each transformation is item-based or batch-based.
3. Use `llm_map` for one-to-one transformations.
4. Use `llm_reduce` for grouped or aggregate outputs.
5. Keep persisted artifacts flat and minimal.
6. Always include `id`, `timestamp`, and `source_ids` in persisted artifacts.
7. Use archive collections only when replay protection matters.
8. Introduce a new adapter in code if the configuration begins to encode too much custom logic.

## Default Pipeline

The default configuration shipped with the project expresses the current processor as a configurable pipeline:

- `l1`: raw vault records -> normalized events with `id`, `timestamp`, `source_ids`, `title`, `description`, and `content`
- `l2`: normalized events -> grouped super-events with `id`, `timestamp`, `source_ids`, `title`, and `description`
- `l3`: super events -> notes with `id`, `timestamp`, `source_ids`, `title`, `description`, `content`, `category`, and `subject`

This default flow is now defined through configuration rather than hard-coded orchestration in the engine.

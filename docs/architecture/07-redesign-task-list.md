# Redesign Task List

## Goal

Replace the current legacy processor pipeline with a new graph-native processor that:

- reads raw OCR and ASR vault events by timestamp
- writes all derived layers into a structured database under the vault
- runs levels independently when their trigger conditions are satisfied
- allows different LLM providers per task
- supports both structured single-shot stages and agentic stages
- produces a versioned, traceable user model

This is a redesign, not a compatibility layer.

## What Exists Today

The current processor already has useful building blocks, but they must be replaced or heavily refactored:

- `exocort/processor/__main__.py` launches 4 long-lived workers in parallel
- `exocort/processor/engine.py` implements a fixed `l1 -> l2 -> l3 -> l4` pipeline
- `exocort/processor/config.py` supports only one global `llm` config plus prompt strings
- current workers archive inputs after use instead of maintaining a durable graph
- current outputs are layer folders, not a relational or graph-structured store

The current runtime is also fragmented across environment variables and multiple config files:

- [exocort/settings.py](/Users/joselu/Proyectos/exocort/exocort/settings.py) loads `.env` and exposes dozens of component getters
- [config/config.openai.json](/Users/joselu/Proyectos/exocort/config/config.openai.json) and sibling files define OCR/ASR/provider routing separately
- several modules still read `os.environ` directly instead of going through a typed config model
- tests currently patch environment variables heavily, which will need a migration plan

## Redesign Principles

- no legacy L1/L2/L3 compatibility mode in the new processor core
- raw events remain immutable
- all derived entities have stable IDs and evidence links
- each level owns its own trigger, scheduler state, and retry policy
- levels can run concurrently as long as input readiness is satisfied
- summaries are outputs for display, never pipeline source-of-truth
- note generation does not write directly into the user model

## Target Storage Layout

The structured database should live under the vault root so the full capture-to-model lineage is colocated.

Recommended layout:

```text
vault/
  YYYY-MM-DD/                         # existing raw capture records
  graph/
    raw_events/
    normalized_events/
    atomic_events/
    sessions/
    processes/
    semantic_clusters/
    notes/
    knowledge_items/
    user_model/
    state/
    indexes/
    runs/
```

## Execution Model

The redesign should use a DAG of independent processors rather than a single sequential conveyor belt.

Example:

```text
raw_events -----------------> normalized_events ---------> atomic_events
                                  |                           |
                                  |                           v
                                  |----------------------> sessions
                                                              |
                                                              v
                                                         processes
                                                              |
                                                              v
                                                       semantic_clusters
                                                              |
                                                              v
                                                            notes
                                                              |
                                                              v
                                                       knowledge_items
                                                              |
                                                              v
                                                          user_model
```

Each node type should have:

- a readiness query
- a trigger policy
- an executor
- an output validator
- persistence logic
- retry and dead-letter behavior

## Config Design Requirements

The new processor config should support:

- one unified user config for the whole system
- per-stage provider selection
- per-stage model selection
- per-stage execution mode: `structured` or `agentic`
- per-stage concurrency and batch policies
- per-stage prompts, schemas, and tools
- provider registry for local and cloud backends
- capture, collector, processor, runner, and storage settings in the same document
- secret references without relying on `.env`

## Unified Config Decision

The redesign should replace `.env` plus fragmented `config/*.json` files with a single typed user config file, preferably YAML.

Important clarification:

- each Exocort run uses exactly one YAML file
- the YAML path is passed explicitly when launching `exocort`
- if multiple YAML files exist, they are alternative full configurations, not merged layers
- examples: `config/exocort.local.yaml`, `config/exocort.cloud.yaml`, `config/exocort.mixed.yaml`
- only one of them is active at runtime

Rationale:

- YAML is easier to author for large nested configs than JSON
- the new architecture needs deeply nested structures for providers, stages, triggers, tools, and schemas
- Pydantic Settings officially supports YAML, JSON, TOML, `pyproject.toml`, custom source ordering, and secrets directories
- the current number of `AUDIO_CAPTURE_*`, `SCREEN_CAPTURE_*`, `COLLECTOR_*`, and `PROCESSOR_*` environment variables has already outgrown the ergonomics of `.env`

Relevant references:

- Pydantic Settings says it supports `YamlConfigSettingsSource`, `JsonConfigSettingsSource`, and `TomlConfigSettingsSource`, and allows overriding source priority with `settings_customise_sources`
- Pydantic Settings also supports secrets directories, which is a better primitive than `.env` for sensitive values
- Python 3.11+ includes `tomllib` in the standard library, which keeps TOML viable, but YAML is still the recommended authoring format here because the config will be nested and operator-edited often

See [09-unified-config.md](/Users/joselu/Proyectos/exocort/docs/architecture/09-unified-config.md) for the full design.

Recommended shape:

```json
{
  "processor": {
    "storage": {
      "root": "./vault/graph"
    },
    "providers": {
      "local_fast": {
        "type": "openai_compatible",
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key_env": "LOCAL_LLM_API_KEY",
        "default_model": "qwen2.5-coder"
      },
      "cloud_reasoning": {
        "type": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-5.4"
      }
    },
    "stages": {
      "event_enrichment": {
        "enabled": true,
        "level": "atomic_events",
        "mode": "structured",
        "provider": "local_fast",
        "model": "qwen2.5-coder",
        "prompt": "prompts/event_enrichment.md",
        "output_schema": "schemas/atomic_event.schema.json",
        "trigger": {
          "min_inputs": 1,
          "max_batch_size": 16,
          "poll_seconds": 2
        },
        "concurrency": 4
      },
      "process_consolidation": {
        "enabled": true,
        "level": "processes",
        "mode": "structured",
        "provider": "cloud_reasoning",
        "model": "gpt-5.4",
        "prompt": "prompts/process_consolidation.md",
        "output_schema": "schemas/process.schema.json",
        "trigger": {
          "min_inputs": 3,
          "stability_window_seconds": 120,
          "poll_seconds": 10
        },
        "concurrency": 2
      },
      "knowledge_extraction": {
        "enabled": true,
        "level": "knowledge_items",
        "mode": "agentic",
        "provider": "cloud_reasoning",
        "model": "gpt-5.4",
        "prompt": "prompts/knowledge_extraction.md",
        "skills": ["taxonomy-normalizer", "dedup-review"],
        "tools": ["graph_lookup", "embedding_search", "evidence_fetch"],
        "output_schema": "schemas/knowledge_item.schema.json",
        "trigger": {
          "min_inputs": 1,
          "poll_seconds": 15
        },
        "concurrency": 1,
        "max_agent_steps": 12
      }
    }
  }
}
```

## Checklist

### 1. Replace the processor entrypoint

- [ ] Replace the current fixed worker bootstrap in [exocort/processor/__main__.py](/Users/joselu/Proyectos/exocort/exocort/processor/__main__.py) with a scheduler that loads stage definitions dynamically from `processor.stages`.
- [ ] Remove the hardcoded `_l1_worker`, `_l2_worker`, `_l3_worker`, `_l4_worker` execution contract from the new runtime.
- [ ] Introduce a stage registry that maps a stage key to executor code, schemas, and readiness logic.
- [ ] Add support for independent worker pools per stage instead of one shared global semaphore model.

### 2. Replace the old config model

- [ ] Remove `.env` as the primary configuration source for Exocort.
- [ ] Replace [exocort/settings.py](/Users/joselu/Proyectos/exocort/exocort/settings.py) with a typed config loader module that reads a unified YAML file.
- [ ] Stop reading config directly with `os.environ` in app code such as collector, vault, runner, and processor modules.
- [ ] Remove the single-LLM assumption from [exocort/processor/config.py](/Users/joselu/Proyectos/exocort/exocort/processor/config.py).
- [ ] Replace `config/config.openai.json`, `config/config.local.json`, and sibling provider files with one unified config file.
- [ ] Add a `providers` registry with support for local and cloud backends.
- [ ] Add per-stage `provider`, `model`, `mode`, `trigger`, `concurrency`, `prompt`, and `output_schema`.
- [ ] Add global sections for `runner`, `audio_capture`, `screen_capture`, `collector`, `storage`, `processor`, `services`, and `secrets`.
- [ ] Add config validation for provider existence, missing env vars, unsupported stage modes, and schema paths.
- [ ] Add explicit versioning fields: `schema_version`, `taxonomy_version`, `prompt_version`, `consolidation_version`.

### 3. Build the graph storage layer under `vault/graph`

- [ ] Define canonical persisted schemas for `raw_events`, `normalized_events`, `atomic_events`, `sessions`, `processes`, `semantic_clusters`, `notes`, `knowledge_items`, and `user_model`.
- [ ] Implement a repository layer that writes entity files or records under `vault/graph/...`.
- [ ] Add relation indexes for `source_ids`, `evidence_ids`, `parent_ids`, and `child_ids`.
- [ ] Add run metadata storage under `vault/graph/runs/` for each stage execution.
- [ ] Add dead-letter storage for invalid outputs, parse failures, and validation failures.

### 4. Preserve raw events as immutable inputs

- [ ] Treat existing timestamped OCR/ASR JSON records in `vault/YYYY-MM-DD/` as immutable raw inputs.
- [ ] Add a raw-event catalog index so stages do not scan the entire vault every cycle.
- [ ] Store ingestion status separately from raw event content.
- [ ] Generate stable `raw_event_id` values independent from path names when needed.

### 5. Implement `normalized_events`

- [ ] Create a deterministic normalization stage that converts raw OCR/ASR records into a canonical event shape.
- [ ] Preserve source payload references and metadata from the collector output.
- [ ] Add fingerprints for deduplication.
- [ ] Make this stage non-LLM by default unless raw providers become heterogeneous enough to justify semantic cleanup.

### 6. Implement `atomic_events`

- [ ] Create the first semantic stage that enriches normalized events into atomic activity units.
- [ ] Support local cheaper models for this stage by default.
- [ ] Validate titles, event types, entities, and confidence values against schema.
- [ ] Persist all evidence links back to `normalized_event_id` and `raw_event_id`.

### 7. Implement deterministic `sessions`

- [ ] Design the sessionization algorithm before higher semantic layers.
- [ ] Define gap thresholds, continuity heuristics, and split rules.
- [ ] Support incremental session extension as new atomic events arrive.
- [ ] Add a session state machine that can reopen recent sessions or finalize stale ones.

### 8. Implement `processes`

- [ ] Build a readiness query that selects candidate sessions for consolidation once they are stable enough.
- [ ] Implement conservative merge behavior: uncertainty should keep processes separate.
- [ ] Persist `process_id`, `purpose`, `category`, `state`, `confidence`, and all evidence links.
- [ ] Use a stronger reasoning-capable provider for this stage if needed.

### 9. Implement `semantic_clusters`

- [ ] Add clustering across processes by topic, intent, and recurring entities.
- [ ] Support incremental cluster updates instead of full reclustering for every new process.
- [ ] Add semantic deduplication and merge histories.
- [ ] Store cluster-to-process relations explicitly.

### 10. Implement `notes`

- [ ] Generate standalone notes from processes or clusters, not from summaries.
- [ ] Define note types like `insight`, `observation`, `action`, and `reminder`.
- [ ] Keep notes fully traceable to cluster, process, session, and event evidence.
- [ ] Allow note regeneration when upstream graph state changes materially.

### 11. Implement `knowledge_items`

- [ ] Add a separate extraction stage between notes and user model.
- [ ] Normalize into typed items such as `skill`, `interest`, `preference`, `habit`, `goal`, `project`, and `constraint`.
- [ ] Add semantic merge rules for repeated items.
- [ ] Add evidence counts, recency, and strength fields.

### 12. Implement the versioned `user_model`

- [ ] Build a consolidation stage that consumes knowledge item deltas, not raw notes.
- [ ] Write versioned snapshots under `vault/graph/user_model/`.
- [ ] Add promotion, decay, contradiction, and deprecation rules.
- [ ] Keep each user-model fact traceable to source knowledge items and raw evidence.

### 13. Build the scheduler and triggers

- [ ] Give each stage its own readiness query.
- [ ] Support trigger conditions such as `min_inputs`, `stability_window`, `max_input_age`, `poll_seconds`, and `schedule`.
- [ ] Allow multiple stages to execute concurrently when they do not contend for the same entity set.
- [ ] Add optimistic locking or entity leases to prevent duplicate processing by concurrent workers.
- [ ] Add idempotency keys for stage runs.

### 14. Support `structured` and `agentic` stage modes

- [ ] Define a common executor interface with `prepare`, `run`, `validate`, and `commit`.
- [ ] Implement `structured` mode for one-shot JSON-in/JSON-out tasks.
- [ ] Implement `agentic` mode for multi-step tool-using tasks.
- [ ] Add per-stage limits such as `max_agent_steps`, `max_tool_calls`, `timeout_seconds`, and `approval_policy`.

### 15. Add tool and skill infrastructure for agentic stages

- [ ] Define internal tools such as `graph_lookup`, `evidence_fetch`, `embedding_search`, `taxonomy_map`, and `merge_preview`.
- [ ] Define skill bundles for reusable behaviors such as taxonomy normalization, note drafting, and knowledge deduplication.
- [ ] Restrict which stages may use networked or high-impact tools.
- [ ] Log all tool calls and agent traces under `vault/graph/runs/`.

### 16. Replace prompt handling

- [ ] Stop using environment-variable prompts as the primary mechanism.
- [ ] Load prompts from versioned files referenced in config.
- [ ] Add output schema files alongside prompts.
- [ ] Add prompt version metadata to every persisted derived entity.

### 17. Add validation and guardrails

- [ ] Validate every LLM output for JSON shape, allowed taxonomy, ID integrity, and confidence ranges.
- [ ] Add retry-once repair flows for malformed outputs.
- [ ] Send unrecoverable outputs to a dead-letter queue for later inspection.
- [ ] Prevent category explosion by enforcing taxonomy mapping before commit.

### 18. Add observability

- [ ] Persist per-run traces with input IDs, provider, model, prompt version, runtime, and tool usage.
- [ ] Add counters for throughput, retries, invalid outputs, stale backlog, and merge rates.
- [ ] Add a compact status view showing backlog by stage and newest successful run.

### 19. Add tests for the redesign

- [ ] Replace tests that assume the old `l1/l2/l3/l4` directory contract.
- [ ] Add unit tests for each stage executor.
- [ ] Add integration tests for DAG readiness and parallel execution.
- [ ] Add traceability tests from `user_model` back to `raw_event`.
- [ ] Add config tests for multi-provider stage routing.

### 20. Remove legacy assumptions

- [ ] Remove the current archive-based consumption model where upstream items disappear into `l0_processed_raw`, `l1_processed`, and `l2_processed`.
- [ ] Remove the single `llm` configuration key.
- [ ] Remove the `.env`-driven settings model from main Exocort.
- [ ] Remove duplicated config ownership split between `.env`, `settings.py`, and `config/*.json`.
- [ ] Remove the legacy assumption that L3 writes notes and user model together.
- [ ] Remove the legacy idea that the processor is fundamentally a four-level pipeline.

## Config Migration Checklist

### A. Introduce a unified config file

- [ ] Require exactly one active YAML config file per run, selected explicitly with `--config /path/to/exocort.yaml`.
- [ ] Allow additional YAML files only as alternative full presets such as `exocort.local.yaml`, `exocort.cloud.yaml`, or `exocort.mixed.yaml`.
- [ ] Do not merge multiple user YAML files at runtime.
- [ ] Add a typed config loader that resolves relative paths from the config file location.
- [ ] Add schema validation errors that point to exact invalid sections.

### B. Replace current environment-backed settings access

- [ ] Replace every getter in [exocort/settings.py](/Users/joselu/Proyectos/exocort/exocort/settings.py) with typed config accessors or injected config objects.
- [ ] Update [exocort/runner.py](/Users/joselu/Proyectos/exocort/exocort/runner.py) to use the new config object instead of `.env` flags.
- [ ] Update [exocort/collector/app.py](/Users/joselu/Proyectos/exocort/exocort/collector/app.py) host and port loading to use unified config.
- [ ] Update [exocort/collector/vault.py](/Users/joselu/Proyectos/exocort/exocort/collector/vault.py) temp and vault path loading to use unified config.
- [ ] Update capture components so they receive config objects instead of reading globals.
- [ ] Update processor startup so stage config comes from the unified file only.

### C. Migrate secrets and credentials

- [ ] Define how secrets are stored: inline for local prototypes, or file-secret references for safer setups.
- [ ] Add support for a `secrets/` directory or provider-specific `secret_ref` values.
- [ ] Remove prompt strings and API keys from `.env.example`.
- [ ] Document secret resolution priority clearly.

### D. Migrate documentation and tests

- [ ] Replace `.env` setup instructions in [README.md](/Users/joselu/Proyectos/exocort/README.md).
- [ ] Replace references in [docs/data-flow.md](/Users/joselu/Proyectos/exocort/docs/data-flow.md) that assume env-based settings.
- [ ] Rewrite tests that monkeypatch env vars to instead load temporary config fixtures.
- [ ] Add a golden example config fixture for local-only and cloud-enabled setups.

## Engineer Notes

Another engineer implementing this should read, in order:

1. [01-overview.md](/Users/joselu/Proyectos/exocort/docs/architecture/01-overview.md)
2. [02-pipeline.md](/Users/joselu/Proyectos/exocort/docs/architecture/02-pipeline.md)
3. [03-data-model.md](/Users/joselu/Proyectos/exocort/docs/architecture/03-data-model.md)
4. [07-redesign-task-list.md](/Users/joselu/Proyectos/exocort/docs/architecture/07-redesign-task-list.md)
5. [09-unified-config.md](/Users/joselu/Proyectos/exocort/docs/architecture/09-unified-config.md)
6. [10-implementation-playbook.md](/Users/joselu/Proyectos/exocort/docs/architecture/10-implementation-playbook.md)

That combination should be treated as the implementation contract for the redesign.

## Suggested Build Order

1. storage and IDs
2. config redesign
3. normalization
4. atomic events
5. sessionization
6. scheduler and stage triggers
7. processes
8. semantic clusters
9. notes
10. knowledge items
11. user model
12. agentic stages and tooling
13. observability and evals

## Definition Of Done

The redesign is done when:

- raw OCR/ASR records in the vault feed a graph-native processor without legacy layer assumptions
- all semantic layers live under `vault/graph`
- stages execute independently based on readiness
- tasks can choose local or cloud LLMs per stage
- agentic stages can use bounded tools and skills
- every user-model fact is traceable to evidence

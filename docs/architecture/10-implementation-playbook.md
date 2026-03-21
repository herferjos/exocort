# Implementation Playbook

## Purpose

This document is the engineering handoff for implementing the redesign without losing important details.

Use it together with:

- [07-redesign-task-list.md](/Users/joselu/Proyectos/exocort/docs/architecture/07-redesign-task-list.md)
- [09-unified-config.md](/Users/joselu/Proyectos/exocort/docs/architecture/09-unified-config.md)

## What The Engineer Must Understand First

The current codebase has two different types of technical debt that interact:

1. pipeline debt
2. configuration debt

Pipeline debt:

- the processor is conceptually a fixed four-step pipeline
- it archives consumed files instead of building a graph
- user-model generation happens too early and too directly

Configuration debt:

- settings are spread across `.env`, `settings.py`, `config/*.json`, and direct `os.environ` reads
- provider selection for OCR, ASR, and processor is inconsistent
- processor prompts live in env vars instead of versioned files

Both must be redesigned together.

## Files And Modules Likely To Change

Core Exocort modules:

- [exocort/settings.py](/Users/joselu/Proyectos/exocort/exocort/settings.py)
- [exocort/runner.py](/Users/joselu/Proyectos/exocort/exocort/runner.py)
- [exocort/collector/app.py](/Users/joselu/Proyectos/exocort/exocort/collector/app.py)
- [exocort/collector/config.py](/Users/joselu/Proyectos/exocort/exocort/collector/config.py)
- [exocort/collector/vault.py](/Users/joselu/Proyectos/exocort/exocort/collector/vault.py)
- [exocort/processor/__main__.py](/Users/joselu/Proyectos/exocort/exocort/processor/__main__.py)
- [exocort/processor/config.py](/Users/joselu/Proyectos/exocort/exocort/processor/config.py)
- [exocort/processor/engine.py](/Users/joselu/Proyectos/exocort/exocort/processor/engine.py)

Tests and docs that will also need migration:

- [tests/test_settings.py](/Users/joselu/Proyectos/exocort/tests/test_settings.py)
- [tests/test_collector_config.py](/Users/joselu/Proyectos/exocort/tests/test_collector_config.py)
- [tests/test_processor_pipeline.py](/Users/joselu/Proyectos/exocort/tests/test_processor_pipeline.py)
- [tests/test_vault.py](/Users/joselu/Proyectos/exocort/tests/test_vault.py)
- [README.md](/Users/joselu/Proyectos/exocort/README.md)
- [docs/data-flow.md](/Users/joselu/Proyectos/exocort/docs/data-flow.md)

## Recommended Implementation Order

Follow this order. Do not start with stage logic before config and storage are stable.

### Step 1. Build typed config first

Deliverables:

- one explicit YAML config path per run
- typed config models
- loader function
- CLI `--config` support

Actions:

- define all top-level config sections
- add model validation
- add path resolution relative to config file
- add secret reference resolution
- wire entrypoints to receive config objects
- make `--config` the source of the single active user config
- treat additional YAML files only as alternative presets, not merge inputs

Why first:

- every component depends on config
- without this, the provider-per-stage design cannot be implemented cleanly

Important rule:

- the runtime must load one chosen YAML file and instantiate one `AppConfig`
- do not build a system that reads `base.yaml` plus `local.yaml` plus `processor.yaml` unless that composition model is explicitly designed later

### Step 2. Remove main runtime dependence on `.env`

Deliverables:

- no mandatory dotenv load in main Exocort runtime
- no user-facing env setup instructions

Actions:

- delete `load_dotenv` from main settings path
- remove ad hoc `os.environ` reads in runtime modules
- convert tests to use temp YAML config fixtures

Pitfall:

- do not leave hidden config backdoors in collector or processor modules

### Step 3. Build storage and repository abstractions

Deliverables:

- `vault/graph/` directory model
- entity repositories
- state repository
- run trace repository

Actions:

- define file naming or record key conventions
- define indexes for relations and timestamps
- make writes atomic
- add idempotent commit logic

Pitfall:

- do not archive and delete upstream evidence as the primary processing model

### Step 4. Implement scheduler and stage registry

Deliverables:

- stage registry
- readiness evaluator
- worker leasing
- run tracing

Actions:

- define a `StageExecutor` interface
- add `deterministic`, `structured`, and `agentic` stage modes
- support per-stage concurrency and retry rules

Pitfall:

- parallel does not mean race-prone; leases or idempotency keys are mandatory

### Step 5. Implement the lower layers first

Deliverables:

- `raw_events`
- `normalized_events`
- `atomic_events`
- `sessions`

Actions:

- normalize raw OCR/ASR vault records
- enrich into atomic events
- design session boundary logic
- keep evidence links at every step

Pitfall:

- do not let the LLM decide purely mechanical session boundaries if deterministic rules suffice

### Step 6. Implement higher semantic layers

Deliverables:

- `processes`
- `semantic_clusters`
- `notes`
- `knowledge_items`
- `user_model`

Actions:

- define readiness conditions carefully
- keep note generation separate from user-model consolidation
- add confidence, strength, and evidence on every semantic artifact

Pitfall:

- do not jump from notes directly to user model without `knowledge_items`

### Step 7. Add agentic capabilities selectively

Deliverables:

- internal tools
- skill bundles
- agent traces
- bounded handoff support

Actions:

- start with one agentic stage only
- keep commit logic outside the free-form agent loop
- validate all proposed outputs before persistence

Pitfall:

- do not make every stage agentic; most stages should stay deterministic or structured

## Detailed Migration Checklist By Concern

### Config Concern

- replace env getters
- remove duplicated config ownership
- centralize prompts, schemas, taxonomies, and providers
- introduce secret references

### Scheduling Concern

- define ready inputs per stage
- define when an entity is stable enough for downstream processing
- define retries and dead-letter policies
- define concurrency model

### Data Integrity Concern

- stable IDs
- explicit relation fields
- schema validation
- run tracing
- append-only history where feasible

### Semantic Quality Concern

- taxonomy control
- confidence scoring
- deduplication rules
- contradiction handling
- decay for stale user-model facts

## Non-Negotiable Constraints

The engineer should not cut these corners:

- do not keep `.env` as the real config source and call it a redesign
- do not silently merge multiple user YAML files in one run
- do not keep the old L1/L2/L3/L4 naming as the main conceptual model
- do not archive away the only copies of upstream evidence
- do not let notes become the direct source of truth for the user model
- do not allow free-form stage outputs without schema validation

## Suggested Deliverable Breakdown

### Milestone 1: Config foundation

- unified YAML config
- typed loader
- secrets support
- entrypoint wiring

### Milestone 2: Graph foundation

- repositories
- IDs
- relation indexes
- run traces

### Milestone 3: Scheduler foundation

- stage registry
- readiness evaluation
- leases
- concurrency controls

### Milestone 4: Lower pipeline

- normalization
- atomic events
- sessionization

### Milestone 5: Higher pipeline

- processes
- clusters
- notes
- knowledge items
- user model

### Milestone 6: Agentic layer

- tool registry
- skill packaging
- agentic stage runtime
- evals and guardrails

## Documentation The Engineer Should Produce While Implementing

As part of the implementation, the engineer should also create:

- a real config example for local-only setup
- a real config example for mixed local-plus-cloud setup
- a migration note explaining removed `.env` settings
- per-stage schema docs
- a troubleshooting note for provider auth and secret resolution

## Done Means

The redesign should be considered complete only when another engineer can:

1. clone the repo
2. create one config YAML such as `config/exocort.local.yaml`
3. provide secrets in the supported mechanism
4. start the system with `--config /path/to/that.yaml` and without `.env`
5. inspect `vault/graph/` and follow the lineage from raw event to user model

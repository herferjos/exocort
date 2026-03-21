# Decisions And Next Steps

## Status

Current Exocort code still reflects a simpler processor pipeline:

- raw vault inputs
- L1 cleaned events
- L2 grouped timeline entries
- L3 notes and user model
- optional L4 reflections

This architecture spec defines the redesign target that should replace that model.

This document is intentionally no longer a list of speculative doubts. It records the current decisions that implementation should follow unless the user explicitly changes them.

## Decided Baseline

### 1. Sessionization

Decision:

- sessions are deterministic first, not LLM-first
- they are built from temporal and contextual continuity
- when the boundary is ambiguous, prefer splitting instead of over-merging
- sessions may be reopened for a short stabilization window if new compatible events arrive

Implementation consequences:

- define inactivity thresholds
- define app/window/document continuity heuristics
- define a short reopen window for recent sessions
- keep a session state machine with at least `open`, `stabilizing`, and `closed`

### 2. Taxonomy

Decision:

- top-level categories are controlled by the system
- LLMs may suggest labels or subtypes, but they do not invent uncontrolled top-level classes
- category consistency matters more than expressive novelty

Baseline top-level types:

- `skill`
- `interest`
- `preference`
- `habit`
- `goal`
- `project`
- `constraint`
- `topic`
- `tooling_preference`
- `behavior_pattern`
- `domain_expertise`

Implementation consequences:

- keep taxonomy files versioned
- validate every LLM output against allowed types
- map unknown suggestions into existing categories or reject them

### 3. User Model Consolidation

Decision:

- the user model is updated from `knowledge_items`, never directly from notes
- promotion into the user model depends on confidence, repeated evidence, and recency
- old signals must decay over time
- contradictory evidence can weaken or deprecate items

Implementation consequences:

- track `confidence`, `strength`, `frequency`, `recency`, and `trend`
- version every user-model write
- keep source links from user model to knowledge items and lower evidence

### 4. Unified Config

Decision:

- there is exactly one active YAML config file per execution
- the YAML path is provided explicitly at launch with `--config`
- multiple YAML files may exist only as alternative presets such as local-only, cloud-only, or mixed
- the runtime does not merge multiple user YAML files implicitly

Implementation consequences:

- remove `.env` as the primary config source
- replace env-driven settings with typed config loading
- centralize OCR, ASR, collector, runner, and processor config in one tree

### 5. Provider Routing

Decision:

- each processor stage selects its own provider and model
- cheap local models should be preferred for lower-risk or high-volume stages
- stronger cloud reasoning models should be reserved for consolidation, clustering, and conflict-heavy tasks

Implementation consequences:

- add a provider registry in the unified config
- validate provider references at startup
- persist provider and model metadata for every run

### 6. Agentic Stages

Decision:

- not every stage is agentic
- deterministic and structured stages remain the default
- agentic execution is allowed only where multi-step tool use materially improves outcomes
- every agentic stage must still end in validated structured output before commit

Implementation consequences:

- support `deterministic`, `structured`, and `agentic` stage modes
- keep tool use bounded and auditable
- never let free-form agent output bypass validation

## Rollout Phases

### Phase A: Config And Infrastructure

Build:

- unified YAML config
- typed config loader
- secrets resolution
- storage primitives
- persistent IDs
- schema versioning

### Phase B: Structural Graph

Build:

- raw events catalog
- normalized events
- atomic events
- sessions
- relation traversal helpers

### Phase C: Semantic Layers

Build:

- processes
- semantic clusters
- notes
- prompt validation and retry logic

### Phase D: Knowledge Layers

Build:

- knowledge extraction
- knowledge deduplication
- user model versions
- consolidation scoring
- decay and deprecation logic

### Phase E: Agentic And Operational Refinement

Build:

- bounded tool registry
- skills
- agentic stage runtime
- quality metrics
- backfill and recompute tooling

## Immediate Next Steps

1. Implement the unified config model and remove `.env` from the main Exocort runtime.
2. Create the `vault/graph` storage contract with typed entity schemas and relation fields.
3. Replace the fixed L1/L2/L3/L4 processor runtime with a stage registry and scheduler.
4. Implement `normalized_events`, `atomic_events`, and deterministic `sessions` before higher semantic stages.
5. Add `knowledge_items` as the mandatory layer before `user_model`.
6. Add provider-per-stage routing, prompt files, schemas, and run tracing.

## Rule For Future Decisions

If an implementation detail is still materially ambiguous and would change system behavior, the engineer should ask the user directly and resolve it explicitly.

The architecture docs should not accumulate speculative "open questions" when a concrete baseline can be chosen safely.

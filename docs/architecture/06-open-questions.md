# Open Questions And Next Steps

## Implementation Status

Current Exocort code still reflects a simpler processor pipeline:

- raw vault inputs
- L1 cleaned events
- L2 grouped timeline entries
- L3 notes and user model
- optional L4 reflections

This spec defines the target architecture for the next iteration.

## Open Questions

These are the three most important unresolved design decisions.

### 1. Sessionization Rules

Still needs a concrete algorithm for:

- inactivity timeout thresholds
- app/window/URL continuity scoring
- interrupt handling
- cross-device or cross-source merges
- when to split versus extend a session

### 2. Initial Taxonomy

Still needs a first stable taxonomy for:

- session categories
- process categories
- cluster topics
- note types
- knowledge item types and subtypes

### 3. User Model Consolidation Rules

Still needs explicit thresholds for:

- promotion from note-derived signal to stable user-model fact
- decay over time
- contradiction handling
- merge rules for semantically similar knowledge items
- confidence versus strength interactions

## Recommended Rollout Phases

### Phase A: Infrastructure

Build:

- ingestion contracts
- normalization layer
- persistent IDs
- schema versioning
- storage primitives

### Phase B: Structural Graph

Build:

- sessionization
- process entities
- semantic cluster entities
- relation traversal helpers

### Phase C: Semantic Artifacts

Build:

- titles
- descriptions
- categories
- notes
- prompt validation and retry logic

### Phase D: Knowledge Layer

Build:

- knowledge extraction
- consolidation scoring
- user model versions
- decay and deprecation logic

### Phase E: Refinement

Build:

- taxonomy governance
- semantic deduplication
- quality metrics
- backfill and recompute tooling

## Suggested Immediate Next Steps

1. Define the canonical schemas for `raw_event`, `normalized_event`, `atomic_event`, `session`, `process`, `note`, and `knowledge_item`.
2. Decide whether `normalized_events` and `atomic_events` should be separate persisted collections or a single collection with derivation stages.
3. Write deterministic sessionization rules before implementing process clustering.
4. Introduce relation fields and stable IDs in the current processor output so migration is easier.
5. Split the current L1/L2/L3 prompts into explicit contracts aligned with this architecture.
6. Add fixtures and tests that verify upward and downward traceability.

## Migration Guidance

To evolve from the current processor incrementally:

1. keep existing vault ingestion unchanged
2. refactor current L1 output into normalized or atomic events
3. replace current L2 grouping with explicit sessions, then processes
4. keep note generation as a later stage rather than using summaries as pipeline input
5. insert a `knowledge_items` layer before writing the user model
6. version user model writes from the beginning


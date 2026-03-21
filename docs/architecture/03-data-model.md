# Data Model

## Canonical Entity Types

The target architecture uses these primary entity types:

- `raw_event`
- `normalized_event`
- `atomic_event`
- `session`
- `process`
- `semantic_cluster`
- `note`
- `knowledge_item`
- `user_model`
- `user_model_version`

## ID Strategy

Every entity needs a persistent, correlatable identifier.

Recommended ID fields:

- `raw_event_id`
- `event_id`
- `atomic_event_id`
- `session_id`
- `process_id`
- `cluster_id`
- `note_id`
- `knowledge_item_id`
- `user_model_id`
- `user_model_version`

ID requirements:

- stable across reprocessing where possible
- globally unique within each entity type
- independent from display labels
- preserved in all downstream references

## Relationship Contract

Every non-root entity should expose explicit link fields.

Minimum link fields:

- `source_ids`: direct upstream evidence
- `parent_ids`: direct structural parents
- `child_ids`: direct structural children
- `derived_ids`: directly emitted downstream objects
- `evidence_ids`: all records used to justify the object

Optional but recommended:

- `supersedes_id`
- `superseded_by_id`
- `merged_from_ids`
- `replaced_by_id`

## Confidence Model

All semantically derived entities should carry machine-readable uncertainty fields.

Recommended fields:

- `confidence`: confidence in correctness
- `strength`: confidence adjusted by repeated evidence
- `evidence_count`
- `frequency`
- `recency`
- `persistence`
- `diversity_of_evidence`
- `negative_evidence`
- `trend`

### Interpretation

- `confidence` answers: "How likely is this inference correct?"
- `strength` answers: "How established is this concept in the graph?"
- `trend` answers: "Is this signal increasing, stable, or fading?"

## Taxonomy Strategy

The system should use a hybrid taxonomy model.

### Closed categories

These must be stable and system-defined:

- `skill`
- `interest`
- `preference`
- `habit`
- `goal`
- `project`
- `constraint`
- `topic`

### Semi-open subtypes

These allow structured extension without creating top-level instability.

Examples:

- `skill.subtype = programming_language | tool | methodology`
- `preference.subtype = format | workflow | communication`
- `interest.subtype = technical | personal | professional`

### Controlled open categories

These may be suggested by LLMs but require explicit semantic validation:

- `domain_expertise`
- `identity_signal`
- `behavior_pattern`
- `tooling_preference`
- `working_style`

## User Model Categories

The user model should consolidate into the following top-level domains.

### Skills

Represents explicit or inferred capabilities.

Suggested fields:

- `name`
- `confidence`
- `strength`
- `evidence_count`
- `first_seen`
- `last_seen`
- `proficiency_estimate`
- `trend`
- `source_ids`

### Interests

Represents recurrent exploration or consumption patterns.

Suggested fields:

- `name`
- `strength`
- `recency`
- `frequency`
- `trend`
- `evidence_ids`

### Preferences

Represents stable choices about format, workflow, or tooling.

Suggested fields:

- `preference_type`
- `value`
- `scope`
- `confidence`
- `strength`
- `source_ids`

### Habits

Represents repeated temporal or behavioral patterns.

Suggested fields:

- `pattern`
- `periodicity`
- `confidence`
- `strength`
- `last_observed`
- `source_ids`

### Projects

Represents active or historical initiatives.

Suggested fields:

- `name`
- `status`
- `related_topics`
- `confidence`
- `last_seen`
- `source_ids`

### Goals

Represents explicit or inferred objectives.

Suggested fields:

- `goal_statement`
- `priority`
- `confidence`
- `time_horizon`
- `source_ids`

### Constraints

Represents stable restrictions or non-negotiable preferences.

Suggested fields:

- `constraint`
- `hardness`
- `confidence`
- `source_ids`

### Working Style

Represents how the user tends to operate.

Examples:

- iterative
- technical
- structured
- automation-oriented
- low-friction

## Consolidation Rules

A knowledge item should enter the user model when at least one of these is true:

1. it appears repeatedly across notes or contexts
2. it appears once with unusually strong explicit evidence
3. it encodes a clearly stated preference or hard constraint

Strength should increase when:

- the same item appears in different contexts
- the same item appears across different time windows
- evidence comes from distinct sources or activity types

Strength should decrease when:

- evidence becomes stale
- repeated contradictions appear
- the signal stops recurring

An item should be deprecated when:

- evidence is too weak
- stronger contradictory evidence exists
- the item is identified as noise or duplication

## Versioning

The system should version:

- prompt schemas
- taxonomies
- entity schemas
- user model snapshots
- consolidation rules

Recommended metadata:

- `schema_version`
- `taxonomy_version`
- `llm_version`
- `prompt_version`
- `consolidation_version`
- `generated_at`


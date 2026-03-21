# Pipeline

## End-to-End Flow

```text
raw_events
  -> normalized_events
  -> atomic_events
  -> sessions
  -> processes
  -> semantic_clusters
  -> notes
  -> knowledge_items
  -> user_model
```

## Layer Definitions

### Level 0: `raw_events`

Raw source records as ingested from capture or upstream processors.

Examples:

- screen OCR payload
- audio transcription payload
- foreground app/window change
- URL change
- text input event
- click
- copy/paste
- shell command

Rules:

- no semantic inference
- no loss of source payload
- immutable after ingestion except status metadata

### Level 1: `normalized_events`

Canonicalized records that unify source-specific payloads into a common structure.

Typical fields:

- `event_id`
- `raw_event_id`
- `timestamp`
- `source`
- `app`
- `window_title`
- `url`
- `content`
- `event_type`
- `raw_payload`
- `fingerprint`

Rules:

- normalize shape, not meaning
- preserve pointers to original source data
- allow deterministic deduplication

### Level 1b: `atomic_events`

Smallest semantically useful units produced from normalized inputs.

Examples:

- "editing authentication config"
- "reading OpenAI docs"
- "discussing processor architecture"

Rules:

- one atomic event should express one meaningful action or state
- enrichment may use local context, but must not invent facts
- confidence and evidence must be attached

### Level 2: `sessions`

Operationally continuous blocks of activity.

Useful signals:

- temporal proximity
- same app or same window
- same URL or base domain
- same document
- same thread or workspace

Examples:

- working in VS Code
- reading docs in a browser
- replying to email
- navigating LinkedIn

Rules:

- sessions are mostly deterministic
- they optimize for continuity, not deep meaning
- ambiguous boundaries should favor smaller sessions over merged ones

### Level 3: `processes`

Higher-level units of work or intent that can span multiple sessions.

Examples:

- debugging a bug
- preparing an interview
- researching a library
- writing a design doc
- planning a trip

Rules:

- processes are semantic and may require LLM assistance
- prefer separating uncertain candidates instead of over-merging
- process state should be explicit: `active`, `stale`, `done`, `unknown`

### Level 4: `semantic_clusters`

Topic- or meaning-based groupings across processes.

Examples:

- software development
- job search
- technical learning
- professional communication
- administrative tasks

Rules:

- clusters group by meaning, not just adjacency
- a cluster may contain multiple long-running processes
- clusters should be taxonomy-aware and deduplicated

### Level 5: `notes`

Useful inbox-ready artifacts derived from processes or clusters.

A note is not just a summary. It should be a standalone unit of insight, action, observation, or reminder.

Examples:

- recurrent interest in local-first tooling
- ongoing work on Exocort processor architecture
- preference for low-friction automation
- switch in focus from capture to semantic consolidation

Rules:

- must be readable on their own
- must preserve trace links to lower layers
- should represent a conclusion, observation, or action

### Level 6: `knowledge_items`

Normalized, structured knowledge extracted from notes.

Supported base types:

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

Rules:

- items are atomic and typed
- each item must include evidence and confidence
- duplicate concepts should merge semantically where possible

### Level 7: `user_model`

Consolidated representation of the user based on accumulated knowledge items.

Required characteristics:

- stable over time
- confidence-aware
- trend-aware
- versioned
- evidence-backed

The user model is not a dump of notes or items. It is a scored synthesis.

## Grouping Criteria

Different layers use different grouping logic.

### Temporal

Used for:

- sessionization
- interruption handling
- daily segmentation

### Contextual

Used for:

- same app/window/document grouping
- URL/thread/workspace continuity
- tool-specific continuity

### Semantic

Used for:

- process formation
- cluster formation
- note subject normalization

### Intentional

Used for:

- inferring likely goals or tasks
- deciding whether sessions belong to the same process

### Entity-centric

Used for:

- grouping by project, company, person, tool, or topic

### Recurrent-pattern

Used for:

- habits
- working style
- repeated interests
- behavior patterns

## Traceability Model

Each layer must support upward and downward traversal.

Forward flow:

```text
raw_event -> normalized_event -> atomic_event -> session -> process -> cluster -> note -> knowledge_item -> user_model
```

Reverse flow:

```text
user_model -> knowledge_item -> note -> cluster -> process -> session -> atomic_event -> normalized_event -> raw_event
```

Required relation fields on derived entities:

- `parent_ids`
- `child_ids`
- `source_ids`
- `derived_ids`
- `evidence_ids`

## Incremental Update Strategy

When new events arrive:

```text
1. ingest raw event
2. normalize into canonical event form
3. enrich into atomic event if applicable
4. assign to an existing session or create a new one
5. update or create a process if cross-session intent emerges
6. update semantic clusters if topic alignment changes
7. emit or revise notes if a meaningful conclusion emerges
8. extract or merge knowledge items
9. update the user model if thresholds are met
10. optionally generate display summaries
```

## Guardrails

### Avoid oversummarization

Do not summarize before structural grouping is stable.

### Avoid category explosion

Use controlled taxonomies with mapping and validation.

### Avoid false certainty

Every semantic layer must store confidence, strength, and evidence.

### Avoid duplicate knowledge

Use semantic deduplication and versioned merges.

### Avoid stale profiles

Apply recency decay, contradiction handling, and periodic recomputation.


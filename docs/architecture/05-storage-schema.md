# Storage Schema

## Scope

This document defines a conceptual storage schema for the target architecture. It is intentionally technology-agnostic and can be implemented with:

- relational tables
- document collections
- hybrid object store plus metadata database

## `raw_events`

```json
{
  "raw_event_id": "...",
  "source": "...",
  "timestamp": "...",
  "payload": {},
  "ingested_at": "...",
  "hash": "...",
  "status": "new|processed|ignored"
}
```

## `events`

This collection may represent normalized events or atomic events depending on the eventual implementation split. If both are kept separately, the normalized layer should reference the raw record and the atomic layer should reference the normalized record.

```json
{
  "event_id": "...",
  "raw_event_id": "...",
  "timestamp": "...",
  "app": "...",
  "window_title": "...",
  "url": "...",
  "content": "...",
  "event_type": "...",
  "title": "...",
  "description": "...",
  "entities": [],
  "embedding_ref": "...",
  "confidence": 0.0
}
```

## `sessions`

```json
{
  "session_id": "...",
  "event_ids": ["..."],
  "start_time": "...",
  "end_time": "...",
  "label": "...",
  "intent": "...",
  "category": "...",
  "confidence": 0.0,
  "source_rules": [],
  "llm_version": "...",
  "taxonomy_version": "..."
}
```

## `processes`

```json
{
  "process_id": "...",
  "session_ids": ["..."],
  "title": "...",
  "purpose": "...",
  "category": "...",
  "state": "active|stale|done|unknown",
  "confidence": 0.0
}
```

## `semantic_clusters`

```json
{
  "cluster_id": "...",
  "process_ids": ["..."],
  "topic": "...",
  "subtopics": [],
  "summary": "...",
  "confidence": 0.0
}
```

## `notes`

```json
{
  "note_id": "...",
  "cluster_id": "...",
  "process_ids": ["..."],
  "session_ids": ["..."],
  "event_ids": ["..."],
  "title": "...",
  "body": "...",
  "category": "...",
  "subject": "...",
  "priority": "...",
  "confidence": 0.0,
  "created_at": "...",
  "note_type": "insight|summary|action|observation|reminder"
}
```

## `knowledge_items`

```json
{
  "knowledge_item_id": "...",
  "note_id": "...",
  "type": "skill|interest|preference|habit|goal|project|constraint|topic",
  "key": "...",
  "value": "...",
  "strength": 0.0,
  "confidence": 0.0,
  "evidence_ids": ["..."],
  "first_seen": "...",
  "last_seen": "...",
  "status": "active|tentative|deprecated"
}
```

## `user_model`

```json
{
  "user_model_id": "...",
  "version": 12,
  "skills": [],
  "interests": [],
  "preferences": [],
  "habits": [],
  "projects": [],
  "goals": [],
  "constraints": [],
  "working_style": [],
  "updated_at": "...",
  "source_knowledge_item_ids": ["..."]
}
```

## Recommended Common Metadata

Most collections should also support:

```json
{
  "schema_version": "...",
  "taxonomy_version": "...",
  "prompt_version": "...",
  "llm_version": "...",
  "parent_ids": [],
  "child_ids": [],
  "source_ids": [],
  "derived_ids": [],
  "evidence_ids": []
}
```

## Storage Notes

Recommended implementation characteristics:

- immutable raw records
- append-friendly derived layers
- lightweight indexes on time, type, and relation IDs
- ability to re-run derivation without losing prior versions
- ability to soft-deprecate derived items rather than deleting them

## Suggested Indexes

Useful indexes for most backends:

- by `timestamp`
- by `status`
- by `type` or `category`
- by `source_ids`
- by `evidence_ids`
- by `process_id`, `cluster_id`, `note_id`, `knowledge_item_id`
- by `updated_at`


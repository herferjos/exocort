# Overview

## Purpose

This specification defines the target semantic architecture for Exocort's processor layer.

The goal is to transform captured activity into a durable, traceable, incrementally updated knowledge graph that supports:

- structured event understanding
- automatic grouping and abstraction
- durable note generation
- normalized knowledge extraction
- user model consolidation

## Non-Goals

This architecture is not designed around:

- manual curation in the critical path
- summaries as the primary source of truth
- direct user model updates from raw notes
- free-form LLM outputs without schema validation
- category creation without taxonomy controls

## Core Principles

### 1. Fully automatic pipeline

The user is not in the loop for routine semantic decisions. The system must automatically decide:

- whether events belong to a session
- whether sessions belong to a process
- how an activity is labeled
- which notes should be emitted
- what enters the user model

To make that safe, the system combines:

- deterministic rules
- LLMs with structured outputs
- persistent IDs
- confidence scoring
- taxonomy versioning

### 2. The data graph is the system

LLMs are semantic engines, not the source of truth.

The source of truth is the graph of entities and relations connecting:

- events
- sessions
- processes
- semantic clusters
- notes
- knowledge items
- user model versions

### 3. Clear layer separation

The pipeline separates five concerns:

- factual capture: what happened
- operational grouping: what belongs together mechanically
- semantic interpretation: what the activity means
- derived knowledge: what can be learned from it
- consolidated profile: what is stable enough to say about the user

### 4. Bidirectional traceability

Every derived object must be explainable from its evidence, and every raw input must be traceable upward to any derived outputs it influenced.

### 5. Incremental, not full rebuild by default

The processor should update affected graph segments as new data arrives rather than recomputing the full model each time.

## Recommended Target Flow

```text
1. capture raw events
2. normalize raw events into atomic events
3. build sessions deterministically
4. refine sessions into processes with LLM assistance
5. cluster processes semantically with LLM assistance
6. generate notes from processes or clusters
7. extract normalized knowledge items from notes
8. consolidate knowledge items into the user model
9. generate summaries only as optional display artifacts
```

## Why This Design

This architecture improves on a flatter `events -> notes -> user_model` pipeline because it:

- reduces ambiguity between operational and semantic grouping
- keeps raw evidence available longer
- makes user-model updates auditable
- avoids losing information through early summarization
- supports deduplication and confidence-aware consolidation
- enables incremental updates and future backfills


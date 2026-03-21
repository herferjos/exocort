# LLM Contracts

## Role of LLMs in the System

LLMs are used where semantic interpretation adds value and deterministic logic is insufficient.

They should not be responsible for:

- identity management
- persistence
- graph integrity
- taxonomy authority
- traceability guarantees

Those responsibilities stay in application logic.

## Global Output Rules

Every semantic LLM step should follow these rules:

- use only the supplied context
- do not invent facts
- return structured output only
- include confidence where required
- prefer concise, factual labels
- preserve upstream IDs in outputs when relevant
- prefer separation over over-merging when uncertain

## LLM 1: Event Enrichment

### Purpose

Convert raw or normalized events into semantically useful atomic events.

### Inputs

- raw event or normalized event
- short local temporal context
- app, window, document, URL, or thread metadata

### Outputs

- title
- description
- event type
- detected entities
- tags
- confidence

### Output schema

```json
{
  "event_id": "e_123",
  "title": "Editing authentication config",
  "description": "The user modified configuration related to authentication.",
  "event_type": "edit",
  "entities": ["authentication", "config"],
  "tags": ["engineering", "configuration"],
  "confidence": 0.84
}
```

### Base prompt

```text
You are an event semantics engine.

Task:
Given a raw event and nearby context, produce a structured semantic enrichment.

Rules:
- Do not invent facts.
- Use only the provided context.
- Return JSON only.
- Include confidence for each field.
- Prefer concise and factual labels.

Input:
{raw_event}
{context}

Output schema:
{
  "title": "",
  "description": "",
  "event_type": "",
  "entities": [],
  "tags": [],
  "confidence": 0.0
}
```

## LLM 2: Session Labeling

### Purpose

Label sessions already built by deterministic rules.

### Inputs

- ordered event list
- temporal metadata
- dominant app or context signals
- optional taxonomy

### Outputs

- session title
- summary
- probable intent
- category
- confidence

### Base prompt

```text
You are a session labeling engine.

Task:
Given a sequence of normalized events, infer the session title, intent, and category.

Rules:
- Group only by the provided events.
- Use the taxonomy provided.
- Return JSON only.
- Do not overgeneralize.

Taxonomy:
{session_taxonomy}

Input:
{session_events}

Output schema:
{
  "session_title": "",
  "intent": "",
  "category": "",
  "summary": "",
  "confidence": 0.0
}
```

## LLM 3: Process Consolidation

### Purpose

Decide whether multiple sessions belong to a higher-level process.

### Inputs

- candidate sessions
- titles and summaries
- embeddings or semantic similarity features
- temporal metadata
- project or topic hints

### Outputs

- process title
- purpose
- category
- member session IDs
- confidence

### Base prompt

```text
You are a process consolidation engine.

Task:
Given multiple sessions, decide whether they belong to the same higher-level process.

Rules:
- Prefer temporal continuity, semantic coherence, and shared goal.
- If uncertain, keep processes separate.
- Return JSON only.

Input:
{sessions}

Output schema:
{
  "process_title": "",
  "purpose": "",
  "category": "",
  "session_ids": [],
  "confidence": 0.0
}
```

## LLM 4: Semantic Clustering

### Purpose

Group processes by broader meaning and recurring themes.

### Inputs

- processes
- existing cluster candidates
- prior notes
- topic taxonomy

### Outputs

- cluster title
- topic tags
- related process IDs
- confidence

## LLM 5: Note Generation

### Purpose

Generate a useful standalone note from a process or semantic cluster.

### Inputs

- cluster or process data
- supporting evidence
- note template or note type taxonomy

### Outputs

- title
- body
- category
- subject
- priority
- confidence
- trace links

### Base prompt

```text
You are a note generation engine.

Task:
Create a high-value note from a process or cluster.

Rules:
- The note must be useful on its own.
- Do not merely paraphrase the input.
- Capture the main conclusion, observation, or action.
- Return JSON only.

Input:
{cluster_or_process}
{evidence}

Output schema:
{
  "title": "",
  "body": "",
  "category": "",
  "subject": "",
  "priority": "",
  "confidence": 0.0,
  "trace_links": {
    "cluster_id": "",
    "process_ids": [],
    "session_ids": [],
    "event_ids": []
  }
}
```

## LLM 6: Knowledge Extraction

### Purpose

Extract normalized knowledge items from notes.

### Inputs

- note
- prior related notes
- current user model
- supported taxonomy

### Outputs

- typed knowledge items
- confidence
- strength
- evidence links
- suggested merge or update behavior

### Base prompt

```text
You are a knowledge extraction engine for a personal knowledge graph.

Task:
From a note and existing user model, extract normalized knowledge items.

Rules:
- Use only supported categories.
- Prefer stable, repeated, or explicitly stated facts.
- Each item must include confidence and evidence.
- Return JSON only.

Supported types:
{knowledge_types}

Input:
{note}
{existing_user_model}

Output schema:
{
  "knowledge_items": [
    {
      "type": "",
      "key": "",
      "value": "",
      "confidence": 0.0,
      "strength": 0.0,
      "evidence_ids": []
    }
  ]
}
```

## LLM 7: User Model Consolidation

### Purpose

Update the versioned user model from new and historical knowledge items.

### Inputs

- new knowledge items
- historical items
- current model state
- recency and frequency signals

### Outputs

- model delta
- version bump recommendation
- updated categories
- deprecated or weakened items

## Validation Layer

Every LLM output must be validated before persistence.

Required validation:

- JSON parse validation
- schema validation
- allowed taxonomy validation
- ID reference validation
- confidence range validation
- deduplication checks

Recommended fallback behavior:

- reject invalid outputs
- retry once with stricter repair prompt
- if still invalid, preserve the input for later reprocessing

## Prompt Versioning

Every prompt invocation should record:

- `prompt_key`
- `prompt_version`
- `model`
- `temperature`
- `input_hash`
- `generated_at`


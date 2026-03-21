# Exocort Architecture Spec v2

This folder defines the target processor architecture for evolving Exocort from a vault compaction pipeline into a traceable semantic knowledge graph.

This is an implementation target, not a description of the current codebase. The current processor still uses the simpler L1/L2/L3 pipeline described in [data-flow.md](/Users/joselu/Proyectos/exocort/docs/data-flow.md).

## Documents

- [01-overview.md](/Users/joselu/Proyectos/exocort/docs/architecture/01-overview.md): system goals, design principles, and architecture summary.
- [02-pipeline.md](/Users/joselu/Proyectos/exocort/docs/architecture/02-pipeline.md): end-to-end pipeline, layer definitions, update flow, and traceability rules.
- [03-data-model.md](/Users/joselu/Proyectos/exocort/docs/architecture/03-data-model.md): canonical entities, relationships, IDs, confidence model, and taxonomy rules.
- [04-llm-contracts.md](/Users/joselu/Proyectos/exocort/docs/architecture/04-llm-contracts.md): LLM roles, input-output contracts, prompting rules, and validation requirements.
- [05-storage-schema.md](/Users/joselu/Proyectos/exocort/docs/architecture/05-storage-schema.md): conceptual storage schema for collections/tables and suggested fields.
- [06-open-questions.md](/Users/joselu/Proyectos/exocort/docs/architecture/06-open-questions.md): unresolved decisions, rollout phases, and implementation sequence.
- [07-redesign-task-list.md](/Users/joselu/Proyectos/exocort/docs/architecture/07-redesign-task-list.md): implementation checklist grounded in the current processor and the target parallel DAG redesign.
- [08-agentic-executors.md](/Users/joselu/Proyectos/exocort/docs/architecture/08-agentic-executors.md): design guidance for agentic stages with tools, skills, handoffs, and provider routing.
- [09-unified-config.md](/Users/joselu/Proyectos/exocort/docs/architecture/09-unified-config.md): unified user configuration design replacing `.env` and fragmented JSON files.
- [10-implementation-playbook.md](/Users/joselu/Proyectos/exocort/docs/architecture/10-implementation-playbook.md): step-by-step engineering handoff for implementing the redesign safely.

## Architecture Summary

The target semantic flow is:

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

The guiding rule is:

> The LLM is not the system. The system is the data graph.

LLMs are used as semantic operators inside a pipeline that preserves structure, evidence, confidence, IDs, and versioning.

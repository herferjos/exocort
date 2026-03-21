# Agentic Executors

## Purpose

Some processor stages should remain structured one-shot transformations, but others may benefit from agentic execution:

- investigating conflicting evidence
- looking up prior graph state before merging
- selecting among competing taxonomic mappings
- running multiple tools before committing a normalized output
- performing careful deduplication or consolidation

This document describes how to design those agentic stages safely.

## When To Use Agentic Execution

Use `structured` mode when:

- the task is narrow
- the input and output schemas are simple
- the transformation can be done in one LLM pass
- tool use is unnecessary

Use `agentic` mode when:

- the stage may need multiple reasoning steps
- the stage benefits from tool calls
- the stage needs evidence retrieval across multiple graph layers
- the stage needs a handoff to a more specialized sub-agent or prompt bundle

Good candidates in Exocort:

- process consolidation
- semantic clustering
- knowledge extraction and deduplication
- user-model consolidation with contradiction review

## Recommended Architecture

Each agentic stage should still end in a validated structured commit.

Recommended lifecycle:

```text
1. scheduler selects ready inputs
2. agent receives bounded context and task contract
3. agent may call approved tools and skills
4. agent may hand off to a specialized sub-agent if configured
5. agent produces a structured proposed output
6. validator checks schema, taxonomy, IDs, and confidence
7. commit layer writes records and relations
```

## Skills

A useful current pattern comes from OpenAI's Skills support. Their docs define a skill as a versioned bundle of files plus a `SKILL.md` manifest containing instructions and supporting assets. The model sees skill metadata first, and if it chooses the skill, it reads the `SKILL.md` instructions from the mounted path. Source: OpenAI Skills guide: https://developers.openai.com/api/docs/guides/tools-skills

For Exocort, a skill should be treated as a reusable capability package for a stage. Examples:

- `taxonomy-normalizer`
- `event-entity-extractor`
- `process-merge-reviewer`
- `knowledge-deduplicator`
- `user-model-consolidation-policy`

Suggested local skill bundle layout:

```text
processor_skills/
  taxonomy-normalizer/
    SKILL.md
    mappings.json
    examples.json
  knowledge-deduplicator/
    SKILL.md
    merge_rules.md
    examples.json
```

## Tools

Agentic stages should use bounded internal tools instead of direct unrestricted access.

Recommended internal tools:

- `graph_lookup(ids | filters)` returns linked entities and relation metadata
- `evidence_fetch(entity_id)` returns the evidence chain for one entity
- `embedding_search(query | vector)` returns candidate semantic matches
- `taxonomy_map(label)` maps free-form labels to allowed taxonomy nodes
- `merge_preview(entity_ids)` computes a possible merged representation without committing
- `commit_candidate(payload)` writes only after validation and policy checks

If external tools are needed, use them through explicit adapters or MCP servers, not ad hoc code paths.

## Handoffs And Specialized Agents

OpenAI's current agent guidance explicitly recommends handoff when one agent should transfer work to a more specialized agent. Their docs say a handoff can be exposed as a function tool, and the Agents SDK can facilitate transfer between agents. Sources:

- OpenAI Voice agents guide: https://developers.openai.com/api/docs/guides/voice-agents
- OpenAI Agents announcement: https://openai.com/index/new-tools-for-building-agents/

For Exocort, handoffs are useful when a general stage planner needs to delegate to a narrower policy agent such as:

- `taxonomy_agent`
- `dedup_agent`
- `contradiction_agent`
- `evidence_agent`

The handoff output should include:

- rationale
- destination agent
- reduced working context
- expected output schema

## Provider Strategy

Agentic execution should support different providers by stage.

Recommended rule of thumb:

- use fast local models for cheap extraction, cleanup, and low-risk enrichment
- use stronger cloud reasoning models for consolidation, conflict resolution, and multi-step deduplication
- allow a stage to override both provider and model in config

Example:

```json
{
  "provider": "cloud_reasoning",
  "model": "gpt-5.4",
  "mode": "agentic",
  "skills": ["knowledge-deduplicator", "taxonomy-normalizer"],
  "tools": ["graph_lookup", "taxonomy_map", "merge_preview"],
  "max_agent_steps": 10
}
```

## Recommended Runtime Contract

Each agentic stage executor should expose:

- `collect_inputs()`
- `build_context()`
- `run_agent_loop()`
- `validate_candidate()`
- `commit()`
- `record_trace()`

The runtime should record:

- provider
- model
- prompt version
- skill versions
- tools used
- tool-call sequence
- input IDs
- output IDs
- runtime and retries

## Safety And Boundedness

OpenAI's current Skills documentation warns that skills should be treated as privileged code and instructions, and that unvetted skill selection increases prompt-injection and data-exfiltration risk. Source: OpenAI Skills guide: https://developers.openai.com/api/docs/guides/tools-skills

Practical implications for Exocort:

- skills must be developer-curated, not user-selectable
- networked tools must be opt-in per stage
- write actions should occur only through validated commit tools
- agent working context should be intentionally scoped, not full-vault by default

## Responses API And MCP Fit

OpenAI's current Responses API supports built-in tools, function calling, remote MCP servers, and skills. This makes it a reasonable mental model for building tool-using stages where the model can search, call tools, or use mounted skill bundles, while the application still owns validation and persistence. Source: OpenAI tools guide: https://developers.openai.com/api/docs/guides/tools

Their tools guide also documents remote MCP integration as a first-class tool type. That pattern is useful if Exocort later exposes graph operations or retrieval through a local MCP server instead of in-process Python calls. Source: https://developers.openai.com/api/docs/guides/tools

## Recommendation For Exocort

Start with a hybrid approach:

1. keep `normalized_events`, `atomic_events`, and `sessions` mostly deterministic or single-shot
2. make `processes`, `semantic_clusters`, `knowledge_items`, and `user_model` eligible for `agentic` mode
3. implement internal tools first
4. add skill bundles for taxonomy and deduplication second
5. add handoffs only after the single-agent loop is reliable

## Sources

- OpenAI Agents SDK: https://developers.openai.com/api/docs/guides/agents-sdk
- OpenAI Using tools: https://developers.openai.com/api/docs/guides/tools
- OpenAI Skills: https://developers.openai.com/api/docs/guides/tools-skills
- OpenAI Voice agents handoff guidance: https://developers.openai.com/api/docs/guides/voice-agents
- OpenAI announcement on Agents SDK, handoffs, guardrails, and tracing: https://openai.com/index/new-tools-for-building-agents/

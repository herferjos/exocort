# Notes Knowledge Principles

This document defines the intended behavior for Exocort's notes processor.

The goal is not to archive captures as summaries. The goal is to build a durable personal knowledge base: a wiki, an Obsidian-style vault, a second brain.

## What Good Notes Look Like

- Notes are organized by durable topics, concepts, tools, entities, projects, or areas of interest.
- Notes accumulate understanding over time instead of mirroring one batch or one session.
- Notes distill useful information into conclusions, takeaways, comparisons, definitions, workflows, and mental models.
- Notes prefer synthesis over transcription. Copy exact wording only when the wording itself is important.
- Notes should help future retrieval. A user should be able to open one note and quickly understand what is known about that topic.
- Notes should be written in the voice of the topic, not in the voice of the ingestion pipeline.
- Opinions, rankings, forecasts, and contested claims should stay attached to whoever made them.
- Notes may accumulate a working understanding of recurring people, companies, teams, products, and projects.
- Notes should build useful profiles, not just piles of remembered fragments.

## What To Avoid

- Do not create one note per batch, screenshot, audio clip, or browsing session.
- Do not produce diary, timeline, or session-log notes unless the user explicitly asks for chronology.
- Do not treat the output as a cleaned-up summary of "what was seen".
- Do not write notes as commentary about captures, screenshots, posts, or batches unless that provenance is itself important.
- Do not keep sections such as `Sources`, `References`, or `Recent Updates` as a default structure.
- Do not dump logs, UI chrome, repeated OCR fragments, or long unprocessed text blocks when the information can be synthesized.
- Do not present weakly supported inferences as certain facts.

## Organization Rules

- Choose note filenames from the subject, not from time or source.
- Split distinct themes into different notes when that improves clarity and later reuse.
- Merge new information into existing notes whenever the topic already exists.
- Prefer a few strong notes with clear scopes over many vague aggregate notes.
- Maintain entity knowledge over time when it is useful: what a person tends to care about, how a team seems to work, what a company appears to prioritize, or how a project is evolving.
- Prefer profile-shaped notes that answer "who is this?", "how do they think?", "what do they care about?", "how do they work?", or "what role do they play?".
- Do not retain details that do not improve the usefulness of the profile or note.
- When something is inferred rather than directly stated, label it as an inference, pattern, or working conclusion.
- Include a link when it is genuinely useful to preserve a canonical resource, benchmark, repo, paper, or action point.
- Prefer placing links inline near the relevant claim or example instead of collecting them in a generic link dump.
- Attribute statements when they are judgments rather than settled facts, for example product rankings, predictions, praise, criticism, or marketing claims.
- Prefer wording like "According to X, ..." or "Y argues that ..." when that attribution matters to interpretation.
- Use `Open Questions` for missing understanding, contradictions, weak evidence, or things worth investigating next.
- Prefer sentences like "Tamux Agent is..." over sentences like "A capture mentions Tamux Agent as...".

## Examples

- Reading several posts about OCR models should update notes such as `ocr.md`, `glm_ocr.md`, or another stable topic note, not a generic batch summary.
- Reading about Agent Skills should update `agent_skills.md` with what it is, what problems it solves, and what differentiates it.
- Seeing Exocort code, config, and runtime behavior should update `exocort_project.md` with a clearer model of the project, its architecture, and its operating loop.

# Architecture Principles

## Repository Layout

The repository is intentionally split into:

- `exocort/` for orchestration and capture
- `services/` for isolated HTTP services
- `services/common/` for shared schemas and utilities

That split is part of the design, not an accident of growth.

## Orchestrator vs Service

`exocort` should stay lightweight. It captures inputs, watches folders, and routes work to services.

Domain-specific intelligence should stay in the relevant service instead of leaking into the runner.

## `app/` and `src/`

The services consistently separate transport and implementation:

- `app/` holds FastAPI bootstrap, routers, and endpoints
- `src/` holds config, helpers, and domain logic

That layout is intentionally more structured than the current service sizes require, so future services can grow into it without rework.

## Shared Contracts

Public request and response shapes belong in `services/common` when they are shared by multiple services or are part of the external contract.

Use Pydantic models at the HTTP boundary. Use simpler internal types when the data is already validated.

## Filesystem Boundary

The project uses files as a stable handoff mechanism between capture, watch, and processing.

That means output files, temp files, and watched directories are part of the system design and should be treated carefully.

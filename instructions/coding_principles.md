# Coding Principles

This is the entry point for the project-specific guidance in Exocort.

Read this first, then jump to the linked docs depending on what you are changing:

- [architecture_principles.md](instructions/architecture_principles.md)
- [service_principles.md](instructions/service_principles.md)
- [runtime_observability.md](instructions/runtime_observability.md)

## Project Shape

Exocort is built around a thin local orchestrator and several focused services.

- `exocort/` coordinates capture and processing.
- `services/` contains standalone HTTP services.
- `services/common/` holds shared contracts and small utilities.

The codebase prefers explicit boundaries, simple flows, and stable contracts over abstraction-heavy design.

## Baseline Rules

- Keep the orchestrator thin.
- Keep services narrow and easy to reason about.
- Put public schemas in shared code only when they are truly shared.
- Prefer direct code over framework magic.
- Keep config obvious and local.
- Treat the filesystem as a real integration boundary when the repo already does so.

## What To Read Next

- Use [architecture_principles.md](instructions/architecture_principles.md) for repository shape, boundaries, and shared models.
- Use [service_principles.md](instructions/service_principles.md) for endpoint structure, startup flow, and service-local conventions.
- Use [runtime_observability.md](instructions/runtime_observability.md) for logging, lifecycle, and operational behavior.

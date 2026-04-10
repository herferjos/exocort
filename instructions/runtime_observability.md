# Runtime And Observability

## Logging

Use standard logging for runtime messages.

The repo should prefer readable, concrete operational messages over noisy or clever logs.

## Error Handling

Keep error handling pragmatic:

- fail fast when a required runtime resource is missing
- persist recoverable errors only when the artifact is useful
- avoid swallowing exceptions unless cleanup truly cannot fail the flow

## Lifecycle

Heavy resources should have an explicit startup path.

That keeps startup failures visible and prevents import-time side effects from hiding runtime costs.

## Settings Access

Settings should be cheap to load and, when practical, cached for the process lifetime.

If a module needs settings frequently, it should not reparse the environment repeatedly.

## Operational Messages

Logs and CLI messages should usually mention:

- file paths
- model names
- locale or language values
- byte counts
- processed item counts

Those are the details that help debug local runs quickly.

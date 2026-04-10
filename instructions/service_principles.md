# Service Principles

## One Service, One Job

Each service should focus on one capability:

- OCR
- transcription
- chat completion

Avoid turning a service into a general platform unless the project clearly needs it.

## Endpoint Shape

Keep APIs small, versioned, and obvious.

- `app/api/v1/` is the right place for routers and endpoints
- `main.py` should only bootstrap the app and start the server
- `api.py` should compose routers, not hold business logic

## Configuration

Service config is loaded from environment variables through a tiny `load_settings()` function.

That keeps runtime behavior explicit and easy to inspect.

## Startup and Health

Heavy resources should be loaded through the service lifecycle, not hidden at import time.

Health endpoints should report the real runtime state when possible, especially if a model or recognizer must be loaded before the service is usable.

## Module Naming

The current naming pattern is useful and should stay recognizable:

- `service.py` for the main operation
- `settings.py` for config loading
- `models.py` for local shapes
- `main.py` for process bootstrap
- `api.py` for router composition

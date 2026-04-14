from __future__ import annotations


def join_url(api_base: str, path: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith(path):
        return base
    return f"{base}{path}"


def maybe_join_openai_path(api_base: str, path: str) -> str:
    stripped = api_base.rstrip("/")
    if stripped.endswith(path):
        return stripped
    if stripped.endswith("/v1"):
        return f"{stripped}{path}"
    if "/v1/" in stripped:
        return stripped
    return f"{stripped}/v1{path}"

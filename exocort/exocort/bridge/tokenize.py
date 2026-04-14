from __future__ import annotations

def approximate_token_count(text: str) -> int:
    normalized = text.strip()
    if not normalized:
        return 0
    return max(1, (len(normalized) + 3) // 4)

__all__ = ["approximate_token_count"]

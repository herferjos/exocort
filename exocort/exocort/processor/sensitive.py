from __future__ import annotations

import re
from dataclasses import dataclass

from exocort.config import ContentFilterSettings


@dataclass(slots=True, frozen=True)
class ContentMatch:
    rule_name: str
    match_type: str
    pattern: str


def detect_content_match(config: ContentFilterSettings, text: str) -> ContentMatch | None:
    if not config.enabled:
        return None

    normalized_text = text.casefold()
    for rule in config.rules:
        for keyword in rule.keywords:
            normalized_keyword = keyword.casefold()
            if normalized_keyword in normalized_text:
                return ContentMatch(
                    rule_name=rule.name,
                    match_type="keyword",
                    pattern=keyword,
                )
        for regex in rule.regexes:
            if re.search(regex, text, re.IGNORECASE):
                return ContentMatch(
                    rule_name=rule.name,
                    match_type="regex",
                    pattern=regex,
                )
    return None

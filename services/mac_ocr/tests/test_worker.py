from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from src.app import ChatCompletionRequest, chat_completions


pytestmark = [pytest.mark.service, pytest.mark.unit, pytest.mark.ocr]


def test_chat_completions_returns_openai_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.app.ocr_image_path",
        lambda path: {
            "text": "hello world",
        },
    )
    payload = asyncio.run(
        chat_completions(
            payload=ChatCompletionRequest(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract text"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/png;base64,aGVsbG8=",
                                },
                            },
                        ],
                    }
                ],
            )
        )
    )

    assert payload["model"] == "gpt-4o-mini"
    assert payload["choices"][0]["message"]["content"] == "hello world"
    assert payload["choices"][0]["finish_reason"] == "stop"


def test_chat_completions_requires_image() -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            chat_completions(
                payload=ChatCompletionRequest(
                    messages=[
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": "only text"}],
                        }
                    ]
                )
            )
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Expected a user image in messages."


def test_chat_completions_wraps_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.app.ocr_image_path",
        lambda path: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            chat_completions(
                payload=ChatCompletionRequest(
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": "data:image/jpeg;base64,aGVsbG8=",
                                    },
                                }
                            ],
                        }
                    ]
                )
            )
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "missing"

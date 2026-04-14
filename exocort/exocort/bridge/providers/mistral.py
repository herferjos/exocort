from __future__ import annotations

from typing import Any

from ..client import HttpClient
from ..models.asr import AsrRequest, AsrResult
from ..models.ocr import OcrPage, OcrRequest, OcrResult
from ..models.response import ResponseRequest, ResponseResult
from ..utils.media import media_to_data_uri
from ..utils.provider import split_model_provider
from ..utils.urls import maybe_join_openai_path
from . import openai as openai_provider

DEFAULT_OCR_PROMPT = "Extract the readable text from this image. Return only the extracted text."


def asr(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: AsrRequest,
    extra_headers: dict[str, str],
) -> AsrResult:
    headers = {"x-api-key": api_key, **extra_headers}
    return openai_provider.asr(client, api_base, api_key, req, headers)


def ocr(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: OcrRequest,
    extra_headers: dict[str, str],
) -> OcrResult:
    _, model = split_model_provider(req.model)
    url = maybe_join_openai_path(api_base, "/ocr")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
        "Content-Type": "application/json",
        **extra_headers,
    }
    payload = {
        "model": model,
        "document": {
            "type": "image_url",
            "image_url": media_to_data_uri(req.media),
        },
    }
    response = client.post_json(url, headers=headers, payload=payload)
    payload_json = _require_payload(response.json)
    pages_payload = payload_json.get("pages")
    if not isinstance(pages_payload, list) or not pages_payload:
        raise ValueError("OCR response must include a non-empty `pages` list.")
    pages: list[OcrPage] = []
    texts: list[str] = []
    for index, item in enumerate(pages_payload):
        if not isinstance(item, dict):
            continue
        markdown = str(item.get("markdown", "")).strip()
        if not markdown:
            continue
        pages.append(OcrPage(index=index, text=markdown))
        texts.append(markdown)
    if not texts:
        raise ValueError("OCR page markdown is empty.")
    return OcrResult(
        text="\n\n".join(texts).strip(),
        pages=tuple(pages),
        raw=payload_json,
    )


def ocr_llm(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: OcrRequest,
    extra_headers: dict[str, str],
) -> OcrResult:
    prompt = req.prompt or DEFAULT_OCR_PROMPT
    result = response(
        client,
        api_base,
        api_key,
        ResponseRequest(
            model=req.model,
            messages=(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": media_to_data_uri(req.media)}},
                    ],
                },
            ),
        ),
        extra_headers,
    )
    text = result.text.strip()
    if not text:
        raise ValueError("OCR page markdown is empty.")
    return OcrResult(text=text, pages=(OcrPage(index=0, text=text),), raw=result.raw)


def response(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: ResponseRequest,
    extra_headers: dict[str, str],
) -> ResponseResult:
    headers = {"x-api-key": api_key, **extra_headers}
    return openai_provider.response(client, api_base, api_key, req, headers)


def _require_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        raise ValueError("OCR endpoint did not return JSON.")
    return payload

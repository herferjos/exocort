from __future__ import annotations

import base64
import mimetypes

from ..models.common import MediaInput


def media_to_data_uri(media: MediaInput) -> str:
    mime_type = guess_mime_type(media)
    encoded = media_to_base64(media)
    return f"data:{mime_type};base64,{encoded}"


def media_to_base64(media: MediaInput) -> str:
    if media.base64:
        return media.base64
    if media.file_path is None:
        raise ValueError("media requires file_path or base64 content.")
    return base64.b64encode(media.file_path.read_bytes()).decode("ascii")


def guess_mime_type(media: MediaInput) -> str:
    if media.mime_type:
        return media.mime_type
    if media.file_path is None:
        return "application/octet-stream"
    guessed, _ = mimetypes.guess_type(str(media.file_path))
    return guessed or "application/octet-stream"


def read_media_bytes(media: MediaInput) -> bytes:
    if media.file_path is None:
        raise ValueError("media file_path is required for this provider flow.")
    return media.file_path.read_bytes()

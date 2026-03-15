from __future__ import annotations

import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile

from .ocr import ocr_image_path


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


logging.basicConfig(
    level=getattr(
        logging, _env_str("MAC_OCR_LOG_LEVEL", "INFO").upper(), logging.INFO
    ),
    format="%(asctime)s | %(levelname)s | %(message)s",
)

app = FastAPI(title="Mac OCR Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True}


@app.get("/status")
def status() -> dict[str, object]:
    return {"ok": True, "service": "mac_ocr"}


@app.post("/ocr")
async def process_image(file: UploadFile = File(...)) -> dict[str, object]:
    suffix = Path(file.filename or "image.png").suffix or ".png"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        tmp_path.write_bytes(await file.read())
        return ocr_image_path(tmp_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> None:
    import uvicorn

    host = _env_str("MAC_OCR_HOST", "127.0.0.1")
    port = int(_env_float("MAC_OCR_PORT", 9091))
    uvicorn.run("src.app:app", host=host, port=port, reload=False)

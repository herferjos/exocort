from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile

from .config import HOST, PORT
from .ocr import ocr_image_path


app = FastAPI(title="Mac OCR", version="0.1.0")


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True}


@app.post("/ocr")
async def process_image(
    file: UploadFile = File(...),
    mode: str = Form("fast"),
) -> dict[str, object]:
    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        path = Path(tmp.name)
    try:
        path.write_bytes(await file.read())
        return ocr_image_path(path, mode=mode)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)


def main() -> None:
    import uvicorn
    uvicorn.run("src.app:app", host=HOST, port=PORT, reload=False)

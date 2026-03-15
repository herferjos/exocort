from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app import main as serve_main
from .ocr import ocr_image_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Native macOS Vision OCR HTTP service.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Run the HTTP OCR service.")
    ocr_file = sub.add_parser(
        "ocr-file",
        help="Run OCR for one image file and print the JSON result.",
    )
    ocr_file.add_argument("path", help="Image file path")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "serve":
        serve_main()
        return

    result = ocr_image_path(Path(args.path).expanduser().resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False))

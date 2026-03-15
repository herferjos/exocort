from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app import build_config
from .app import main as serve_main
from .asr import ensure_speech_permission, transcribe_audio_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Native macOS speech-to-text HTTP service."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Run the HTTP transcription service.")
    transcribe = sub.add_parser(
        "transcribe-file",
        help="Transcribe one audio file and print the JSON result.",
    )
    transcribe.add_argument("path", help="Audio file path")
    transcribe.add_argument(
        "--language",
        default=None,
        help="Override the default locale/language",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "serve":
        serve_main()
        return

    config = build_config()
    if not ensure_speech_permission(prompt=config.prompt_permission):
        raise SystemExit("Speech recognition permission is required for mac_asr.")

    path = Path(args.path).expanduser().resolve()
    result = transcribe_audio_file(
        path,
        locale=args.language or config.locale,
        timeout_s=config.transcription_timeout_s,
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

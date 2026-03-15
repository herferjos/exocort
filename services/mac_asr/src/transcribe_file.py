from __future__ import annotations

import json
import sys
from pathlib import Path

from .asr import transcribe_audio_file_direct


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: python -m src.transcribe_file <wav_path> <locale> <timeout_s>")

    wav_path = Path(sys.argv[1]).expanduser().resolve()
    locale = sys.argv[2]
    timeout_s = float(sys.argv[3])

    transcription = transcribe_audio_file_direct(
        wav_path,
        locale=locale,
        timeout_s=timeout_s,
    )
    print(json.dumps(transcription.to_dict(), ensure_ascii=False))


if __name__ == "__main__":
    main()

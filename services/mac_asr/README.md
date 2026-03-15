# Mac ASR Service

Native macOS speech-to-text HTTP service. It receives uploaded audio files, sends them through the system Speech framework, and returns the transcription as JSON.

## Endpoints

- `GET /health`
- `GET /status`
- `POST /v1/audio/transcriptions`

The transcription endpoint follows the common multipart shape:

- `file`: audio file
- `language`: optional locale override, for example `es-ES`
- `model`: accepted for compatibility but ignored
- `prompt`: accepted for compatibility but ignored

Response:

```json
{
  "text": "hello world",
  "locale": "en",
  "is_final": true
}
```

## Permissions

macOS Speech Recognition permission is required. If you run it from Cursor or Terminal, allow that app in **System Settings -> Privacy & Security -> Speech Recognition**.

## Usage

From `services/mac_asr`:

```bash
uv sync
uv run mac-asr-service serve
```

Transcribe one local file:

```bash
uv run mac-asr-service transcribe-file /path/to/audio.wav --language es-ES
```

Defaults:

- host: `127.0.0.1`
- port: `9092`
- locale: `es-ES`

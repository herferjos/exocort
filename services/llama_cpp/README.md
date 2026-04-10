# Llama.cpp service

Minimal HTTP service that exposes an OpenAI-compatible chat completion endpoint
backed by `llama-cpp-python`.

Endpoint

- `POST /v1/chat/completions`

Request JSON (subset):

- `messages`: list of `{ role, content }`
- `temperature`, `max_tokens`, `top_p`, `stop`
- `stream` is rejected (non-streaming only)

Response JSON:

Matches the OpenAI `chat.completions` schema with `choices[]` and `usage`.

Configuration

Environment variables:

- `LLAMA_CPP_MODEL_ID`: required Hugging Face repo id for auto-download (e.g. `TheBloke/Mistral-7B-Instruct-v0.2-GGUF`)
- `LLAMA_CPP_QUANTIZATION`: required quantization level of the model to download (e.g. `Q4_K_M`)
- `LLAMA_CPP_MODEL_DIR`: download target directory (default `./models`)
- `LLAMA_CPP_CTX`: context size (default 4096)
- `LLAMA_CPP_N_GPU_LAYERS`: GPU layers (default 0)
- `LLAMA_CPP_THREADS`: CPU threads (default 0 = llama.cpp default)
- `LLAMA_CPP_N_BATCH`: Batch size (default 512)
- `LLAMA_CPP_SEED`: Seed for reproducibility (default 42)
- `LLAMA_CPP_TEMPERATURE`: default temperature (default 0.2)
- `LLAMA_CPP_HOST`: bind host (default 127.0.0.1)
- `LLAMA_CPP_PORT`: bind port (default 9100)
- `LLAMA_CPP_RELOAD`: enable `uvicorn` reload in local development (default True)

Running

From `services/llama_cpp`:

```bash
uv sync
uv run llama-cpp-service
```

Copy `.env.example` to `.env` before running. The example file includes the code defaults for optional runtime knobs and sample values for the required model settings.

If the model file is not present locally, the service will download the specified
quantization of the model from Hugging Face on startup.

Testing
-------

You can test the chat completions endpoint with `curl`:

```bash
curl -X POST http://127.0.0.1:9100/v1/chat/completions \
-H "Content-Type: application/json" \
-d '{
  "messages": [
    {
      "role": "user",
      "content": "Hello! Can you tell me a joke?"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 100
}'
```

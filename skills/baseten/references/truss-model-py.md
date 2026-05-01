# Python-class Truss (`model.py`)

The Python-class flavor runs user-written Python in the request path via a `Model` class with three methods. Pick it when you need Python pre- or post-processing, custom architectures not covered by an engine, or anything that doesn't fit a ready-made HTTP server.

If an off-the-shelf server (vLLM, TGI, SGLang, Triton) or a Baseten engine (TensorRT-LLM, BEI, BIS-LLM) does the job, prefer those instead. See `truss-custom-servers.md` and `truss-config.md` (engines section).

This skill covers the core contract. Sophisticated streaming patterns, custom batching, and performance tuning of the in-process server are intentionally out of scope; consult <https://docs.baseten.co/development/model> and the examples repo for those.

## Directory shape

```
my-model/
├── config.yaml
├── model/
│   └── model.py
├── packages/          # optional: local Python packages copied into the image
└── data/              # optional: static data bundled with the model
```

`truss init my-model` generates this scaffold.

## The `Model` class

The official starter template (from `truss init`) is:

```python
class Model:
    def __init__(self, **kwargs):
        # self._data_dir = kwargs["data_dir"]
        # self._config = kwargs["config"]
        # self._secrets = kwargs["secrets"]
        self._model = None

    def load(self):
        # Load model here and assign to self._model.
        pass

    def predict(self, model_input):
        # Run model inference here
        return model_input
```

### What `__init__` receives

Truss inspects the `__init__` signature and passes only the keyword arguments it explicitly accepts. The recognized names (per `truss/templates/server/model_wrapper.py`) are:

- `config`: parsed `config.yaml` as a dict.
- `data_dir`: path to the bundled `data/` directory.
- `secrets`: dict mapping declared secret name to value.
- `lazy_data_resolver`: helper for lazily-resolved external data.
- `environment`: information about the environment the deployment is attached to (e.g. `production`), or `None`.

Two equivalent styles:

```python
def __init__(self, **kwargs):           # receive everything Truss provides
    self._secrets = kwargs.get("secrets", {})

def __init__(self, secrets, config):    # receive only what you name
    self._secrets = secrets
```

### `load`

Runs once after `__init__`, before the server accepts requests. Load weights and other heavy resources here so the readiness check correctly gates traffic.

### `predict`

Runs per request. Receives the request body (typically a dict). Returns a dict, bytes, or a generator (see streaming below).

## Worked examples

For real model code, do not invent it. Read the examples repo, where each model directory has a complete `config.yaml` plus `model/model.py`:

- <https://github.com/basetenlabs/truss-examples>

Common starting points include the LLM examples (e.g. Mistral, Llama variants), image generation (SDXL), and multimodal pipelines.

## Streaming responses

Return a generator from `predict` to stream chunks. The server emits them as a streaming HTTP response; clients read with `requests` + `iter_content`, SSE parsers, or the OpenAI SDK for OpenAI-compatible payloads.

```python
def predict(self, model_input):
    prompt = model_input["prompt"]
    for token in self._stream_tokens(prompt):
        yield token
```

See <https://docs.baseten.co/inference/streaming> for the client side.

## Async `predict`

`predict` may be `async def` for I/O-bound work (e.g. calling external services inside the request). Baseten's server awaits it appropriately. CPU- or GPU-bound model work should stay sync or offload via a thread pool.

## Binary output

Return `bytes` from `predict` to emit a binary response (e.g. an image, audio clip). Set headers via the `starlette` response helpers if you need specific `Content-Type`; see the examples repo for patterns.

## Accessing secrets and `data_dir`

- `self._secrets["name"]` pulls values for secrets declared in `config.yaml`.
- `self._data_dir` is a `pathlib.Path` to the bundled `data/` directory. Use it for tokenizers, small aux files, or anything baked into the image.

## Gotchas

- **Load weights in `load`, not `__init__`.** The server uses `load()` completion to gate readiness; weight loading in `__init__` delays startup without the benefit of the readiness gate.
- **`predict` runs per request.** Do not reload the model or re-open heavy resources inside it.
- **`predict_concurrency` and `num_workers`** live in `config.yaml` under `runtime`. If a sync `predict` does long blocking work, concurrency settings determine throughput; consult the docs when tuning.
- **Logs go to stdout/stderr.** Use ordinary `logging` or `print`; Baseten captures them.
- **Local packages live in `packages/`**, not in `requirements`. Add the directory to `external_package_dirs` in `config.yaml`.

## Further reading

- <https://docs.baseten.co/development/model> (custom model code, lifecycle, streaming, async)
- <https://docs.baseten.co/inference/streaming>
- Real examples: <https://github.com/basetenlabs/truss-examples>

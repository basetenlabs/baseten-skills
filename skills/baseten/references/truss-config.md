# `config.yaml`

`config.yaml` sits at the root of a Truss directory and describes how a model is built and served: its name, runtime,
hardware, packages, secrets, and (for non-Python flavors) the Docker or engine configuration that stands in for
`model.py`.

## Authoring flavor — pick before writing config

A `config.yaml` does not produce a working deployment on its own; it must be paired with one of three authoring flavors.
Pick by the model, not by habit — `model.py` is the worst default for modern LLMs.

| Flavor | When to pick | Reference |
| --- | --- | --- |
| **Python class** (`model.py` with `load` / `predict`) | Custom pre/post-processing, custom architecture, Python in the request path. | `truss-model-py.md` |
| **Custom Docker server** (`docker_server` block — vLLM, TGI, SGLang, Triton, Ollama, NIM) | An off-the-shelf inference server already does it. Most common path for modern LLMs. | `truss-custom-servers.md` |
| **Engine-only** (no code; `trt_llm` / BEI / BIS-LLM block in this file) | Standard architecture covered by a Baseten engine. Fastest path; no Python or Docker to maintain. | engines section below |

The authoritative schema is the Pydantic-backed JSON schema in the Truss repo:

- <https://github.com/basetenlabs/truss/blob/main/truss/config.schema.json>

Grep or read that file before guessing about an obscure field. The public reference page is
<https://docs.baseten.co/reference/truss-configuration>.

## A typical example

All fields in this example are optional at the schema level, but most real Trusses have at least these:

```yaml
model_name: my-model
python_version: py311
requirements:
  - transformers==4.44.0
  - torch==2.4.0
resources:
  accelerator: L4
  use_gpu: true
```

`model_name` is effectively required for a usable deployment (it identifies the model in the workspace).
`python_version` is strongly recommended - omitting it relies on whatever default the current Truss release ships.
`requirements`, `resources`, and other blocks are per-flavor and per-need, not universally required.

## Core fields

- `model_name` (str): display name in the Baseten workspace.
- `python_version` (str): one of `py39`, `py310`, `py311`, etc. Determines the base image's Python.
- `requirements` (list[str]): pip packages. Prefer pinned versions for reproducible builds.
- `requirements_file` (str): path to a `requirements.txt` instead of inline `requirements`. Use one or the other, not
  both.
- `system_packages` (list[str]): `apt-get` packages installed into the image (e.g. `ffmpeg`, `libsndfile1`).
- `environment_variables` (map[str, str]): env vars set in the container. Do not put secret values here.
- `external_package_dirs` (list[str]): local directories copied into the image and added to `PYTHONPATH`.
- `build_commands` (list[str]): shell commands run at image build time (before model load).
- `data_dir` / `external_data`: bundle static data with the model. `external_data` pulls from a URL at build time.

## `resources` block

Controls hardware. Two ways to specify, choose one:

```yaml
resources:
  cpu: "4"
  memory: "16Gi"
  accelerator: L4
  use_gpu: true
```

or

```yaml
resources:
  instance_type: "L4:4x16" # GPU:vCPUxMEMORY_GiB
```

If both are set, `instance_type` wins and overrides `cpu`, `memory`, `accelerator`.

Accelerator naming (exact strings the platform accepts):

- Single GPU: `L4`, `A10G`, `A100`, `H100`, `H200`, `B200`.
- Multi-GPU: append `:N`, for example `H100:2`, `A100:8`, `B200:4`.
- H100 / H200 `instance_type` strings use just `"H100:2"` (no vCPU/RAM suffix); other GPUs take `"L4:4x16"` style.

For the full current list of instance types, see <https://docs.baseten.co/deployment/resources> and the management API
instance-types endpoint.

## `secrets` block

Secrets in `config.yaml` are declared by **name**, not by value. The value is stored in the Baseten workspace and
injected into the container at runtime.

```yaml
secrets:
  hf_access_token: null # or a placeholder string, never the real token
  openai_api_key: null
```

In `model.py`, read them from the `secrets` dict passed to `__init__`. In a `docker_server` deployment, Baseten mounts
secret values to files under a configurable path (see `truss-custom-servers.md`). Never commit a real secret value to
`config.yaml`.

## `model_cache` (large weights)

Heavy models should download weights at **image build** time, not at model load, so replicas cold-start fast.

```yaml
model_cache:
  - repo_id: meta-llama/Llama-3.1-8B-Instruct
    revision: main
    allow_patterns:
      - "*.safetensors"
      - "tokenizer*"
      - "*.json"
```

The weights are baked into the image (or a layer) and available on disk when the container starts. Pair with a Hugging
Face access secret if the repo is gated.

## `docker_server` block (custom server flavor)

When `docker_server:` is set, Baseten runs a user-defined HTTP server (vLLM, TGI, SGLang, Triton, etc.) instead of the
Python Truss server. See `truss-custom-servers.md` for the full field list; in short you specify `start_command`,
`server_port`, `predict_endpoint`, `readiness_endpoint`, `liveness_endpoint`, `base_image`, and `run_as_user_id`.

## Engine-only deploys

Engine-only deployments skip `model.py` and skip a custom server: the engine runs the model directly from `config.yaml`.

- **TensorRT-LLM** via the `trt_llm` block. Fields include `max_batch_size`, `quantization_type`,
  `tensor_parallel_count`, `num_builder_gpus`. Tradeoffs and valid value ranges are not all documented centrally; read
  <https://docs.baseten.co/engines> and the schema file for the current surface.
- **Baseten Embedding Inference (BEI)**: embedding-model engine, OpenAI-compatible `/v1/embeddings` endpoint.
- **Baseten Inference Stack LLM (BIS-LLM)** and **Engine-Builder-LLM**: LLM engines, OpenAI-compatible
  `/v1/chat/completions` endpoint.

When to pick which engine, and the exact `config.yaml` shape for each, is covered on the docs site under `/engines`.
Confirm with the user which engine they want before generating config; do not guess.

## `runtime`, `build`, and advanced blocks

- `runtime`: predict concurrency, timeouts, streaming buffering settings.
- `build`: `model_server` selection (defaults to `TrussServer`), build-time options, secret-to-file mapping for
  `docker_server`.
- `live_reload`, `apply_library_patches`, `weights`, `training_checkpoints`: advanced features. Consult the schema or
  docs before using.

## Gotchas

- **Secrets are names, not values.** Never put a real token in `config.yaml`.
- **`instance_type` overrides `cpu`/`memory`/`accelerator`.** Setting both is confusing; pick one style.
- **`model_metadata.example_model_input` is publicly visible** on the deployment. Do not put credentials, PII, or
  internal data there.
- **`model_cache` downloads at build time, not load time.** If the user complains about slow cold starts, check whether
  weights are coming from disk or downloading at load.
- **Gated Hugging Face repos need a secret** (`hf_access_token` is the conventional name) **and** the secret must be
  configured in the workspace.
- **Pinned Python, pinned packages.** Unpinned `requirements` produce non-reproducible builds; mismatched
  `python_version` and a package's wheels lead to slow source builds or install failures.

## Further reading

- Config schema (authoritative): <https://github.com/basetenlabs/truss/blob/main/truss/config.schema.json>
- Docs reference: <https://docs.baseten.co/reference/truss-configuration>
- Resources and instance types: <https://docs.baseten.co/deployment/resources>
- Engines overview: <https://docs.baseten.co/engines>
- Real examples: <https://github.com/basetenlabs/truss-examples>

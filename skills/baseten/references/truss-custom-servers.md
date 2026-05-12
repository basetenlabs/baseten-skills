# Custom Docker server Truss

The custom-server flavor wraps a pre-built HTTP inference server (vLLM, TGI, SGLang, Triton, Ollama, NIM, anything that
listens on HTTP) instead of running Python in the request path. Pick it when an off-the-shelf server already does what
the user needs; it is often the most popular path for modern LLM deployments.

A custom-server Truss has no `model.py`. The `config.yaml` declares a `base_image` and a `docker_server` block; Truss
builds (or, with `no_build`, ships verbatim) and Baseten runs the resulting image.

## The `docker_server` block

```yaml
base_image:
  image: your-registry/your-image:latest
docker_server:
  start_command: your-server-start-command
  server_port: 8000
  predict_endpoint: /predict
  readiness_endpoint: /health
  liveness_endpoint: /health
```

Field meanings (from the published reference):

- `image` (under `base_image`): the Docker image to use.
- `start_command`: command to start the server. Overrides the base image's default entrypoint.
- `server_port`: the port your server listens on.
- `predict_endpoint`: the path inside your server that Baseten maps `/predict` to.
- `readiness_endpoint`: path Baseten polls to check the server is ready to serve traffic.
- `liveness_endpoint`: path Baseten polls to check the server is still alive.

Full field list (private registries, advanced options, etc.) lives at
<https://docs.baseten.co/reference/truss-configuration#docker_server>.

## Worked example: Ollama with TinyLlama

This example is the published custom-server walkthrough at <https://docs.baseten.co/development/model/custom-server>.
TinyLlama runs on CPU.

```yaml
model_name: ollama-tinyllama
base_image:
  image: python:3.11-slim
build_commands:
  - apt-get update && apt-get install -y curl ca-certificates zstd
  - curl -fsSL https://ollama.com/install.sh | sh
docker_server:
  start_command: sh -c "ollama serve & sleep 5 && ollama pull tinyllama && wait"
  readiness_endpoint: /api/tags
  liveness_endpoint: /api/tags
  predict_endpoint: /api/generate
  server_port: 11434
resources:
  cpu: "4"
  memory: 8Gi
```

Deploy with `truss push`; calls to `/predict` are forwarded to Ollama's `/api/generate`.

For ready-made server walkthroughs, see:

- vLLM: <https://docs.baseten.co/examples/vllm>
- SGLang: <https://docs.baseten.co/examples/sglang>
- TensorRT-LLM (also doable as engine-only): <https://docs.baseten.co/examples/tensorrt-llm>

## Endpoint mapping

`predict_endpoint` only handles the `/predict` route. To hit any other path on your server, use Baseten's sync endpoint:

| Baseten endpoint | Maps to |
| --- | --- |
| `/environments/production/predict` | Your `predict_endpoint` route |
| `/environments/production/sync/{any/route}` | `/{any/route}` in your server |

Example: with `predict_endpoint: /v1/chat/completions`, calling `/environments/production/sync/v1/models` reaches
`/v1/models` in your server. This makes it possible to expose OpenAI-compatible servers (which need both
`/v1/chat/completions` and `/v1/models`) cleanly.

## Non-root user (`run_as_user_id`)

Some base images expect a specific non-root UID (NVIDIA NIM and Triton run as `1000`).

```yaml
docker_server:
  start_command: ...
  server_port: 8000
  predict_endpoint: /predict
  readiness_endpoint: /health
  liveness_endpoint: /health
  run_as_user_id: 1000
```

The UID must already exist in the base image. Values `0` (root) and `60000` (Baseten's platform default) are not
allowed. Baseten sets ownership of `/app`, `/workspace`, the packages directory, and `$HOME` to the specified UID.
Anything else your server writes to must be made writable by that UID via the base image or `build_commands`.

## No-build deployment

For security-hardened images that must remain unmodified, set `no_build: true` to skip `docker build`. Baseten copies
the image to its registry as-is.

```yaml
base_image:
  image: your-registry/your-hardened-image:latest
docker_server:
  no_build: true
  server_port: 8000
  predict_endpoint: /predict
  readiness_endpoint: /health
  liveness_endpoint: /health
```

Constraints:

- Custom server only. `model.py`-based Trusses cannot use `no_build`.
- Not enabled by default for an organization; the user must contact Baseten support to turn it on.
- Development mode is not supported; deploy with plain `truss push`.
- Truss config fields beyond `docker_server`, `base_image`, `environment_variables`, `secrets`, and `data` are not
  injected. Pass other configuration as environment variables.
- `start_command` is optional; if omitted, the image's original `ENTRYPOINT` runs.
- Path remapping is skipped: `predict_endpoint` is required but has no effect, and all server paths are reachable via
  `/environments/production/sync/<path>`.

## Secrets

Secrets declared in `config.yaml` are available to custom servers; the mount path is configurable. See
<https://docs.baseten.co/development/model/secrets#custom-docker-images> for the exact mechanism (environment-variable
vs file-mounted depending on configuration).

## Per-request logging

Baseten assigns a unique request ID per call and returns it in the `X-Baseten-Request-Id` response header. Standard
Python Trusses log this automatically; **custom servers must extract it from the incoming `X-Baseten-Request-Id` request
header and include it as a top-level `request_id` field in JSON-formatted logs written to stdout**. Without that,
per-request log filtering does not work. FastAPI and Flask snippets are at
<https://docs.baseten.co/development/model/custom-server#per-request-logging>.

## Gotchas

- **Port 8080 is reserved** by Baseten's internal reverse proxy. A server bound to 8080 fails with
  `[Errno 98] address already in use`. Choose any other port.
- **`run_as_user_id` cannot be `0` or `60000`.** Match what the base image actually uses.
- **No-build needs to be enabled** by support before it works for the organization.
- **Custom servers do not get automatic per-request log correlation.** If users need it, they must format logs as JSON
  with a `request_id` key.
- **`predict_endpoint` is required even when no-build skips remapping.** Treat it as documentation of your primary
  inference route.

## Further reading

- Custom Docker images: <https://docs.baseten.co/development/model/custom-server>
- Config reference (`docker_server`, `base_image`, `no_build`): <https://docs.baseten.co/reference/truss-configuration>
- Private registries: <https://docs.baseten.co/development/model/private-registries>
- Calling deployed models (sync/async/streaming): <https://docs.baseten.co/inference/calling-your-model>
- Examples: <https://github.com/basetenlabs/truss-examples>

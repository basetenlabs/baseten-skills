---
name: baseten
description: Use this skill for anything involving Baseten or Truss, such as deploying a custom model, writing or debugging a `config.yaml`, choosing between a Python `model.py`, a custom Docker server (vLLM/TGI/SGLang/Triton), or an engine-only deploy (TensorRT-LLM, BEI, BIS-LLM), running `truss push` or `truss watch`, working with Chains, managing environments and rolling deployments, calling pre-hosted Baseten Model APIs, or calling custom deployments via the inference API or managing them via the management API.
---

# Baseten

Baseten is a platform for serving machine learning models. Two broad paths exist:

- **Model APIs** - pre-hosted, ready-to-call models (chat, embeddings, etc.) accessed over HTTP. No deployment step. Good when a hosted model already does what the user needs.
- **Custom deployments via Truss** - package and deploy a user-supplied model. A Truss is a directory containing a `config.yaml` plus optionally model code, a custom server image, or an engine config. Built and deployed with the `truss` CLI; operated via the management API; called via the inference API.

This skill is the entry point for any Baseten work. Read this body fully, then load only the references relevant to the task.

## Mental model for custom deployments

A deployed Truss has three pieces a user works with:

1. **The Truss** (source): a directory you author.
2. **The deployment** (running): a containerized instance attached to an environment such as `development` or `production`.
3. **The endpoint** (call site): the URL clients hit, e.g. `https://model-{id}.api.baseten.co/environments/production/predict`.

Almost every custom-deployment task touches one or more.

## Three ways to author a Truss

Pick the simplest one that fits.

| Flavor | When to pick | Reference |
|---|---|---|
| **Python class** (`model.py` with `load`/`predict`) | Custom pre/post-processing, custom architectures, anything needing Python in the request path. | `references/truss-model-py.md` |
| **Custom server** (`docker_server` block, BYO HTTP server such as vLLM, TGI, SGLang, Triton) | An existing inference server already does the job. Often the most popular path for modern LLMs. | `references/truss-custom-servers.md` |
| **Engine-only** (no code; engine config in `config.yaml`, e.g. TensorRT-LLM, BEI, BIS-LLM) | Standard architecture covered by a Baseten-supported engine. Fastest path; no Python or Docker to maintain. | `references/truss-config.md` (engines section) |

If unsure which flavor fits, ask. Don't default to Python class out of habit; custom servers and engines are often better choices.

## Decision routing

Match the task to the reference(s) to load. **Only load what you need.**

| Task | Load |
|---|---|
| Calling a pre-hosted Model API | `references/model-apis.md` |
| Writing or editing `config.yaml` | `references/truss-config.md` |
| Writing the Python `Model` class | `references/truss-model-py.md` |
| Configuring a custom Docker server | `references/truss-custom-servers.md` |
| Running `truss push`, `truss watch`, `truss init` | `references/truss-cli.md` |
| Building a multi-step inference pipeline | `references/truss-chains.md` |
| Understanding environments, promotion, rolling deploys, autoscaling | `references/deployment-lifecycle.md` |
| Listing/promoting/deleting deployments programmatically | `references/management-api.md` |
| Calling a custom-deployed model (sync, streaming, async, OpenAI-compat) | `references/inference-api.md` |

## Installing the truss CLI

Preferred:

```
uv tool install truss     # installs the CLI as a uv-managed tool
# or
uvx truss <command>       # run without installing
```

`pip install truss` also works in a regular Python environment. Authentication and first-push setup are covered in `references/truss-cli.md`.

## Getting started (custom deployment)

End-to-end shape of a first Truss deployment. Each step has a deeper reference.

1. **Scaffold**: `truss init my-model` creates a directory with a starter `config.yaml` and `model.py`. See `references/truss-cli.md`.
2. **Choose a flavor** and edit accordingly: keep the generated `model.py` (Python class), replace it with a `docker_server` block (custom server), or use an engine block (engine-only). See the three-flavors table above.
3. **Edit `config.yaml`**: set `model_name`, `python_version`, `resources`, `requirements`, and any secrets. See `references/truss-config.md`.
4. **Push**: `truss push` for a published deployment, or `truss push --watch` for an iterative development deployment that live-reloads. See `references/truss-cli.md`.
5. **Call**: hit the model's inference endpoint (use curl, `requests`, the OpenAI SDK pointed at a Baseten base URL, etc.). See `references/inference-api.md`.

### Minimal Python Truss example

A complete Python-class Truss is just two files. This example deploys [Phi-3-mini-4k-instruct](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct) on a T4 GPU; it is the published walkthrough at <https://docs.baseten.co/examples/customize-a-model>.

`model/model.py`:

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


class Model:
    def __init__(self, **kwargs):
        self._model = None
        self._tokenizer = None

    def load(self):
        self._model = AutoModelForCausalLM.from_pretrained(
            "microsoft/Phi-3-mini-4k-instruct",
            device_map="cuda",
            torch_dtype="auto",
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            "microsoft/Phi-3-mini-4k-instruct"
        )

    def predict(self, request):
        messages = request.pop("messages")
        model_inputs = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(model_inputs, return_tensors="pt").to("cuda")
        with torch.no_grad():
            outputs = self._model.generate(input_ids=inputs["input_ids"], max_length=256)
        return {"output": self._tokenizer.decode(outputs[0], skip_special_tokens=True)}
```

`config.yaml`:

```yaml
python_version: py311
requirements:
  - six==1.17.0
  - accelerate==0.30.1
  - einops==0.8.0
  - transformers==4.41.2
  - torch==2.3.0
resources:
  accelerator: T4
  use_gpu: true
```

Deploy and call: `uvx truss push --watch`, then POST to `https://model-{id}.api.baseten.co/development/predict` with an `Authorization: Api-Key $BASETEN_API_KEY` header.

## Out of scope for this skill

- **Advanced Python authoring patterns** (sophisticated streaming, custom batching, performance tuning of the in-process Python server, fine-grained Truss internals). May be covered by a future, more specialized skill. For now, stick to the contract documented in `references/truss-model-py.md` and refer the user to `docs.baseten.co` for deeper material.
- **Model training on Baseten** (Truss-Train). Out of scope here; mention that a separate path exists if asked.
- **Web UI navigation.** Defer to docs.baseten.co.
- Generic Docker / FastAPI / vLLM questions where the user is not deploying to Baseten.

## External resources

When references in this skill don't cover something, consult these before guessing. Per-resource references (e.g. for OpenAPI specs, config schema) live in the relevant reference files.

- **Baseten docs**: <https://docs.baseten.co> - authoritative for product behavior.
- **Truss source and issues**: <https://github.com/basetenlabs/truss>.
- **Truss examples**: <https://github.com/basetenlabs/truss-examples> - real `config.yaml` and `model.py` files for many model families.

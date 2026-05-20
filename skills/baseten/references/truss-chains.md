# Baseten Chains

Chains is the framework for orchestrating multi-step inference pipelines on Baseten where each step has different
hardware, dependency, or scaling needs. Pick Chains when a single monolithic Truss does not fit: RAG, multi-model
pipelines (e.g. LLM then TTS then transcription), audio or video chunking and reassembly, image generation with safety
or upscaling steps, retrieval into an LLM.

Each step in a Chain is a **Chainlet**: a Python class that deploys independently on its own hardware with its own
autoscaling policy. One Chainlet is marked as the **entrypoint** and handles the Chain's public HTTP surface.

**Prerequisites:** `truss-config.md` (each Chainlet's `RemoteConfig` mirrors `config.yaml`); `deployment-lifecycle.md`
(dev vs published, per-chainlet autoscaling, environments). For iteration: `truss-cli.md` + `model-dev-loop.md`.

Reference docs live at <https://docs.baseten.co/development/chain/overview> and the CLI reference at
<https://docs.baseten.co/reference/cli/chains/chains-cli>. For deeper patterns (streaming, binary I/O, error handling,
subclassing), defer to the docs.

## Minimal example

The "hello world" Chain from <https://docs.baseten.co/development/chain/getting-started>:

```python
import random
import truss_chains as chains


class RandInt(chains.ChainletBase):
    async def run_remote(self, max_value: int) -> int:
        return random.randint(1, max_value)


@chains.mark_entrypoint
class HelloWorld(chains.ChainletBase):
    def __init__(self, rand_int=chains.depends(RandInt, retries=3)) -> None:
        self._rand_int = rand_int

    async def run_remote(self, max_value: int) -> str:
        num_repetitions = await self._rand_int.run_remote(max_value)
        return "Hello World! " * num_repetitions
```

Deploy:

```
truss chains push --watch hello.py
```

Call (URL is printed by `push`):

```
curl -X POST $INVOCATION_URL \
  -H "Authorization: Api-Key $BASETEN_API_KEY" \
  -d '{"max_value": 10}'
```

## The Chainlet contract

- Subclass `truss_chains.ChainletBase`.
- Expose exactly one public method, `run_remote`. It is the Chainlet's API.
- `run_remote` must be **fully type-annotated** with primitive Python types (`int`, `str`, `list[float]`, ...) or
  Pydantic models. Annotations drive serialization across Chainlets and into the public API.
- Mark exactly one Chainlet with `@chains.mark_entrypoint`. That Chainlet's `run_remote` is the Chain's public HTTP
  endpoint.
- Chainlets cannot be instantiated naively (`RandInt()`). The only valid ways to use another Chainlet are:
  - declare it as an `__init__` argument via `chains.depends(OtherChainlet, retries=...)`, or
  - drive it through local debugging mode (<https://docs.baseten.co/development/chain/localdev>).
- Beyond `run_remote`, you can structure the class however you like: private methods, imports from other files, Pydantic
  models, etc.

## Per-Chainlet resources

Each Chainlet declares its own hardware and dependencies via `remote_config`:

```python
class PhiLLM(chains.ChainletBase):
    remote_config = chains.RemoteConfig(
        docker_image=chains.DockerImage(
            pip_requirements=[
                "accelerate==0.30.1",
                "transformers==4.41.2",
                "torch==2.3.0",
            ],
        ),
        compute=chains.Compute(cpu_count=2, gpu="T4"),
        assets=chains.Assets(cached=[model_repo]),
    )
```

`compute`, `docker_image`, and `assets` are the common knobs; `assets.cached` bakes model weights into the image at
build time, same idea as the `model_cache` block in a classic Truss `config.yaml`. The full API surface is at
<https://docs.baseten.co/reference/sdk/chains>.

## What Chains gives you (beyond DIY orchestration)

Most of these you'd have to build (poorly) if you wired N Trusses together with `httpx` by hand.

- **Typed IO between Chainlets** — `run_remote` signatures use Pydantic / primitives; mismatches fail at deploy/import
  time, not at first call in prod. Full IDE autocomplete on dependency calls.
- **Generated client stubs (`BasetenSession`)** — created from your `chains.depends()` graph. You get rate limiting,
  HTTP connection reuse + periodic rotation, retries, structured stack-trace propagation from a failing inner Chainlet
  back to the caller (not "500 Internal Server Error" from a black box), and exported per-edge metrics — all without
  writing the glue.
- **Binary IO helpers** — Chains can serialize numpy arrays as raw binary instead of base64'd JSON. Saves the ~33%
  base64 overhead on every payload edge (and that's before counting JSON's number-encoding bloat). See
  <https://docs.baseten.co/development/chain/binaryio>.
- **Structured streaming** — helpers for end-to-end typed streams (`AsyncIterator[Model]`) across Chainlets, not just
  at the entrypoint. See <https://docs.baseten.co/development/chain/streaming>.
- **Local testability** — `chains.run_local()` runs the whole graph in your process with mocked or real downstream
  Chainlets; you can swap any node for a stub or point it at a separately-deployed test deployment, and exercise the
  orchestration logic without paying GPU costs. See
  <https://docs.baseten.co/development/chain/localdev>.
- **Selective watch** — `truss chains push --watch --experimental-watch-chainlets <A>,<B>` patches only the named
  Chainlets, skipping `load()` on heavy siblings. Cuts inner-loop wall time when one Chainlet has slow startup.
- **Per-Chainlet independence** — autoscaling, instance type, deps, and image rebuild scope are each per-Chainlet, so
  one slow node doesn't gate the rest.

Broader context: <https://www.baseten.co/blog/baseten-chains-explained/>.

## Heavy-dependency imports

Imports of Chainlet-specific packages (e.g. `torch`, `transformers`) commonly live **inside** `__init__` or `run_remote`
rather than at module top, because those packages are only available in the remote Chainlet image, not in the local dev
environment.

```python
def __init__(self) -> None:
    import torch
    import transformers
    ...
```

This is a local exception to the general rule of keeping imports at module top: the constraint is that top-level imports
run in the local dev shell, which need not have GPU libraries installed.

## Deploy

```
truss chains push [--watch] <chain.py>
```

`--watch` gives a development deployment with live reload. `truss chains push` without `--watch` deploys a published
Chain; see <https://docs.baseten.co/reference/cli/chains/chains-cli> for environment/promotion flags. The output lists
each Chainlet's status and log URL, plus the invocation URL for the entrypoint.

## Calling a deployed Chain

The entrypoint's `run_remote` is exposed at a URL of the shape:

```
https://chain-{chain_id}.api.baseten.co/.../run_remote
```

Use standard HTTP with an `Authorization: Api-Key $BASETEN_API_KEY` header. Body is the JSON-encoded arguments to
`run_remote`.

For streaming, binary I/O, and websockets, see:

- <https://docs.baseten.co/development/chain/streaming>
- <https://docs.baseten.co/development/chain/binaryio>

## Gotchas

- **Rolling deployments are not supported for Chains.** Plan promotions accordingly; there is no gradual traffic shift
  between versions.
- **Chainlets cannot be instantiated directly.** Always use `chains.depends()` in `__init__` arguments, or the
  documented local debugging path.
- **Full type annotations on `run_remote` are required** for serialization. Un-annotated parameters will not work.
- **Avoid module-level global state and dynamic imports in Chainlet code.** Chainlets are distributed and replicated;
  globals do not behave the way you might expect.
- **Per-Chainlet autoscaling is independent.** A slow downstream Chainlet can become the bottleneck; tune its
  `autoscaling` separately from the entrypoint.
- **Local imports of heavy dependencies** (`torch`, `transformers`, etc.) inside `__init__` or `run_remote` are
  idiomatic for Chains even though they contradict the general "imports at top" rule - those libs live in the remote
  image, not the local dev shell.
- **A Chainlet hosts a real workload, not an HTTP wrapper.** If `run_remote` is essentially
  `await httpx.post(other_endpoint)`, collapse it into the caller — you're paying for a container + autoscaler +
  cold-start budget to do zero work. Split into Chainlets only where hardware, dependencies, or scaling actually
  differ.
- **Batching vs unit-of-work is a tradeoff, not a default.** Calling `run_remote(items: list[T]) -> list[U]` once
  beats N parallel calls **only when** the underlying model framework batches natively (e.g. diffusers, vLLM) **and**
  replica count is small. With many autoscaling replicas at low `predict_concurrency`, small unit-of-work calls
  spread across replicas often win. Measure both; don't assume.

## Further reading

- Chains overview: <https://docs.baseten.co/development/chain/overview>
- Getting started (Hello World + Poetry examples): <https://docs.baseten.co/development/chain/getting-started>
- Concepts and `run_remote` chaining: <https://docs.baseten.co/development/chain/concepts>
- SDK reference (`ChainletBase`, `depends`, `RemoteConfig`, `Compute`, `Assets`):
  <https://docs.baseten.co/reference/sdk/chains>
- CLI reference: <https://docs.baseten.co/reference/cli/chains/chains-cli>
- Local development: <https://docs.baseten.co/development/chain/localdev>
- Example Chains (audio transcription, RAG): <https://docs.baseten.co/examples/chains-audio-transcription> and
  <https://docs.baseten.co/examples/chains-build-rag>
- Blog (design rationale): <https://www.baseten.co/blog/baseten-chains-explained/>

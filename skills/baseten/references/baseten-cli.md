# Baseten CLI

Use `baseten` to deploy and operate models: model push (including the live-patch development loop), deployment promotion
and lifecycle, environments, autoscaling schedules, replicas, Model APIs, training jobs, and Loops runs. It is the
default for any deploy or operate task — reach for `truss` only to author Chains, Training jobs, and Loops, which the
CLI does not cover natively (see `truss-cli.md`).

## Setup

Check `baseten version`. On macOS or Linux, install with Homebrew:

```sh
brew tap basetenlabs/baseten
brew install baseten
```

For other platforms, use the release archives linked from <https://docs.baseten.co/reference/cli/baseten/overview>.

Authenticate interactively with `baseten auth login --web`. In CI, use `BASETEN_API_KEY` from the environment. Use
`--profile` to select a saved profile when needed; verify the target before changing workspace state.

## Push a model

`baseten model push` packages the model directory (the `config.yaml` plus `model/` and `packages/`) and deploys it. It
creates a **published** deployment by default.

```sh
baseten model push                                  # published deployment
baseten model push --wait --tail                     # block until active, stream logs
baseten model push --dry-run                         # validate + request upload credentials, deploy nothing
baseten model push --develop                         # overwrite the model's dev deployment
baseten model push --environment staging --wait      # push straight to an environment
```

There is no `--promote` flag on push. Publish, then promote as a second step:

```sh
baseten model push --wait
baseten model deployment promote --model-id <model_id> --deployment-id <deployment_id>
```

Flags worth knowing:

- `--dir <path>`: model directory (defaults to the current directory). Use it instead of changing directories.
- `--deployment-name <name>`: human-readable deployment name.
- `--override-name <name>`: push under a different `model_name` without editing `config.yaml`.
- `--create-environment-if-missing`: required when `--environment` names an environment the model doesn't have yet.
- `--preserve-env-instance-type`: keep the target environment's instance type instead of `config.yaml`'s.
- `--deploy-timeout 30m`: raise the build timeout (range 10m to 24h).
- `--labels '{"team":"ml"}'`: attach searchable key/value labels.
- `--team <name>`: target team, only valid when creating a new model. Always pass it from automation.
- `--wait` exits non-zero on a terminal failure, so a CI step fails with the deploy.

## Live iteration

`baseten model push --watch` creates a development deployment, waits for it to become ready, then watches the project
directory and live-patches it on every save. The process does not return — run it in the background and read its log.

```sh
baseten model push --watch                       # start the dev loop
baseten model push --watch --watch-hot-reload    # swap model code in-process, keep loaded weights
baseten model watch                              # re-attach to an existing dev deployment
baseten model watch --hot-reload
```

- Keep-warm is on by default (periodic pings prevent scale-to-zero). Pass `--watch-no-keepalive` on push, or
  `--no-keepalive` on watch, to let the dev deployment scale to zero.
- Hot reload re-imports the module and swaps the class in place. It does **not** re-run `__init__()` or `load()`; if new
  instance state lives there, do a full reload instead.
- Changes to `resources`, `python_version`, `system_packages`, or `live_reload` require a full `baseten model push`.

Note the flag names differ from truss: the truss equivalents are `--watch-no-sleep` (push) and `--no-sleep` (watch).

## Operate

```sh
baseten model deployment list --model-id <model_id>
baseten model deployment logs --model-id <model_id> --deployment-id <id> --tail
baseten model deployment promote --model-id <model_id> --deployment-id <id>
baseten model deployment update-autoscaling --model-id <model_id> --environment production
baseten model environment autoscaling-schedule --help
baseten model deployment replica terminate --model-id <model_id> --deployment-id <id>
baseten model predict --model-id <model_id> --data '{"x":1}'
```

Read the resource's help before scripting a mutation. Autoscaling schedules accept daily, hourly, or one-time windows
with a shared timezone; outside those windows the environment's default settings apply.

## Discover and script

```sh
baseten --help
baseten model push --help-output
baseten model list --output json
baseten model list --jq '.models[].id'
```

`--help-output` documents the command's output shape and exit codes. `--jq` implies JSON output. Native commands also
support `--output jsonl` for streaming records and `--output none` to suppress stdout. These flags apply to
Baseten-native commands; inspect delegated Truss command help separately.

## Hosted inference

```sh
baseten model-api list
baseten model-api describe --model zai-org/GLM-5.2
baseten model-api predict --model zai-org/GLM-5.2 --content "What is gradient descent?"
```

Discover an available slug before calling it. See `model-apis.md` for SDK integrations and authentication differences.

## Truss interop

`baseten truss` runs truss through `uv tool run` and forwards this CLI's credentials, so `baseten truss chains push`
works without a separate `truss login`. Truss commands that import your own Python code need `--truss-executable`
pointed at a truss installed in the project, because `uv tool run` uses an isolated environment that cannot see your
dependencies.

`baseten train` and `baseten loops` manage training and Loops natively, and delegate to truss for the commands that need
a Python config file (`train push`, `train init`, `loops checkpoint deploy`).

## Training and Loops

`baseten train` manages training projects and jobs; `baseten loops` manages Loops runs and checkpoints. Inspect each
command's help. For choosing between managed Loops training and a custom container, read
<https://docs.baseten.co/training/index>. For SDK code, use the current Loops quickstart and supported-models docs
instead of copying inference-model slugs into a trainer configuration.

For Loops SDK work, install `baseten-loops` and import from `baseten.loops`. Creating a training client provisions GPUs;
the paired sampler is provisioned when first requested. A running `TrainingClient` keeps the session warm. Close it when
finished and explicitly deactivate the run with `baseten loops run deactivate --run-id <run_id> --yes` when the user
wants to end the session. Deactivation shuts down trainer and sampler; saved checkpoints survive. See
<https://docs.baseten.co/loops/quickstart>.

Sources:

- <https://docs.baseten.co/reference/cli/baseten/overview>
- <https://docs.baseten.co/reference/cli/baseten/model>
- <https://docs.baseten.co/reference/cli/baseten/model-api>
- <https://docs.baseten.co/reference/cli/baseten/truss>
- <https://docs.baseten.co/reference/cli/index>

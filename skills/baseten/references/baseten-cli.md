# Baseten CLI

Use `baseten` to deploy and operate models: model push (including the live-patch development loop), deployment promotion
and lifecycle, environments, autoscaling schedules, replicas, Model APIs, training jobs, and Loops runs. It is the
default for everything at Baseten except Chains — reach for `truss` only to author a Chain, and even then you can run it
as `baseten truss chains …` (see `truss-cli.md`).

It is built for agents. Every Baseten-native command takes `--output json` (or `jsonl`, or `none`), `--jq` implies JSON
output, and `--help-output` prints the command's JSON schema and exit codes. Anything without a first-class command is
reachable through `baseten api management <path>`.

## Setup

Check `baseten version`. On macOS or Linux, install with Homebrew:

```sh
brew tap basetenlabs/baseten
brew install baseten
```

For other platforms, use the release archives linked from <https://docs.baseten.co/reference/cli/baseten/overview>.

## Auth

`baseten auth` manages credentials, stored as named profiles.

```sh
baseten auth login                 # interactive browser login (OAuth device flow)
baseten auth login --web           # same browser flow without interactive prompts
baseten auth login --with-api-key  # read an API key from stdin
baseten auth status                # print the current user and workspace
baseten auth switch                # change the active profile
baseten auth logout
```

In CI, pass `BASETEN_API_KEY` in the environment instead of logging in. Use `--profile <name>` on any command to target
a workspace without switching the default profile, and verify the target before changing workspace state. A profile
binds to one workspace; `login --remote-url` points it at a non-default Baseten remote.

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
- Changes to `resources`, `python_version`, or `live_reload` require a full `baseten model push`. Everything else,
  including `system_packages` and `requirements`, rides as a patch. See [the cost tiers](model-dev-loop.md).

Note the flag names differ from truss: the truss equivalents are `--watch-no-sleep` (push) and `--no-sleep` (watch).

## Operate

```sh
baseten model deployment list --model-id <model_id>
baseten model deployment logs --model-id <model_id> --deployment-id <id> --tail
baseten model deployment promote --model-id <model_id> --deployment-id <id>
baseten model deployment update-autoscaling --model-id <model_id> --deployment-id <id>
baseten model environment autoscaling-schedule --help
baseten model deployment replica terminate --model-id <model_id> --deployment-id <id>
baseten model predict --model-id <model_id> --data '{"x":1}'
```

Read the resource's help before scripting a mutation. Autoscaling schedules accept daily, hourly, or one-time windows
with a shared timezone; outside those windows the environment's default settings apply.

## Discover and script

```sh
baseten --help
baseten model push --help-output                                       # JSON schema + exit codes
baseten model list --output json
baseten model list --jq '.models[].id'                                 # --jq implies JSON output
baseten model deployment logs --model-id <id> --deployment-id <id> --tail --output jsonl --jq '.message'
```

`--help-output` documents the command's output shape and exit codes. `--jq` implies JSON output. Native commands also
support `--output jsonl` for streaming records and `--output none` to suppress stdout. These flags apply to
Baseten-native commands; inspect delegated Truss command help separately.

`baseten api` reaches the Management and inference APIs directly, for anything without a first-class command. Paths are
relative to `/v1/`:

```sh
baseten api management models                          # GET /v1/models
baseten api management models --field name=my-model    # POST a field
baseten api management models --jq '.models[].id'
baseten api inference --model-id <id> --data '{"x":1}'
```

The method defaults to GET, or POST when `--field`, `--raw-field`, or `--input` is given. The Management API OpenAPI
spec is at <https://api.baseten.co/v1/spec>.

## Org and workspace

```sh
baseten org describe                                          # organization details
baseten org regions                                           # region slugs for --region
baseten org api-key list
baseten org api-key create --type workspace-invoke --name ci
baseten org secret set --name hf_access_token                 # value comes from stdin or a prompt
baseten org billing usage --since 7d
baseten org team list                                         # also: org user list
baseten org audit-logs --since 7d --event-type-group deployed
```

`org secret` stores the secrets `config.yaml` references, so it is usually the step before a first deploy. Avoid
`org secret set --value`, which leaks into shell history; pass the value on stdin instead. `org audit-logs` records
deploys, promotions, and API-key, secret, and autoscaling changes.

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

The same lifecycle is available without the CLI: the Loops Management API at `api.baseten.co/v1/loops` (sessions, runs,
checkpoints, checkpoint files, `POST /v1/loops/checkpoints/deploy`) and the `baseten` MCP Loops tools (create session
and run, list runs, list checkpoints and files, deploy, deactivate). Only sampler-target checkpoints deploy;
trainer-target checkpoints hold training state. Deploys are billable and not idempotent: repeating the same request
creates another deployment, so confirm before calling and never retry blindly. The management API reference is at
<https://docs.baseten.co/reference/loops-api>.

The SDK client process orchestrates a run, so it needs sustained outbound connectivity to Baseten. For unattended work,
host it with `truss loops exec`, which packages the current directory and starts the client as a Training Job. See
<https://docs.baseten.co/loops/concepts#run-the-client>.

Sources:

- <https://docs.baseten.co/reference/cli/baseten/overview>
- <https://docs.baseten.co/reference/cli/baseten/model>
- <https://docs.baseten.co/reference/cli/baseten/model-api>
- <https://docs.baseten.co/reference/cli/baseten/truss>
- <https://docs.baseten.co/reference/cli/index>

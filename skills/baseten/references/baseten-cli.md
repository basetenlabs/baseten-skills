# Baseten CLI

Use `baseten` for workspace management, model deployment, hosted Model APIs, training jobs, and Loops runs. It is beta;
discover the installed command and output schema before writing automation. Keep using `truss` for Chains authoring and
Python configuration workflows. Some `baseten train` and `baseten loops` commands delegate to Truss.

## Setup

Check `baseten version`. On macOS or Linux, install with Homebrew:

```sh
brew tap basetenlabs/baseten
brew install baseten
```

For other platforms, use the release archives linked from <https://docs.baseten.co/reference/cli/baseten/overview>.

Authenticate interactively with `baseten auth login --web`. In CI, use `BASETEN_API_KEY` from the environment. Use
`--profile` to select a saved profile when needed; verify the target before changing workspace state.

## Discover and script

```sh
baseten --help
baseten model --help
baseten model list --help-output
baseten model list --output json
baseten model list --jq '.models[].id'
```

`--help-output` documents the command's output shape and exit codes. `--jq` implies JSON output. Native commands also
support `--output jsonl` for streaming records and `--output none` to suppress stdout. These flags apply to
Baseten-native commands; inspect delegated Truss command help separately.

Read the resource's help for model push, environment promotion, autoscaling, logs, replicas, and raw API calls. For
native model pushes, start with `baseten model push --help`; for existing Truss workflows see `truss-cli.md`.

## Hosted inference

```sh
baseten model-api list
baseten model-api describe --model zai-org/GLM-5.2
baseten model-api predict --model zai-org/GLM-5.2 --content "What is gradient descent?"
```

Discover an available slug before calling it. See `model-apis.md` for SDK integrations and authentication differences.

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
- <https://docs.baseten.co/reference/cli/baseten/model-api>
- <https://docs.baseten.co/reference/cli/index>

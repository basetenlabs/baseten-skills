# Loops operations

Use this reference for Loops lifecycle operations, checkpoint deployment, running SDK clients unattended, and capacity
refusals. For training code, start from the [Loops quickstart](https://docs.baseten.co/loops/quickstart), the
[Loops cookbook](https://github.com/basetenlabs/loops-cookbook/tree/main), and the
[SDK reference](https://docs.baseten.co/reference/sdk/loops/overview). Select a model from
[supported models](https://docs.baseten.co/loops/supported-models), not the inference model catalog.

## Modes, billing, and capacity

A run uses the serverless mode by default when the model, LoRA rank, and sequence length support it, and the dedicated
mode otherwise. Set `scope` to `serverless` to refuse a run that serverless can't take, or `deployment` to reserve a
trainer and sampler for the run. See [availability modes](https://docs.baseten.co/loops/availability-modes/overview).
Serverless bills for tokens trained and sampled; dedicated bills for GPU time, including replicas and spot capacity.

Creating a run or a standalone sampler waits for capacity. While Baseten's shared capacity is fully committed, Loops
returns a `429` and the SDK retries for a few minutes before raising `LoopsCapacityError`. A `details.limit` of
`org_cap` means the organization hit its own concurrency limit instead, so retrying doesn't help. Resolve it by
retrying, [requesting more access](https://www.baseten.co/talk-to-us/loops-signup/), or moving the run to the dedicated
mode. See [capacity and quota errors](https://docs.baseten.co/troubleshooting/loops#resolve-capacity-and-quota-errors).

## Availability and authentication

Before recommending an operation, inspect the connected MCP server's tools and input schemas, the hosted API reference,
or `baseten loops --help`. An operation described here is not proof that the connected server or installed CLI supports
it. If it is absent, report that limitation. Use the REST fallback only when that endpoint is documented and deployed.

The backend MCP supports browser-based OAuth sign-in; logging in with the CLI does not sign in to the MCP server.
Headless clients can authenticate with a management API key. REST requests use `Authorization: Bearer <API_KEY>` against
`https://api.baseten.co`. These tools manage platform resources; they do not host or expose the Forge agent workflow.

## MCP tools and REST equivalents

The tool names below are backend names; a client may add a server-name prefix. Use the discovered input schema, not the
REST body verbatim: MCP request objects can be nested under names such as `create_loops_run_request_v1` and
`deploy_loops_checkpoint_request_v1`.

| MCP tool | REST operation | Inputs |
| --- | --- | --- |
| `create_loops_session` | `POST /v1/loops/sessions` or `POST /v1/teams/{team_id}/loops/sessions` | Optional `team_id` selects the team used for authorization, not the session's project team. Omission checks the default team. |
| `list_loops_runs` | `GET /v1/loops/runs` | Optional query filters from the API reference. |
| `get_loops_run` | `GET /v1/loops/runs/{run_id}` | Run ID. |
| `create_loops_run` | `POST /v1/loops/runs` | JSON with `session_id` and `base_model`; creates the run in the default team. |
| `create_team_loops_run` | `POST /v1/teams/{team_id}/loops/runs` | Team ID in the path; the same run body. |
| `deactivate_loops_run` | `POST /v1/loops/runs/{run_id}/deactivate` | Run ID; stops the run and its paired sampler. |
| `list_loops_checkpoints` | `GET /v1/loops/checkpoints` | Exactly one query filter: `run_id`, `base_model`, or `checkpoint_path`. |
| `list_loops_checkpoint_files` | `GET /v1/loops/checkpoints/{checkpoint_id}/files` | Checkpoint ID; optional `page_size` and `page_token`. |
| `deploy_loops_checkpoint` | `POST /v1/loops/checkpoints/deploy` | JSON with `checkpoint_ids`, `model_name`, `instance_type_id`, and `hf_secret_name`. |

Confirm the user's intent before creating billable training, sampling, or deployment resources, and before stopping a
run. Creating an SDK training client provisions GPUs; the SDK provisions the paired sampler when first requested. A
running `TrainingClient` keeps the session warm. Close the client when finished, and explicitly deactivate the run when
the user wants to stop its resources. Saved checkpoints survive run deactivation.

## CLI surface

`baseten loops run create|list|describe|logs|deactivate` covers run lifecycle,
`baseten loops checkpoint list|files|deploy` covers checkpoints and their deployment, `baseten loops usage` reports GPU
allocations, and `baseten loops exec` runs a client as a managed Training Job. Check `baseten loops --help` for the
installed surface.

## Interactive checkpoint deployment

Prefer the Baseten CLI for interactive checkpoint deployment. Check `baseten loops checkpoint deploy --help` for
installed support. Preview the generated GPU and serving config before creating a deployment:

```sh
baseten loops checkpoint deploy --checkpoint-id <SAMPLER_CHECKPOINT_ID> --dry-run
```

The command prompts for deployment settings and prints the generated Truss config without creating a deployment. Review
it, then rerun without `--dry-run` after the user confirms deployment. To customize the generated config, save the
printed YAML as `config.yaml` in a Truss directory and edit it. After confirmation, deploy with
`baseten --profile <PROFILE> model push --dir <DIRECTORY> --team <CHECKPOINT_TEAM>`. Keep the preview's profile and the
checkpoint's team. The generated config doesn't store the team; omitting `--team` selects the organization's default
team and can cause a checkpoint/team mismatch. The Hugging Face secret must be available in that team. The CLI delegates
to Truss; it is not a wrapper for the REST endpoint below. For explicitly requested API or MCP automation, use the
available operation and its discovered schema instead.

## REST fallback

List checkpoints for a known run:

```sh
curl --fail-with-body --get \
  'https://api.baseten.co/v1/loops/checkpoints' \
  --header "Authorization: Bearer ${BASETEN_API_KEY}" \
  --data-urlencode "run_id=${RUN_ID}"
```

For checkpoint files, follow `next_page_token` until it is absent or null. Download the returned presigned URLs without
forwarding the Baseten API key to the storage host.

When presenting this request, explain that it creates billable inference resources and requires the user's confirmation
before execution. Confirm endpoint availability and replace the placeholders:

```sh
curl --fail-with-body --request POST \
  'https://api.baseten.co/v1/loops/checkpoints/deploy' \
  --header "Authorization: Bearer ${BASETEN_API_KEY}" \
  --header 'Content-Type: application/json' \
  --data '{
    "checkpoint_ids": ["<SAMPLER_CHECKPOINT_ID>"],
    "model_name": "loops-checkpoint",
    "instance_type_id": "<INSTANCE_TYPE_ID>",
    "hf_secret_name": "<TEAM_HF_SECRET_NAME>"
  }'
```

The response contains `model_id` and `deployment_id`. The Hugging Face secret must exist in the checkpoint's team;
`hf_secret_name` is its name, not its value. Every checkpoint in one request must belong to the same team, and the
caller must have deployment permission for that team. The caller need not personally own the checkpoint or belong to
only one team. Missing and inaccessible checkpoints share one public error.

Only sampler-target checkpoints deploy; trainer-target checkpoints contain training state. Deployment is not idempotent.
A timeout or lost response leaves the outcome unknown: inspect the team's models and deployments before retrying. If you
cannot establish whether a deployment was created, stop and ask for reconciliation rather than creating another one. Do
not invent an idempotency key or assume repeating a model name makes retries safe.

## Unattended SDK clients

The client process orchestrates training and needs sustained outbound connectivity. Use `baseten loops exec` for managed
execution rather than relying on a laptop to remain awake. Your workspace must have Training SSH enabled; see the
[Training SSH prerequisites](https://docs.baseten.co/training/ssh#prerequisites).

```sh
baseten loops exec --dir . --with-uv -- uv run python train.py
baseten train job logs --job-id <JOB_ID> --tail
```

The first command packages the directory selected by the required `--dir` flag and submits the client as a Training Job.
Use `.` for the current project or pass another project path. The remote command runs from that directory. Submission
returns a job ID; use it with the separate log command. To submit and follow logs in one command, add `--tail` before
`--`:

```sh
baseten loops exec --dir . --with-uv --tail -- uv run python train.py
```

The native Baseten client streams logs to stderr and supports OAuth refresh. The job result stays on stdout; add
`--output json` before `--` for a structured result with `job_id`. With `--tail`, a job that fails to deploy or execute
causes exit code 1. Ctrl-C stops watching without stopping the job. Resume with the separate log command above.

Submission uses the active Baseten CLI profile. The remote job receives `BASETEN_API_KEY` through a team secret, created
on first use unless you supply a credential. Submission does not copy the active profile into the job. The delegated
Truss submission process cannot refresh an OAuth token.

A third-party sandbox or hosted notebook can restrict networking even while the process stays running. Check DNS
resolution and outbound HTTPS access from the environment running the script. Check proxy, VPN, firewall,
idle-connection, and process-suspension policies. One successful API request does not establish sustained connectivity.
Do not assume a specific provider blocks Loops without evidence from that environment.

## Sources and checks

- [Loops concepts](https://docs.baseten.co/loops/concepts) covers client execution and resource behavior.
- [Where to run the script](https://docs.baseten.co/loops/where-to-run) covers running locally versus on Baseten with
  `baseten loops exec`.
- [Availability modes](https://docs.baseten.co/loops/availability-modes/overview) covers serverless and dedicated
  billing and placement.
- [Deploy a checkpoint](https://docs.baseten.co/loops/deploy-checkpoints) covers CLI previews and deployment.
- [Capacity and quota errors](https://docs.baseten.co/troubleshooting/loops#resolve-capacity-and-quota-errors) covers
  the `429` and `403` responses above.
- [Loops API reference](https://docs.baseten.co/reference/loops-api/overview) is the public source for REST contracts.
  The deploy request takes `checkpoint_ids`, `model_name`, `instance_type_id`, and `hf_secret_name`.
- [Loops CLI reference](https://docs.baseten.co/reference/cli/baseten/loops) documents released commands.

Verify live MCP discovery and input schemas, released CLI help, and the linked documentation before promising an
operation. A live job or deployment smoke test needs explicit approval to spend compute and a cleanup plan. Offline
evaluations do not verify live authentication, permissions, billing, or deployment behavior.

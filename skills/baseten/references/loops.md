# Loops operations

Use this reference for Loops lifecycle operations, checkpoint deployment, and running SDK clients unattended. For
training code, use the [Loops quickstart](https://docs.baseten.co/loops/quickstart) and
[SDK reference](https://docs.baseten.co/reference/sdk/loops/overview). Select a model from
[supported models](https://docs.baseten.co/loops/supported-models), not the inference model catalog.

## Availability and authentication

This reference is staged for the Loops MCP and checkpoint API releases. Before recommending an operation, inspect the
connected MCP server's tools and input schemas, the hosted API reference, or `baseten loops exec --help`. An operation
described here is not proof that the connected server or installed CLI supports it. If it is absent, report that
limitation. Use the REST fallback only when that endpoint is documented and deployed.

The backend MCP uses an API key for its configured organization. CLI OAuth login does not establish MCP OAuth support.
REST requests use `Authorization: Bearer <API_KEY>` against `https://api.baseten.co`. These tools manage platform
resources; they do not host or expose the Forge agent workflow.

## MCP tools and REST equivalents

The tool names below are backend names; a client may add a server-name prefix. Use the discovered input schema, not the
REST body verbatim: MCP request objects can be nested under names such as `create_loops_run_request_v1` and
`deploy_loops_checkpoint_request_v1`.

| MCP tool | REST operation | Inputs |
| --- | --- | --- |
| `create_loops_session` | `POST /v1/loops/sessions` | No request body for the organization route. |
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

`baseten loops checkpoint deploy` is a separate CLI path that delegates to Truss, not a wrapper for this REST endpoint.

## Unattended SDK clients

The client process orchestrates training and needs sustained outbound connectivity. Once available in the installed CLI,
use managed execution rather than relying on a laptop to remain awake:

```sh
baseten loops exec --with-uv -- uv run python train.py
baseten train job logs --job-id <JOB_ID> --tail
```

The first command packages the current directory and submits the client as a Training Job. It returns after submission;
use the returned job ID with the separate log command. Do not add `--tail` to `loops exec`.

Submission uses the active Baseten CLI profile. The remote job receives `BASETEN_API_KEY` through a team secret, created
on first use unless you supply a credential. Submission does not copy the active profile into the job. The delegated
Truss process cannot refresh an OAuth token; the separate native log command can.

## Sources and release checks

- [Loops concepts](https://docs.baseten.co/loops/concepts) covers client execution and resource behavior.
- [Loops API reference](https://docs.baseten.co/reference/loops-api/overview) is the public source for REST contracts.
- [Loops CLI reference](https://docs.baseten.co/reference/cli/baseten/loops) documents released commands.

Before publishing this reference, deploy backend PRs [30996](https://github.com/basetenlabs/baseten/pull/30996) and
[30741](https://github.com/basetenlabs/baseten/pull/30741), release CLI
[115](https://github.com/basetenlabs/baseten-cli/pull/115), and publish docs
[1616](https://github.com/basetenlabs/docs.baseten.co/pull/1616) plus the checkpoint-deployment API reference. The new
endpoint example above is staged against #30741's request schema; it must match the hosted reference before this skill
ships. Skills are not the source of truth for unreleased product behavior.

Then verify live MCP discovery and input schemas, released CLI help, and the linked documentation. A live job or
deployment smoke test needs explicit approval to spend compute and a cleanup plan. Offline evaluations do not verify
live authentication, permissions, billing, or deployment behavior.

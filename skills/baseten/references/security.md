# Baseten security practices

How to handle Baseten credentials, secrets, access, and production changes when you act for a user. The rules in
`SKILL.md` § Security rules always apply; this file has the procedures behind them. Authoritative docs:
<https://docs.baseten.co/organization/api-keys>, <https://docs.baseten.co/organization/secrets>, and
<https://docs.baseten.co/observability/security>. For compliance programs, policies, and data handling commitments, send
the user to <https://docs.baseten.co/observability/security> and the [Baseten Trust Center](https://trust.baseten.co/)
instead of summarizing them.

## Authenticate with what is already configured

- Baseten CLI: `BASETEN_API_KEY` in the environment, or a stored profile from `baseten auth login`. Check the resolved
  profile with `baseten auth status`; target another workspace with `--profile`.
- Local development: `baseten auth login --web` signs in through the browser. Use it for local work in place of a
  personal key.
- Backend MCP: OAuth sign-in by default; headless clients use a key stored in `BASETEN_MCP_KEY` (see `SKILL.md` §
  Setup).
- Code you write reads the key from the environment: `Authorization: Bearer $BASETEN_API_KEY`, or
  `os.environ["BASETEN_API_KEY"]`.
- Baseten SDK applications authenticate with `BASETEN_API_KEY`; a CLI sign-in doesn't sign an application in.

When authentication fails (`401`), run `baseten auth status` and report what you find. Common causes from the docs: the
key expired, was revoked, or was a personal key revoked after 30 days without use, or its owner was deprovisioned. Ask
the user to sign in again or provide a working key through the environment.

## Choose the narrowest key

Create a key only when the user asks for one. Match the workload:

| Workload | Credential |
| --- | --- |
| Local development and CLI use | Browser sign-in with `baseten auth login --web` |
| CI that deploys models | Team key with full access (`--type workspace-manage-all`) in the team that owns the models |
| CI that starts Loops runs or Training Jobs and deploys checkpoints | Team key with **Manage and call all team models** in the team that owns the training resources |
| Application or partner that calls models | Team inference key (`--type workspace-invoke`) with `--model-id` for each allowed model |
| Calls limited to specific environments, or to Model APIs only | Team key created in the dashboard with **Restricted environment access** or **Call Model APIs** |
| Metrics export | Team key with metrics-only access (`--type workspace-export-metrics`) |
| Automated key provisioning and rotation | API key management key (`--type workspace-manage-api-keys`); only Organization Admins create these |
| Direct sandbox API or sandbox MCP calls | Short-lived sandbox access token (see Sandboxes below) |

- Use team keys for production, CI/CD, and shared automation. Personal keys carry the user's permissions, are revoked
  when the user is deprovisioned, and are revoked automatically after 30 days without use.
- Omitting `--model-id` on an inference key grants access to every model in the team.
- Set an expiration on every key: `--expires-at "<ISO 8601 timestamp>"`. Personal keys require one, within 90 days or
  the organization's limit. An expiration can't be changed later; rotate to change it.
- The value is shown once. Store it directly in the user's secret manager or CI secret store, then confirm the key's
  name, type, team, and expiration with `baseten org api-key list` (metadata only, never values). Check model lists,
  environment restrictions, and Model APIs access in the dashboard.

```sh
baseten org api-key create \
  --type workspace-invoke \
  --name production-inference \
  --team "<team>" \
  --model-id "<model-id>" \
  --expires-at "<expires-at>"
```

## Keep credentials out of code, logs, and prompts

- Store keys in environment variables or a secret manager. Never commit a key.
- Refer to a key by its environment variable name, its key name, or its prefix. Don't print, log, or paste the value.
- Pass values on stdin, not as flags: `baseten org secret set --name <name>` and
  `baseten auth login --with-api-key --profile <profile>` read stdin. `--value` leaks into shell history and `ps`
  output.
- Keep the API key and sandbox access tokens out of agent prompts, application logs, and code you submit to a sandbox.
  Don't put the Baseten API key in a sandbox's environment variables.
- Keys created on or after 15:30 UTC on November 9, 2026, start with `b10_`. Secret scanners can match
  `b10_[A-Za-z0-9]{8}\.[A-Za-z0-9]{32}`; older keys lack the prefix and don't match.

## Respond to an exposed key

A key that appears in a commit, file, log, or transcript is exposed. Don't use it, copy it, or quote it. Tell the user
where it appeared, identified by location and prefix, and that the docs direct them to revoke it immediately and create
a replacement. Revocation is permanent and stops every workload that uses the key, so the user decides when it happens.

To replace a key that a workload still needs (rotation):

1. Create a replacement with the original's type, team, model list, and environment restrictions. Dashboard **Recreate
   API key** copies the current permissions, including environment restrictions and Model APIs access.
2. Check the replacement's access, then update the workload's secret or environment variable. Restart or redeploy if the
   workload reads credentials only at startup.
3. Run an operation the workload normally performs and confirm it succeeds.
4. Revoke the original by prefix (`baseten org api-key delete --prefix "<key-prefix>"`) and confirm the workload still
   succeeds.

## Reference secrets by name

Secrets hold credentials a model, Chain, or training job needs at runtime. Their values live in Baseten; configs hold
names only.

```yaml
secrets:
  - hf_access_token
```

- `model.py` reads `kwargs["secrets"]["hf_access_token"]`. Custom Docker servers read `/secrets/hf_access_token`.
- Weights loaded through BDN authenticate with the weight source's `auth` block (`auth_method: CUSTOM_SECRET`,
  `auth_secret_name: hf_access_token`). A `secrets:` entry alone doesn't authenticate weight mirroring.
- Training jobs inject secrets with `SecretReference(name="...")` in `environment_variables`, never plain strings.
- Never put a secret value in `config.yaml`, in `environment_variables`, or in code.
- In organizations with teams, secrets are team-scoped: a deployment reads only its own team's secrets.
- Setting a secret upserts by name, and names are normalized (`hf_access_token` and `hf-access-token` are the same
  secret). A new value takes effect immediately for every deployment that uses it. Check
  `baseten org secret list --team <team>` before setting a name, and overwrite an existing secret only when the user
  asks.

## Use short-lived cloud credentials

Prefer workload identity to long-lived cloud keys stored as secrets.

- **OIDC** (<https://docs.baseten.co/organization/oidc>): Baseten issues short-lived tokens scoped to a workload. Use it
  to pull images from ECR or Artifact Registry and to read weights from S3 or GCS at build time; enable it at runtime
  with `runtime.oidc.enabled: true` (not available for training jobs). Write the most specific subject condition that
  fits, such as one team, model, or environment. Never grant `v=1:org=*:team=*:*`. Get org and team IDs with
  `baseten org describe` and `baseten org team list`.
- **AWS AssumeRole** (<https://docs.baseten.co/organization/aws-assume-role>): build-time access to ECR and S3 through a
  role in the user's AWS account. The trust policy must require the organization's external ID (`baseten org describe`).
  Attach read-only permissions scoped to the specific repository or bucket. The trust covers the whole Baseten
  organization; use runtime OIDC for model code that calls AWS at inference time.
- When migrating from long-lived credentials, deploy and test with OIDC first, then remove the old credentials and ask
  the user before deleting the secrets that held them.

## Respect access controls

- Roles: Admin, Member, and Viewer. Viewers have read-only access and can call models. Role, membership, SSO, and SCIM
  settings belong to the user's admins; leave them unchanged.
- Restricted environments: only designated users can modify deployments, autoscaling, or promotions in them. A `403` on
  such an operation means the credential's user lacks access. Report it; don't retry with another credential.
- Regional environments: when an environment requires its regional endpoint
  (`https://model-{model_id}-{env_name}.api.baseten.co/predict`), its standard endpoint returns `403`. Update the caller
  to the regional endpoint.
- Validate a deployment in a separate environment before promoting it to production.
- Prefer deactivation to deletion. Deleting a deployment is irreversible; deleting a sandbox or its volume permanently
  removes its files.

## Verify changes in the audit log

The audit log records deploys, promotions, autoscaling and instance-type changes, environment changes, API key creation
and deletion, secret updates and deletion, webhook signing secret changes, SSH certificate signing, and user role
changes.

```sh
baseten org audit-logs --since 7d --event-type-group deployed --output json
baseten model audit-logs --model-id <model-id> --since 30d --event-type-group promoted
```

In organizations with teams, only Organization Admins can read the workspace-wide log; members can read activity for
models and Chains in their teams.

## Restrict egress for sensitive deployments

By default, a deployment can reach any host on TCP ports 443 and 80. `runtime.egress_restrictions` in `config.yaml`
limits outbound traffic to `ip_allow_list` (public IPv4 or CIDR) and `fqdn_allow_list`. The organization must have the
feature enabled.

```yaml
runtime:
  egress_restrictions:
    fqdn_allow_list:
      - model-<model-id>.api.baseten.co
```

- Allow exact hostnames, such as each Baseten model's hostname, rather than wildcards like `*.api.baseten.co`.
- Restrictions apply to runtime downloads too. Load weights through BDN or the model cache instead of allowing broad
  download hosts.
- Allow lists can't change in place; deploy a new version. After deploying, test every outbound call the model needs.
- Restrictions apply to model deployments only, not Chains or training jobs. `fqdn_allow_list` is enforced by IP, so
  allowing one host on shared infrastructure, such as one S3 bucket, permits others served from the same IPs.

## Verify async webhook signatures

- Webhook endpoints use HTTPS (`localhost` is allowed for development).
- Create a webhook secret in the workspace Secrets settings. Verify with that secret, not a model secret or the API key.
- Compute HMAC-SHA256 of the raw request body before parsing it. Compare against every `v1=` value in
  `X-BASETEN-SIGNATURE` with a constant-time comparison (`hmac.compare_digest`). Reject requests with a missing header
  or no match.
- During rotation, the header carries signatures for both secrets, and both stay valid for 24 hours.

Code: <https://docs.baseten.co/inference/async#secure-webhooks>.

## Sandboxes

- The Baseten CLI and SDKs create and refresh sandbox access tokens. Create one yourself only when calling the sandbox
  API or a sandbox MCP server directly. Never send the workspace API key to a sandbox URL.
- A sandbox access token expires 2 hours after creation and carries the creator's team memberships; it isn't limited to
  one sandbox.
- Previews are private by default and need a preview token. A URL containing a preview token is a credential; share it
  only as the user directs. Make a preview public only when the user asks. Set preview and preview token expirations to
  match how long the user needs access; an expired preview is deleted. Deleting a preview removes its tokens.

## Training remote access and private repositories

- Training SSH uses short-lived certificates that the CLI issues on each connection.
- To clone a private GitHub repository from `start_commands`, store a fine-grained GitHub token with **Contents:
  Read-only** as a Baseten secret and inject it with `SecretReference`.

## Frontier Gateway keys

Federated API keys are shown once at mint time. To rotate a customer's key, mint a new key in the same group, hand it
over, and revoke the old key after cutover. Revocation is irreversible, and deleting a group revokes every key in it and
in its descendant groups. Confirm with the user before either.

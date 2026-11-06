# Baseten Sandboxes

Use Sandboxes to run an agent's commands and file operations in an isolated environment. Read the
[overview](https://docs.baseten.co/sandboxes/overview) and [management guide](https://docs.baseten.co/sandboxes/manage)
for the current interfaces and examples. The `baseten sandbox` commands and sandbox volumes are in pre-release, so their
arguments, flags, and output may change.

## Choose an interface

- For a coding agent doing work in a sandbox, use the Baseten CLI.
- For an application that creates and manages sandboxes, use a Baseten Sandbox SDK: TypeScript `@basetenlabs/sandbox`,
  Python `baseten.sandbox`, or Go `github.com/basetenlabs/baseten-go/sandbox`.
- For a model's tool calls, each sandbox exposes its own MCP server. Follow
  [sandbox authentication](https://docs.baseten.co/sandboxes/authentication) to connect it. The workspace MCP server
  manages Baseten resources; the sandbox MCP server runs tools inside that sandbox.

Baseten SDK applications authenticate with `BASETEN_API_KEY`. Signing in to the CLI doesn't sign an application in. SDK
clients create and refresh the sandbox access tokens they need; use the documented client instead of passing a workspace
API key to a sandbox URL.

The Loops cookbook also has sandboxed-agent examples. Follow each recipe's provider and credentials when working on
those integrations.

## Create a sandbox and run a command

Check the CLI and current sign-in before creating resources:

```sh
baseten version
baseten auth status
baseten org team list
```

Use the intended team when several are available. Create a sandbox only when the task calls for a new environment;
inspect an existing sandbox before deciding to replace it.

```sh
baseten sandbox create --team "<team>" --name research-session
baseten sandbox describe --team "<team>" --name research-session --output json
baseten sandbox exec --team "<team>" --name research-session -- 'pwd'
```

Creation waits for `DEPLOYED`. `exec` runs a command in the sandbox; its result is evidence about that command, not
proof that a long-running server is ready. For background processes, output, and exit status, follow
[Run commands and work with files](https://docs.baseten.co/sandboxes/run-commands). An organization can run up to 10
sandboxes at once; a create beyond that fails with a quota error.

Names, images, memory, regions, and volume mounts are creation settings. Read the current
[management guide](https://docs.baseten.co/sandboxes/manage) before changing a sandbox's configuration, especially
environment variables: replacing the variable map must include values the application needs to keep.

## Preview an application

Follow [Sandbox previews](https://docs.baseten.co/sandboxes/previews) to declare an application port, start the process,
and expose it through HTTPS. Bind the application to the sandbox's `HOST` environment variable so the preview can reach
it, and serve it on a port other than `8080`, where the sandbox API server listens. Port `80` can't serve a preview, and
a preview of port `443` must be private.

Previews are private by default and use preview tokens. Preserve the access level the user requests. A preview token is
separate from a sandbox access token and a workspace API key. Verify the application through its returned preview URL
before reporting that it is reachable.

## Preserve project files

Standby preserves a sandbox's local state. Deletion or expiration permanently removes its local files. Put files that
need to outlive the sandbox on a [sandbox volume](https://docs.baseten.co/sandboxes/volumes), or export them before
deleting it.

Sandbox volumes are writable persistent storage, with one sandbox attached at a time. A sandbox can mount one persistent
volume, in the same team and region. Use `baseten sandbox volume` for this storage;
[BDN volumes](https://docs.baseten.co/development/volumes/overview) distribute model weights through `baseten volume`.

```sh
baseten sandbox volume create --team "<team>" --name project-data --size 10Gi
baseten sandbox volume describe --team "<team>" --name project-data --output json
```

Wait for the volume's status to become `DEPLOYED`, then mount it in a new sandbox in its returned region:

```sh
baseten sandbox create --team "<team>" --name research-session \
  --region "<volume-region>" --volume project-data:/data
```

Before moving the volume to another sandbox, delete the old sandbox and wait until the volume has no `attached_to`
value. Check a file from the new sandbox to verify persistence. Volume deletion removes the saved data too, so retaining
a volume and deleting a sandbox have different outcomes.

## Finish and troubleshoot

Choose a [lifecycle and expiration policy](https://docs.baseten.co/sandboxes/lifecycle) that matches how long the user's
project should remain available. Keep requested environments running or in standby; clean up disposable resources
created for a test when the task is complete.

```sh
baseten sandbox describe --team "<team>" --name research-session --output json
baseten sandbox delete --team "<team>" --name research-session --yes
```

Read [process logs](https://docs.baseten.co/sandboxes/logs) for a command failure and
[metrics](https://docs.baseten.co/sandboxes/metrics) for resource use. A `DEPLOYED` sandbox doesn't establish that the
application's process is running, listening on the expected port, or serving correct responses.

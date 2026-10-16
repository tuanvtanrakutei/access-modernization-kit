---
name: dev-stack
description: "Bring a modernization project's Docker stack up, check it, or stop it - backend, frontend and a local development database, with migrations applied. Trigger when the user wants to start, run, check or stop the project locally, or a check needs the stack. Examples: \"/ak:dev-stack up\", \"/ak:dev-stack status\", \"start the dev stack\", \"is the backend up\", \"stop the containers\"."
---

# Dev Stack

Run `dev_stack.py` against the repository the user is in. It reads the rows of
`PROJECT_CONFIG.md` §12 (`COMPOSE_FILE`, `HEALTH_PATH`) when the project has them, and detects
the compose file otherwise.

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/dev_stack.py" <action> --repo . [--compose <COMPOSE_FILE>] [--health-path <HEALTH_PATH>]
```

| Request | Action |
|---|---|
| start, run, bring up, "is it working" on a stack that is down | `up` |
| check, status, "is the backend up" | `status` |
| stop, shut down | `down` (the database volume is kept) |
| "what would it do" | `plan` |

`up` creates the external networks the compose file expects and, on a project whose `DEV_DB` is
`local-container` (or that has no `PROJECT_CONFIG.md` yet), writes a gitignored
`docker-compose.override.yml` with a local PostgreSQL. It then builds, starts, makes and applies
migrations, and waits for the backend's health path and the frontend's page. A frontend that
installs and builds on start takes minutes the first time: run `up` in the background and report
when it ends.

Report what the script printed: each service's URL and whether it answered. On exit `2`, name the
one thing the user has to do (start Docker Desktop, add the override to `.gitignore`). On exit `1`,
show the failing output; a failure in the project's own code is reported, not fixed here.

Never pass `-v` to `down` and never delete the database volume unless the user asks for that by
name: it holds the migrated schema and anything the developer entered.

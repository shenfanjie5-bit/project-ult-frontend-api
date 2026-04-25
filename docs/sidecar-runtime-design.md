# API-5B Sidecar Runtime Design

Status: design only. API-5B does not implement automatic startup, sidecar
packaging, new routes, or any write-capable command surface.

## Goals

- Define how the Tauri/desktop app connects to the local `frontend-api`
  service at startup.
- Define the future decision point for whether Tauri manages a bundled
  Python/runtime sidecar or continues to use an externally started backend.
- Keep API-5B as a design document only. No automatic backend startup is
  introduced in this phase.
- Preserve the current read-only API boundary used by the Project ULT desktop
  workspace.

## Non-Goals

- Do not implement a sidecar.
- Do not add command endpoints.
- Do not bypass `frontend-api` to read Project ULT modules directly from the
  frontend or Tauri shell.
- Do not expose release-freeze, min-cycle, replay, run, freeze, or other
  write operations to the frontend.
- Do not solve multi-user, SaaS, or remote deployment concerns.
- Do not change compatibility matrix verification or promotion semantics.

## Runtime Modes

### External Backend Mode

External backend mode is the current supported runtime model.

The user or developer starts `frontend-api` explicitly:

```bash
project-ult-frontend-api serve \
  --project-root /Users/fanjie/Desktop/Cowork/project-ult \
  --profile lite-local \
  --host 127.0.0.1 \
  --port 8701
```

The Tauri/FrontEnd process connects through environment configuration:

```bash
VITE_PROJECT_ULT_API_BASE=http://127.0.0.1:8701
```

The frontend treats `VITE_PROJECT_ULT_API_BASE` as a service root and appends
`/api`. A direct API-root override remains available through:

```bash
VITE_PROJECT_ULT_API_BASE_URL=http://127.0.0.1:8701/api
```

External mode is simple and explicit. If the backend is not running, the UI
must show a clear unavailable/error state and must not fabricate Project ULT
data.

### Managed Sidecar Mode

Managed sidecar mode is a future option. In this model, Tauri starts a bundled
backend runtime, such as a Python launcher, a packaged Python environment, or a
native/local binary that hosts the same `frontend-api` HTTP service.

A managed sidecar must include:

- Startup command construction from explicit configuration.
- Readiness probing before the UI considers Project ULT API access available.
- Captured stdout/stderr.
- Stable log paths.
- Lifecycle management:
  - start process
  - wait for health
  - surface startup timeout
  - stop process on app exit
  - detect crash and expose degraded/unavailable state
  - avoid restart loops

Managed mode must not silently change the API boundary. It should still expose
the same `frontend-api` HTTP routes and should still require the frontend to
talk only to `frontend-api`.

### Degraded/Offline Mode

Degraded/offline mode is the required UI behavior when `frontend-api` is not
available or returns degraded health.

The UI should:

- Show "starting" while the backend is being probed.
- Show "unavailable" when the backend cannot be reached.
- Show "degraded" when `/api/project-ult/health` responds but reports degraded
  state.
- Keep the page shell visible.
- Show the error envelope or network error state.
- Avoid blank pages.
- Avoid fallback data that could be mistaken for real Project ULT state.

The UI must not fabricate Project ULT data in offline mode.

## Security Boundaries

- `frontend-api` must bind only to `127.0.0.1` by default.
- Sidecar mode must not listen on public interfaces.
- CORS must remain restricted to local development and Tauri origins, such as:
  - `http://127.0.0.1:1420`
  - `http://localhost:1420`
  - `tauri://localhost`
- API-5B does not alter the current read-only route surface.
- API-5B does not introduce command, run, freeze, release-freeze, compat-run,
  e2e-run, min-cycle, or replay POST routes.

If write-capable command endpoints are introduced in a later phase, they must
be separately designed and gated with at least:

- A confirmation token or equivalent explicit action-time authorization.
- Dry-run as the default behavior.
- Audit/command log records.
- An allowlist of permitted command types.
- Clear per-command status and error envelopes.
- Separate route and UI review before exposure.

## Ports And Configuration

Default network configuration:

- Backend host: `127.0.0.1`
- Backend port: `8701`
- Frontend dev host: `127.0.0.1`
- Frontend dev port: `1420`

Relevant backend environment variables:

- `PROJECT_ULT_ROOT`
- `PROJECT_ULT_PROFILE`
- `PROJECT_ULT_FRONTEND_API_MODE`
- `PROJECT_ULT_FRONTEND_API_CORS_ORIGINS`

Relevant frontend/Tauri environment variables:

- `VITE_PROJECT_ULT_API_BASE`
- `VITE_PROJECT_ULT_API_BASE_URL`

### Port Conflicts

External backend mode:

- If `127.0.0.1:8701` is already in use, startup should fail clearly.
- The error should tell the user which port is occupied and how to choose a
  different port.
- The frontend should display unavailable if it is configured for a port that
  does not answer health checks.

Future managed sidecar mode:

- The simplest strategy is fixed port startup with clear failure on conflict.
- A dynamic port strategy is possible, but it requires an explicit handoff
  mechanism before implementation.
- The handoff mechanism must define how Tauri communicates the selected API
  base to the webview before Project ULT requests are issued.
- Candidate handoff mechanisms include:
  - generated runtime config file
  - injected webview initialization value
  - Tauri command that returns sidecar connection info
- Dynamic ports must not be added before the handoff mechanism is designed and
  tested.

## Packaging Strategy

API-5B does not package the backend.

Packaging constraints:

- Do not commit `.venv`.
- Do not commit cache directories.
- Do not commit local `.env`.
- Do not commit local logs.
- Do not depend on a developer-specific absolute path at runtime.

Python dependency installation and lock strategy is deferred to API-5C or a
later packaging phase. The packaging plan must decide whether to use:

- a Python virtual environment generated during install
- a prebuilt standalone Python runtime
- a native launcher wrapping the Python service
- a fully packaged backend binary

Future macOS app bundle design should define how the bundle contains either:

- a backend launcher that locates an installed Project ULT workspace, or
- a backend runtime plus a configured workspace location, or
- a documented external backend dependency.

Recommended log paths:

- macOS app logs:
  `~/Library/Logs/ProjectULT/frontend-api.log`
- Development logs:
  `/tmp/project-ult-frontend-api-8701.log`

Log records should include startup command, selected host/port, project root,
profile, readiness outcome, crash exit code, and timestamps. Logs must not
record secrets.

## Readiness And Health Check

The readiness probe is:

```text
GET /api/project-ult/health
```

Expected semantics:

- `healthy`: the backend is reachable and core read-only sources are available.
- `degraded`: the backend is reachable, but one or more read-only sources are
  missing or degraded.
- network failure: the backend is unavailable or not started.
- non-2xx response: the backend is reachable but not ready for normal UI use.

Suggested readiness policy for a future managed sidecar:

- Probe immediately after process start.
- Retry with short backoff, for example 100 ms, 250 ms, 500 ms, 1 s.
- Use an overall startup timeout, for example 10 to 20 seconds in development.
- After timeout, keep the UI shell visible and show unavailable state.
- If the process exits before readiness, show startup failure and link to the
  log path.

UI states:

- `starting`: sidecar process started or external backend is being probed.
- `healthy`: health endpoint reports healthy.
- `degraded`: health endpoint reports degraded; read-only pages may still show
  available artifacts and per-source degraded states.
- `unavailable`: health request fails, times out, or the configured API base is
  unreachable.

## Testing Plan

API-5B is design only, but future implementation phases should cover:

- Browser dev external mode smoke:
  - start `frontend-api` manually
  - start Vite with `VITE_PROJECT_ULT_API_BASE=http://127.0.0.1:8701`
  - verify System, Data, Graph, and Evidence pages
- Tauri dev external mode smoke:
  - start `frontend-api` manually
  - start Tauri with `VITE_DATA_MODE=projectUlt`
  - verify the same read-only pages in the desktop shell
- Future sidecar mocked process tests:
  - successful startup
  - delayed readiness
  - startup timeout
  - crash before readiness
  - crash after readiness
- Port conflict test:
  - occupy `127.0.0.1:8701`
  - verify clear failure in external mode
  - verify managed sidecar conflict behavior once implemented
- Backend crash/unavailable test:
  - stop backend during UI session
  - verify error state, no blank page, no fabricated Project ULT data
- No POST route introspection:
  - assert Project ULT route table has no `POST`, `PUT`, or `DELETE`
- CORS preflight test:
  - verify allowed local origins receive the expected CORS headers
  - verify unexpected origins are not granted access

## Rollout Plan

- API-5B: design only. No sidecar implementation and no automatic startup.
- API-5C: scriptable external runtime helper. It may help users start the
  backend explicitly, but still must not auto-start from Tauri.
- API-5D: optional managed sidecar prototype behind a feature flag.
- API-5E: full Tauri sidecar packaging smoke, including app bundle behavior,
  readiness, crash handling, logs, and read-only route boundary checks.

## Open Questions

- Which Python packaging format should be used for the backend runtime?
- How will signing and notarization affect bundled Python or backend binaries?
- Should managed sidecar mode use a fixed port or dynamic port handoff?
- If dynamic ports are used, what is the exact handoff mechanism from Tauri to
  the webview?
- What is the log retention policy for desktop app logs?
- How should logs be redacted if future write-capable operations exist?
- How should Project ULT module workspace paths be discovered on another
  machine?
- Should the desktop app support multiple local Project ULT roots?
- What is the migration path from external backend mode to managed sidecar
  mode?

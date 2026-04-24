# project-ult-frontend-api

Read-only Backend-for-Frontend skeleton for Project ULT API-1 through API-3A.

This module exposes the System Map and read-only Cycle/Formal/Entity/Data
surface:

- `GET /api/project-ult/health`
- `GET /api/project-ult/modules`
- `GET /api/project-ult/profiles`
- `GET /api/project-ult/compat`
- `GET /api/project-ult/cycles`
- `GET /api/project-ult/cycles/{cycle_id}`
- `GET /api/project-ult/formal/{object_type}`
- `GET /api/project-ult/formal/{object_type}/{cycle_id}`
- `GET /api/project-ult/manifests/latest`
- `GET /api/project-ult/entities/search?q=&limit=`
- `GET /api/project-ult/entities/{entity_id}`
- `GET /api/project-ult/data/canonical/{table}?limit=&cursor=`
- `GET /api/project-ult/data/raw/{source}?limit=&cursor=`
- `GET /api/world-state/latest`
- `GET /api/pool/latest`
- `GET /api/recommendations/latest`

It reads assembly-owned public artifacts from:

- `assembly/module-registry.yaml`
- `assembly/profiles/*.yaml`
- `assembly/compatibility-matrix.yaml`

Cycle/Formal routes prefer `data-platform/artifacts/frontend-api/*.json`
read-model artifacts and otherwise degrade through data-platform public package
APIs if they are importable in the runtime.

Entity/Data routes read stable frontend-api artifacts owned by their source
modules:

- `entity-registry/artifacts/frontend-api/entities.json`
- `data-platform/artifacts/frontend-api/data/canonical/*.json`
- `data-platform/artifacts/frontend-api/data/raw/*.json`

Boundary rules for this phase:

- No command endpoints.
- No release-freeze behavior.
- No imports from assembly private implementation modules or sibling module
  private implementation modules.

Assembly integration:

- Standard public entrypoints live in `frontend_api.public`:
  - `health_probe`
  - `smoke_hook`
  - `init_hook`
  - `version_declaration`
  - `cli`
- Assembly registration is tracked in
  `/Users/fanjie/Desktop/Cowork/project-ult/assembly/MODULE_REGISTRY.md`.
- Public smoke evidence is tracked in
  `/Users/fanjie/Desktop/Cowork/project-ult/assembly/reports/smoke/frontend-api-api1-public-smoke-20260425.md`.

## Run

```bash
cd /Users/fanjie/Desktop/Cowork/project-ult/frontend-api
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
project-ult-frontend-api serve \
  --project-root /Users/fanjie/Desktop/Cowork/project-ult \
  --profile lite-local \
  --host 127.0.0.1 \
  --port 8701
```

## Test

```bash
cd /Users/fanjie/Desktop/Cowork/project-ult/frontend-api
python -m pytest
```

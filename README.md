# project-ult-frontend-api

Read-only Backend-for-Frontend for the Project ULT API-1 through API-5C
release surface.

This module exposes the System, Cycle/Formal, Entity/Data, Graph, and Evidence
read-only surface:

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
- `GET /api/project-ult/graph/subgraph?seed=&depth=&limit=`
- `GET /api/project-ult/graph/paths?seed=&depth=&limit=&channel=`
- `GET /api/project-ult/graph/impact?entity_id=&cycle_id=`
- `GET /api/project-ult/reasoner/providers`
- `GET /api/project-ult/reasoner/results?limit=&cursor=&cycle_id=`
- `GET /api/project-ult/audit/{cycle_id}`
- `GET /api/project-ult/replay/{cycle_id}`
- `GET /api/project-ult/backtests?limit=&cursor=`
- `GET /api/project-ult/backtests/{backtest_id}`
- `GET /api/project-ult/orchestrator/runs?limit=&cursor=&status=`
- `GET /api/project-ult/orchestrator/runs/{run_id}`
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

Raw data artifacts are not part of the default production read-only surface.
They are only exposed through the optional debug route
`GET /api/project-ult/debug/data/raw/{source}` when
`PROJECT_ULT_FRONTEND_API_ENABLE_RAW_DEBUG_ROUTES=1` is set.

Graph routes read stable frontend-api artifacts owned by graph-engine:

- `graph-engine/artifacts/frontend-api/subgraph.json`
- `graph-engine/artifacts/frontend-api/paths.json`
- `graph-engine/artifacts/frontend-api/impact.json`

MVP20 read-side behavior is intentionally narrow: graph/impact artifacts may
surface `decision_target` and `context_only` related entities, while
`recommendation_snapshot` public outputs keep only the decision target
recommendations and cap that list at 20 items. This is response
sanitization only; frontend-api does not create graph relationships or write
formal snapshots.

Evidence routes read stable frontend-api artifacts owned by reasoner-runtime,
audit-eval, and orchestrator:

- `reasoner-runtime/artifacts/frontend-api/providers.json`
- `reasoner-runtime/artifacts/frontend-api/results.json`
- `audit-eval/artifacts/frontend-api/audit/*.json`
- `audit-eval/artifacts/frontend-api/replay/*.json`
- `audit-eval/artifacts/frontend-api/backtests.json`
- `audit-eval/artifacts/frontend-api/backtests/*.json`
- `orchestrator/artifacts/frontend-api/runs.json`
- `orchestrator/artifacts/frontend-api/runs/*.json`

Boundary rules for this phase:

- No command endpoints.
- No release-freeze behavior.
- No sidecar auto-start or managed backend lifecycle.
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

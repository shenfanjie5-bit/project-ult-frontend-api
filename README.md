# project-ult-frontend-api

Read-only Backend-for-Frontend skeleton for Project ULT API-1.

This module exposes the System Map surface only:

- `GET /api/project-ult/health`
- `GET /api/project-ult/modules`
- `GET /api/project-ult/profiles`
- `GET /api/project-ult/compat`

It reads assembly-owned public artifacts from:

- `assembly/module-registry.yaml`
- `assembly/profiles/*.yaml`
- `assembly/compatibility-matrix.yaml`

Boundary rules for this phase:

- No command endpoints.
- No release-freeze behavior.
- No assembly registry registration.
- No imports from assembly private implementation modules or sibling module
  implementations.

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

# frontend-api Project Doc

`frontend-api` is the Project ULT console HTTP boundary. API-1 is intentionally
small: it only exposes read-only System/Assembly data for the frontend System
Map.

## API-1 Scope

- Health: frontend-api service health plus assembly artifact availability.
- Modules: assembly module registry rows.
- Profiles: assembly profile manifests with matching compatibility evidence.
- Compat: assembly compatibility matrix rows.

## Out of Scope

- Command endpoints such as compat run or smoke run.
- Release-freeze and matrix promotion.
- Assembly registry registration for this module.
- Imports from private assembly loaders, validators, runners, or sibling module
  implementations.

## Data Sources

The adapter reads stable assembly artifacts under the configured Project ULT
root. If assembly later exposes a public read API for registry/profile/compat,
the adapter can switch to that boundary without changing route contracts.

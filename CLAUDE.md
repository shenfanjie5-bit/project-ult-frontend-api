# frontend-api Guardrails

- The API is a read-only BFF boundary in API-1.
- Treat assembly registry, profile, and compatibility YAML files as the source
  artifacts for System Map responses.
- Do not import `assembly.registry`, `assembly.profiles`, `assembly.compat`, or
  sibling module implementation packages.
- Do not add command endpoints, release-freeze behavior, or assembly registry
  registration in this phase.
- Keep route schemas stable and explicit; adapters may map fields but must not
  create business truth.

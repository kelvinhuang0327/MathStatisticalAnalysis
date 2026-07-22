# Shared Control Plane v1

Document status: `DRAFT_FOR_OWNER_REVIEW`

This directory is the public, cross-project home for common evidence, authorization, routing,
lifecycle, manifest, and role-prompt rules. Consumer facts stay in the consumer repository's
`.ai/agent-profile.yaml` and in one Task Manifest.

## Canonical sources

Exactly five files are maintained as policy sources:

1. `AGENT_CORE.md`
2. `ROLE_PROFILES.md`
3. `ROUTING_AND_LIFECYCLE.md`
4. `TASK_MANIFEST.schema.yaml`
5. `WORKER_TASK_TEMPLATE.md`

Everything under `compiled/` is generated. `prototype/` is implementation, `examples/` is neutral
usage/migration evidence, and this README is an operator guide; none is an additional policy source.

## Commands

No package or network dependency is required. Schema and example files use JSON-compatible YAML,
which is valid YAML 1.2 and permits deterministic standard-library parsing.

```bash
python prompt/control-plane-v1/prototype/promptctl.py compile
python prompt/control-plane-v1/prototype/promptctl.py lint
python prompt/control-plane-v1/prototype/promptctl.py check
python prompt/control-plane-v1/prototype/promptctl.py fingerprint
python prompt/control-plane-v1/prototype/promptctl.py render \
  --manifest prompt/control-plane-v1/examples/low-readonly.task.yaml
```

`compile` writes all four prompts. `check` performs strict UTF-8/Markdown/YAML checks, regenerates
twice, compares fresh bytes with committed outputs, validates role boundaries and route contracts,
and scans operational content for consumer hardcoding and public-repository hazards.

## Change flow

1. Edit only the relevant canonical source or sources.
2. Run `lint`, then `compile`, then `check`.
3. Review generated diffs; never patch a compiled prompt directly.
4. Validate neutral examples and project-local manifests before rendering.
5. Keep outputs in `DRAFT_FOR_OWNER_REVIEW` until an Owner separately approves activation.

Compiled prompts are standalone: they embed their shared rules, role profile, routing table, and—for
the Planner only—the manifest schema and complete Worker Prompt template. A web agent does not need
access to this local source tree to use a compiled prompt.

## Included evidence and examples

- `examples/LEGACY_RESPONSIBILITY_MAPPING.md` inventories how the four supplied legacy prompts were
  retained, centralized, routed, parameterized, or removed.
- `examples/agent-profile.example.yaml` shows neutral consumer-owned project context.
- `examples/low-readonly.task.yaml` demonstrates the lean Planner -> Worker -> Handoff route.
- `examples/medium-implementation.task.yaml` demonstrates implementation plus independent fixed-head
  review, integration, and standard cleanup.

This draft performs no activation, publication, deployment, remote mutation, or consumer-memory
write.

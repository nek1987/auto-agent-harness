# Spec Creation Skills + Documentation Gate

## Summary

Add spec-creation skills context to the spec chat system prompt, add a coverage review phase, and require documentation deliverables to be part of the spec and final feature plan.

## Goals

- Inject expert skills for spec creation to improve requirements quality.
- Ensure coverage review happens before approval to catch missing flows.
- Require final documentation deliverables and make them part of the feature count.

## Decisions

- Add a new skills category `spec_creation` in `lib/skills_loader.py`.
- Inject `spec_creation` skills into the create-spec system prompt (replace `{{SKILLS_CONTEXT}}`, fallback to prepend).
- Extend `.claude/commands/create-spec.md` with a coverage review step and documentation deliverables in `app_spec.txt`.
- Add a final "Documentation & Handoff" feature category to the initializer prompt so docs are built after features and tests.

## Flow Changes

1. Spec chat loads create-spec prompt and injects `spec_creation` skills.
2. The agent performs a coverage review before final approval.
3. The generated `app_spec.txt` includes a documentation deliverables section.
4. The initializer feature plan ends with documentation tasks.

## Documentation Outputs

- docs/OVERVIEW.md
- docs/ARCHITECTURE.md
- docs/API.md
- docs/RUNBOOK.md
- docs/CONTEXT.md

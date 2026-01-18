# Agent Guardrails + Model Control

## Summary

Introduce explicit engineering guardrails (env/config + TDD) in coding prompts, align coding skills with quality patterns, and add UI-driven model selection for agent runs.

## Goals

- Prevent hardcoded URLs/keys by enforcing env/config usage.
- Require test-first implementation for code-level logic.
- Allow users to select Claude models from the UI per project.

## Decisions

- Update coding prompt templates to include guardrails and TDD requirements.
- Update `coding` skills to prioritize clean code, env management, and TDD.
- Add a project-level Agent Settings panel (collapsed by default) stored per project in localStorage and pass to `/agent/start`.

## Flow Changes

1. UI exposes a project-level Agent Settings panel with lock/unlock controls and stores model choices locally.
2. Agent start requests include the selected model.
3. Process manager passes `--model` to the agent CLI.
4. Coding prompts enforce env/config usage and test-first development.

## Notes

- Model selection currently applies to agent runs (initializer/coding/regression/redesign).
- Spec analysis and spec creation models remain fixed unless extended later.

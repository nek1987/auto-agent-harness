---
description: Enter plan mode for designing implementation
---

Please enter **plan mode** to design a structured implementation approach before coding.

## What Plan Mode Does

1. **Explore the codebase** - Understand existing architecture, patterns, and dependencies
2. **Identify key files** - Find files that will need to be modified or created
3. **Design approach** - Outline the implementation strategy with clear phases
4. **Consider alternatives** - Evaluate different approaches with trade-offs
5. **Document plan** - Create a structured plan file for review

## Planning Guidelines

When creating a plan:

### Structure
- Break work into distinct phases (3-5 phases ideal)
- Each phase should have clear deliverables
- Order phases by dependencies (foundation first)

### Content
- List specific files to create/modify
- Include code snippets for complex changes
- Note potential risks and mitigation strategies
- Identify integration points with existing code

### Format
Use this structure for the plan:

```markdown
# Plan: [Feature Name]

## Problem Statement
[What needs to be built/fixed]

## Current State
[Relevant existing code/architecture]

## Proposed Solution
[High-level approach]

## Implementation Phases

### Phase 1: [Name]
**Files:** list of files
**Changes:** what to do
**Verification:** how to test

### Phase 2: [Name]
...

## Risks & Considerations
- [Risk 1]: [Mitigation]
- [Risk 2]: [Mitigation]

## Verification Steps
1. [How to verify phase 1]
2. [How to verify phase 2]
```

## After Planning

Once the plan is approved:
1. Create the plan file in `.claude/plans/` or project docs
2. Use the TodoWrite tool to track implementation progress
3. Work through phases sequentially
4. Mark phases complete as you verify them

## When to Use Plan Mode

- Complex features spanning multiple files
- Architectural changes or refactoring
- Unclear requirements needing exploration
- Features with multiple valid approaches
- Any change you want reviewed before implementation

## Start Planning

Begin by:
1. Exploring relevant parts of the codebase
2. Understanding current architecture
3. Drafting the implementation approach

Ask clarifying questions if the requirements are unclear.

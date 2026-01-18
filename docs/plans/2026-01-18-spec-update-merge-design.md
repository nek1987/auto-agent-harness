# Spec Update Merge Design

## Overview

Add a guided spec update workflow that ingests a large requirements document (md/txt or paste), extracts structured requirements across the entire document, and merges them into the existing app_spec with a controlled diff and feature mapping flow. The process preserves project progress and flags logic changes for review.

## Goals

- Support large specs that exceed model context without losing details.
- Provide a deterministic, multi-step flow: analyze -> diff -> map -> apply.
- Preserve completed work where safe and flag logical changes.
- Store version history (snapshots + diffs) for audit and rollback.

## Non-Goals

- Full requirements management system with custom schemas.
- Automatic application of changes without user confirmation.

## User Flow

1. Update Spec (project action)
   - Upload md/txt or paste text.
   - Start analysis.

2. Diff and Coverage
   - Show coverage map (sections processed, requirements count).
   - Show proposed app_spec and summary of changes.
   - Block next step if coverage < 100% or unresolved conflicts.

3. Feature Mapping
   - Auto-match new or changed features to existing ones.
   - User confirms or edits mapping.
   - Show impact summary: keep status, needs review, new.

4. Apply
   - Write a new spec version and diff.
   - Update features based on mapping and change classification.

## Large Spec Processing (Extract -> Spec)

- Chunking: split by headings and lists, 2-4k tokens per chunk.
- Extraction pass: each chunk becomes structured requirements with:
  - req_id, title, description, acceptance, constraints, priority, tags, source_anchor.
- Normalization: dedupe near-duplicates, group conflicts into conflict_group.
- Synthesis: build the proposed app_spec from the full requirements set.
- Coverage gate: require 100% chunk coverage and resolved conflicts.

## Data Model

- Extend prompts/.spec_manifest.json with a spec_versions list:
  - version_id, created_at, source, spec_file, input_file, diff_file, notes.
- Store files under prompts/spec_versions/:
  - app_spec.<timestamp>.xml
  - app_spec.<timestamp>.diff.json
  - input.<timestamp>.md
- Store extraction artifacts under prompts/spec_updates/:
  - requirements.<timestamp>.json
  - mapping.<timestamp>.json

## Change Classification Rules

- Cosmetic: rename, reorder, formatting, and description-only changes.
- Logic: behavior changes, data constraints, workflows, permissions, edge cases.
- Logic changes must set feature status to needs_review.
- Cosmetic changes keep existing status.

## API Endpoints

- POST /api/spec/update/analyze
  - Input: project_name, input_text, mode (merge|rebuild)
  - Output: proposed_spec, diff, coverage, requirements, conflicts, match_candidates

- POST /api/spec/update/apply
  - Input: mapping_decisions, apply_mode, notes
  - Output: version_id, updated_feature_counts

## UI Components

- SpecUpdateWizard (steps: upload, diff/coverage, mapping, apply)
- CoverageMap (section list with extraction counts)
- MappingTable (new/changed -> existing with confidence)
- HybridSpecEditor (visual tree + raw XML with sync)

## Error Handling

- If chunk extraction fails: retry per chunk and mark as incomplete.
- If conflicts remain: block apply and highlight conflict groups.
- If mapping incomplete: require confirmation before apply.

## Testing

- Unit tests for chunking, extraction normalization, and diff classification.
- Integration tests for analyze/apply API flows.
- UI test for step gating and mapping confirmation.

## Open Questions

- Exact requirement schema fields to expose in visual editor.
- Confidence thresholds for auto-match suggestions.

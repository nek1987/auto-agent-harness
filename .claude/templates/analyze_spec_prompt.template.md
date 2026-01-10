# Spec Analysis Task

You are analyzing an application specification (app_spec.txt) for quality and completeness.

## Spec Content

<spec>
{SPEC_CONTENT}
</spec>

## Analysis Requirements

Analyze this specification thoroughly and provide your assessment.

### 1. Validation Check

Verify the presence of required sections:

- [ ] Has `<project_specification>` root tag
- [ ] Has `<project_name>` with a clear, descriptive name
- [ ] Has `<overview>` with 2-3 sentences describing the app
- [ ] Has `<technology_stack>` with frontend and backend specified
- [ ] Has `<feature_count>` with a realistic number (typically 20-200)
- [ ] Has `<core_features>` with categorized feature descriptions
- [ ] Has `<database_schema>` if the app uses a database
- [ ] Has `<api_endpoints_summary>` for backend APIs
- [ ] Has `<implementation_steps>` with phases or milestones
- [ ] Has `<success_criteria>` for completion verification

### 2. Strengths

Identify what is well-defined in this spec:
- Clear project scope
- Detailed feature descriptions
- Appropriate technology choices
- Realistic feature count
- Good structure and organization

### 3. Improvements Needed

Suggest specific improvements that would make the spec better:
- Missing details that should be added
- Unclear descriptions that need clarification
- Better organization suggestions
- Feature count adjustments if unrealistic

### 4. Critical Issues

Identify any blocking problems that MUST be fixed:
- Missing required sections
- Contradictory requirements
- Technically infeasible requests
- Security concerns in the design
- Unrealistic scope (too many/few features)

### 5. Quality Score

Rate the spec quality from 0-100 based on:
- **Completeness (40%)**: Are all required sections present and filled?
- **Clarity (30%)**: Is the spec clear and unambiguous?
- **Technical Feasibility (30%)**: Is the spec realistic and achievable?

## Output Format

Provide your analysis as a JSON object with the following structure:

```json
{
  "strengths": [
    "List specific things that are well-defined in this spec"
  ],
  "improvements": [
    "List specific suggestions for improvement (not blocking)"
  ],
  "critical_issues": [
    "List any blocking problems that MUST be fixed before proceeding"
  ],
  "suggested_changes": {
    "project_name": "suggested name if missing or unclear",
    "feature_count": "suggested count if unrealistic",
    "missing_sections": ["list of sections that should be added"],
    "tech_stack_notes": "any concerns about technology choices"
  },
  "quality_score": 75,
  "summary": "One paragraph summary of the overall spec quality"
}
```

Output ONLY the JSON object, no additional text or explanation.

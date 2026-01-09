# Add Spec Command

Add an additional app specification to an existing project. This allows you to extend a project with new features (e.g., adding frontend spec to a backend project).

## Usage

When the user invokes `/add-spec`, guide them through creating an additional specification for their project.

## Interactive Flow

### Step 1: Identify the Project

First, confirm which project to add the spec to:

```
Which project would you like to add a spec to?
Current project directory: {project_dir}
```

### Step 2: Name the Spec

Ask for a name that describes this part of the project:

```
What should this spec be called?

Examples:
- "frontend" - For React/Vue/UI components
- "backend" - For API/server code
- "mobile" - For React Native/Flutter app
- "database" - For schema/migrations
- "infrastructure" - For DevOps/deployment
```

### Step 3: Check for Extensions

Ask if this builds on existing specs:

```
Does this spec extend or depend on another spec?

Current specs:
- main (110 features)

Options:
1. Yes, extends "main" (features will come after main)
2. No, independent spec
```

### Step 4: Gather Requirements

Use the same interactive process as `/create-spec`:

1. **Purpose**: What is the goal of this addition?
2. **Technology**: What frameworks/tools to use?
3. **Features**: What specific features should be implemented?
4. **Integration**: How does this integrate with existing code?

### Step 5: Generate Spec

Create the spec in XML format:

```xml
<project_specification>
  <metadata>
    <spec_name>frontend</spec_name>
    <extends>main</extends>
    <created_at>2026-01-09T12:00:00Z</created_at>
  </metadata>

  <overview>
    <name>MyApp Frontend</name>
    <description>React-based frontend for the MyApp backend API</description>
    <stack>
      <frontend>React 18, TypeScript, TailwindCSS</frontend>
      <state>Zustand</state>
      <routing>React Router</routing>
    </stack>
  </overview>

  <features>
    <category name="UI Components">
      <feature priority="1">
        <name>Header Component</name>
        <description>Navigation header with logo and menu</description>
        <test_steps>
          <step>Header renders without errors</step>
          <step>Navigation links work correctly</step>
          <step>Mobile menu toggles properly</step>
        </test_steps>
      </feature>
      <!-- More features... -->
    </category>
  </features>
</project_specification>
```

### Step 6: Save and Register

Save the spec file and register it in the manifest:

```python
from prompts import add_spec_file

# Save the spec
spec_path = add_spec_file(
    project_dir=project_dir,
    spec_name="frontend",
    content=spec_content,
    extends="main"
)

print(f"Created spec at: {spec_path}")
```

### Step 7: Confirm Next Steps

Explain what happens next:

```
✅ Spec "frontend" has been added!

File: {project_dir}/prompts/app_spec_frontend.txt
Manifest: {project_dir}/prompts/.spec_manifest.json

Next steps:
1. Review the spec file and make any adjustments
2. Start the agent - it will process features from all specs
3. New features will be tagged with source_spec="frontend"

To run the initializer for just this spec:
python autonomous_agent_demo.py --project-dir {project_name} --spec frontend
```

## Example Session

```
User: /add-spec
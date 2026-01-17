# Contributing to Auto-Agent-Harness

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We're building something together.

## How to Contribute

### Reporting Bugs

1. Check existing [issues](https://github.com/nek1987/auto-agent-harness/issues) first
2. Create a new issue with:
   - Clear title describing the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)

### Suggesting Features

1. Check existing issues for similar suggestions
2. Create a new issue with:
   - Clear description of the feature
   - Use case / motivation
   - Proposed implementation (optional)

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Run tests and linting
5. Commit with clear messages
6. Push and create a Pull Request

## Development Setup

### Backend

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/auto-agent-harness.git
cd auto-agent-harness

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
python test_security.py
```

### Frontend

```bash
cd apps/ui
npm install
npm run dev      # Development server
npm run lint     # Check for issues
npm run build    # Production build
```

## Code Style

### Python

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Write docstrings for public functions/classes
- Keep functions focused and small

```python
def create_checkpoint(
    name: str,
    feature_id: Optional[int] = None,
) -> Checkpoint:
    """
    Create a new checkpoint.

    Args:
        name: Checkpoint name/description
        feature_id: Current feature being worked on

    Returns:
        Created checkpoint object
    """
    ...
```

### TypeScript/React

- Use TypeScript strict mode
- Prefer functional components with hooks
- Use descriptive variable names
- Keep components small and focused

```typescript
interface FeatureCardProps {
  feature: Feature;
  onStatusChange: (id: number, status: string) => void;
}

export function FeatureCard({ feature, onStatusChange }: FeatureCardProps) {
  // ...
}
```

## Project Structure

### Adding New Protection Mechanisms

Add to `lib/` directory:

```python
# lib/your_module.py
"""
Your Module
===========

Brief description of what this module does.
"""

class YourClass:
    """Docstring explaining the class."""

    def __init__(self, config: YourConfig):
        ...
```

Export in `lib/__init__.py`:

```python
from .your_module import YourClass

__all__ = [
    ...,
    "YourClass",
]
```

### Adding New API Endpoints

1. Create router in `apps/server/routers/`:

```python
# apps/server/routers/your_router.py
from fastapi import APIRouter, Depends
from apps.server.services.auth_service import get_current_user

router = APIRouter(prefix="/your-endpoint", tags=["your-tag"])

@router.get("/")
async def get_items(user: dict = Depends(get_current_user)):
    ...
```

2. Register in `apps/server/main.py`:

```python
from apps.server.routers.your_router import router as your_router
app.include_router(your_router, prefix="/api")
```

### Adding New UI Components

1. Create component in `apps/ui/src/components/`:

```typescript
// apps/ui/src/components/YourComponent.tsx
interface YourComponentProps {
  // props
}

export function YourComponent({ ... }: YourComponentProps) {
  return (
    // JSX
  );
}
```

2. Use neobrutalism design system (see `apps/ui/src/styles/globals.css`)

## Testing

### Security Tests

```bash
python test_security.py
```

### Manual Testing

1. Start the server: `python start_ui.py`
2. Open UI at `http://localhost:5173`
3. Test your changes

### Testing Protection Layer

```python
# Test loop detection
from lib import LoopDetector, create_action_from_tool_call

detector = LoopDetector(exact_threshold=3)
for i in range(5):
    action = create_action_from_tool_call("Edit", {"file_path": "test.py"})
    pattern = detector.record_action(action)
    if pattern:
        print(f"Loop detected: {pattern.description}")
```

## Commit Messages

Use clear, descriptive commit messages:

```
feat: add checkpoint rollback functionality

- Add rollback method to CheckpointManager
- Support git reset and database restore
- Add tests for rollback scenarios
```

Prefixes:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `refactor:` - Code change that doesn't add feature or fix bug
- `test:` - Adding tests
- `chore:` - Maintenance tasks

## License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0 license.

## Questions?

Open an issue with the `question` label or reach out to maintainers.

Thank you for contributing!

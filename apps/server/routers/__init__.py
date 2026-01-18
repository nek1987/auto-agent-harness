"""
API Routers
===========

FastAPI routers for different API endpoints.
"""

from .agent import router as agent_router
from .assistant_chat import router as assistant_chat_router
from .auth import router as auth_router
from .feature_analyze import router as feature_analyze_router
from .features import router as features_router
from .filesystem import router as filesystem_router
from .projects import router as projects_router
from .spec_creation import router as spec_creation_router
from .spec_import import router as spec_import_router
from .spec_update import router as spec_update_router
from .skills_analysis import router as skills_analysis_router
from .redesign import router as redesign_router
from .component_reference import router as component_reference_router

__all__ = [
    "auth_router",
    "projects_router",
    "features_router",
    "agent_router",
    "spec_creation_router",
    "spec_import_router",
    "spec_update_router",
    "filesystem_router",
    "assistant_chat_router",
    "feature_analyze_router",
    "skills_analysis_router",
    "redesign_router",
    "component_reference_router",
]

"""Local, dependency-free LoomQ research workbench.

The package deliberately keeps the HTTP server out of ``__init__`` so that
``python -m loomq.ui.server`` starts without import-time side effects.
"""

from .service import WorkbenchService
from .workspace import WorkspaceSession

__all__ = ["WorkbenchService", "WorkspaceSession"]

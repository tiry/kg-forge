"""
Pipeline hooks for entity processing.

Provides hook registry and interactive session support,
plus modular normalization and deduplication hooks.
"""

# Import hook registry components from hooks.py module
# We need to import from the .py file,not this package
import sys
import importlib.util
from pathlib import Path

# Load hooks.py module directly to make classes available
_hooks_py_path = Path(__file__).parent.parent / "hooks.py"
_spec = importlib.util.spec_from_file_location("kg_forge.pipeline._hooks_module", _hooks_py_path)
_hooks_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hooks_module)

# Re-export classes from hooks.py
InteractiveSession = _hooks_module.InteractiveSession
HookRegistry = _hooks_module.HookRegistry
get_hook_registry = _hooks_module.get_hook_registry

# Import modular hook modules
from kg_forge.pipeline.hooks.normalization import basic, dictionary
from kg_forge.pipeline.hooks.deduplication import fuzzy

__all__ = [
    'InteractiveSession',
    'HookRegistry', 
    'get_hook_registry',
    'basic',
    'dictionary',
    'fuzzy',
]

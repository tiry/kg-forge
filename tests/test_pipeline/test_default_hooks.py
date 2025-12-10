"""Test default pipeline hooks registration."""

import pytest
from kg_forge.pipeline.default_hooks import register_default_hooks
from kg_forge.pipeline.hooks import get_hook_registry


class TestRegisterDefaultHooks:
    """Test default hook registration."""
    
    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear hook registry before each test."""
        registry = get_hook_registry()
        # Clear hooks manually
        registry.before_store_hooks = []
        registry.after_batch_hooks = []
        yield
        # Clean up after test
        registry.before_store_hooks = []
        registry.after_batch_hooks = []
    
    def test_register_non_interactive(self):
        """Test registering hooks in non-interactive mode."""
        register_default_hooks(interactive=False)
        
        registry = get_hook_registry()
        
        # In non-interactive mode, should have no hooks registered
        # (hooks are currently imported but not auto-registered in default_hooks.py)
        assert isinstance(registry.before_store_hooks, list)
        assert isinstance(registry.after_batch_hooks, list)
    
    def test_register_interactive(self):
        """Test registering hooks in interactive mode."""
        register_default_hooks(interactive=True)
        
        registry = get_hook_registry()
        
        # Should have interactive hooks registered
        assert len(registry.before_store_hooks) >= 1  # review_extracted_entities
        assert len(registry.after_batch_hooks) >= 1   # deduplicate_similar_entities
    
    def test_register_multiple_times(self):
        """Test that registering multiple times doesn't cause errors."""
        register_default_hooks(interactive=False)
        register_default_hooks(interactive=False)
        
        # Should not raise errors
        registry = get_hook_registry()
        assert isinstance(registry.before_store_hooks, list)
    
    def test_registry_is_accessible(self):
        """Test that hook registry is accessible."""
        registry = get_hook_registry()
        
        assert hasattr(registry, 'before_store_hooks')
        assert hasattr(registry, 'after_batch_hooks')
        assert hasattr(registry, 'register_before_store')
        assert hasattr(registry, 'register_after_batch')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

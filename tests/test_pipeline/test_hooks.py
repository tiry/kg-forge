"""Tests for pipeline hooks system."""

import pytest
from unittest.mock import Mock, MagicMock

from kg_forge.pipeline.hooks import (
    InteractiveSession,
    HookRegistry,
    get_hook_registry,
)
from kg_forge.models.extraction import ExtractedEntity
from kg_forge.models.document import ParsedDocument


class TestInteractiveSession:
    """Tests for InteractiveSession."""
    
    def test_disabled_session_returns_defaults(self):
        """Test that disabled session returns default values."""
        session = InteractiveSession(enabled=False)
        
        assert session.enabled is False
        assert session.confirm("Test question?", default=True) is True
        assert session.confirm("Test question?", default=False) is False
        assert session.prompt("Enter value:", default="default") == "default"
        assert session.choose("Pick one:", ["a", "b"], default="b") == "b"
    
    def test_enabled_session_flag(self):
        """Test that enabled flag is set correctly."""
        session = InteractiveSession(enabled=True)
        assert session.enabled is True
        
        session = InteractiveSession(enabled=False)
        assert session.enabled is False


class TestHookRegistry:
    """Tests for HookRegistry."""
    
    def test_empty_registry(self):
        """Test newly created registry is empty."""
        registry = HookRegistry()
        
        assert len(registry.before_store_hooks) == 0
        assert len(registry.after_batch_hooks) == 0
    
    def test_register_before_store_hook(self):
        """Test registering before_store hook."""
        registry = HookRegistry()
        
        def test_hook(doc, entities, graph_client):
            return entities
        
        registry.register_before_store(test_hook)
        
        assert len(registry.before_store_hooks) == 1
        assert registry.before_store_hooks[0] == test_hook
    
    def test_register_after_batch_hook(self):
        """Test registering after_batch hook."""
        registry = HookRegistry()
        
        def test_hook(entities, graph_client, interactive):
            pass
        
        registry.register_after_batch(test_hook)
        
        assert len(registry.after_batch_hooks) == 1
        assert registry.after_batch_hooks[0] == test_hook
    
    def test_run_before_store_hooks(self):
        """Test running before_store hooks in sequence."""
        registry = HookRegistry()
        
        # Create mock entities
        entity1 = ExtractedEntity(
            entity_type="Product",
            name="K8s",
            confidence=0.9,
            properties={}
        )
        entities = [entity1]
        
        # Create a hook that modifies entity name
        def normalize_hook(doc, entities, graph_client):
            for entity in entities:
                if entity.name == "K8s":
                    entity.name = "Kubernetes"
            return entities
        
        registry.register_before_store(normalize_hook)
        
        # Run hooks
        doc = Mock(spec=ParsedDocument)
        graph_client = Mock()
        result = registry.run_before_store(doc, entities, graph_client)
        
        assert len(result) == 1
        assert result[0].name == "Kubernetes"
    
    def test_run_before_store_hooks_chain(self):
        """Test that before_store hooks form a chain."""
        registry = HookRegistry()
        
        entity1 = ExtractedEntity(
            entity_type="Product",
            name="test",
            confidence=0.9,
            properties={}
        )
        entities = [entity1]
        
        # Hook 1: Convert to uppercase
        def hook1(doc, entities, graph_client):
            for entity in entities:
                entity.name = entity.name.upper()
            return entities
        
        # Hook 2: Add prefix
        def hook2(doc, entities, graph_client):
            for entity in entities:
                entity.name = "PREFIX_" + entity.name
            return entities
        
        registry.register_before_store(hook1)
        registry.register_before_store(hook2)
        
        doc = Mock(spec=ParsedDocument)
        graph_client = Mock()
        result = registry.run_before_store(doc, entities, graph_client)
        
        # Should be: test -> TEST -> PREFIX_TEST
        assert result[0].name == "PREFIX_TEST"
    
    def test_run_after_batch_hooks(self):
        """Test running after_batch hooks."""
        registry = HookRegistry()
        
        hook_called = {'count': 0}
        
        def test_hook(entities, graph_client, interactive):
            hook_called['count'] += 1
        
        registry.register_after_batch(test_hook)
        
        entities = []
        graph_client = Mock()
        interactive = InteractiveSession(enabled=False)
        
        registry.run_after_batch(entities, graph_client, interactive)
        
        assert hook_called['count'] == 1
    
    def test_hook_error_handling(self):
        """Test that hook errors don't stop pipeline."""
        registry = HookRegistry()
        
        # Hook that raises an error
        def failing_hook(doc, entities, graph_client):
            raise ValueError("Test error")
        
        # Hook that works
        def working_hook(doc, entities, graph_client):
            return entities
        
        registry.register_before_store(failing_hook)
        registry.register_before_store(working_hook)
        
        doc = Mock(spec=ParsedDocument)
        graph_client = Mock()
        entities = []
        
        # Should not raise an exception
        result = registry.run_before_store(doc, entities, graph_client)
        
        # Should still return entities (from working hook)
        assert result == entities


class TestGlobalRegistry:
    """Tests for global hook registry."""
    
    def test_get_hook_registry_returns_singleton(self):
        """Test that get_hook_registry returns the same instance."""
        registry1 = get_hook_registry()
        registry2 = get_hook_registry()
        
        assert registry1 is registry2

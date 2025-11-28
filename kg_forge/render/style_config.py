"""
Visual styling configuration for graph rendering with neovis.js.
"""

from typing import Any, Dict, List
from kg_forge.render.graph_query import NodeRecord, RelationshipRecord


# Default color palette
COLORS = {
    "doc": "#1f77b4",           # Blue
    "entity_product": "#2ca02c", # Green  
    "entity_team": "#ff7f0e",   # Orange
    "entity_technology": "#9467bd", # Purple
    "entity_component": "#8c564b", # Brown
    "entity_workstream": "#e377c2", # Pink
    "entity_domain": "#7f7f7f",  # Gray
    "entity_default": "#d62728", # Red fallback
    "relationship_mentions": "#cccccc", # Light gray
    "relationship_works_on": "#2ca02c", # Green
    "relationship_collaborates": "#1f77b4", # Blue
    "relationship_uses": "#9467bd", # Purple
    "relationship_default": "#666666", # Dark gray
}


# Default node styles configuration
DEFAULT_NODE_STYLES = {
    "Doc": {
        "color": COLORS["doc"],
        "shape": "box",
        "font": {"color": "white", "size": 14},
        "size": 25,
        "borderWidth": 2,
        "borderColor": "#0f5a8a"
    },
    "Entity": {
        "color": COLORS["entity_default"],
        "shape": "dot", 
        "font": {"color": "black", "size": 12},
        "size": 20,
        "borderWidth": 1,
        "borderColor": "#333333"
    }
}


# Entity type specific styles
ENTITY_TYPE_STYLES = {
    "Product": {
        "color": COLORS["entity_product"],
        "borderColor": "#1a6b1a"
    },
    "EngineeringTeam": {
        "color": COLORS["entity_team"],
        "borderColor": "#cc5500"
    },
    "Technology": {
        "color": COLORS["entity_technology"],
        "borderColor": "#6b4395"
    },
    "Component": {
        "color": COLORS["entity_component"],
        "borderColor": "#5a3a31"
    },
    "Workstream": {
        "color": COLORS["entity_workstream"],
        "borderColor": "#b85398"
    },
    "AiMlDomain": {
        "color": COLORS["entity_domain"],
        "borderColor": "#5a5a5a"
    }
}


# Default relationship styles configuration
DEFAULT_RELATIONSHIP_STYLES = {
    "MENTIONS": {
        "color": COLORS["relationship_mentions"],
        "width": 1,
        "arrows": "to",
        "dashes": False,
        "font": {"size": 10, "color": "#666666"}
    },
    "WORKS_ON": {
        "color": COLORS["relationship_works_on"],
        "width": 2,
        "arrows": "to", 
        "dashes": False,
        "font": {"size": 12, "color": "#2ca02c"}
    },
    "COLLABORATES_WITH": {
        "color": COLORS["relationship_collaborates"],
        "width": 2,
        "arrows": "to",
        "dashes": False,
        "font": {"size": 12, "color": "#1f77b4"}
    },
    "USES": {
        "color": COLORS["relationship_uses"], 
        "width": 2,
        "arrows": "to",
        "dashes": True,
        "font": {"size": 12, "color": "#9467bd"}
    }
}


class StyleConfig:
    """
    Configuration manager for visual styling of graph elements.
    
    Provides methods to generate neovis.js compatible style configurations
    for nodes and relationships based on their types and properties.
    """
    
    def __init__(self, custom_styles: Dict[str, Any] = None):
        """
        Initialize with optional custom style overrides.
        
        Args:
            custom_styles: Dictionary with custom style configurations
        """
        self.custom_styles = custom_styles or {}
    
    def get_node_style(self, node: NodeRecord) -> Dict[str, Any]:
        """
        Get neovis.js style configuration for a node.
        
        Args:
            node: Node to generate style for
            
        Returns:
            Dictionary with neovis.js style properties
        """
        # Start with base style for primary label
        primary_label = node.primary_label
        style = DEFAULT_NODE_STYLES.get(primary_label, DEFAULT_NODE_STYLES["Entity"]).copy()
        
        # Apply entity type specific styling
        if primary_label == "Entity":
            entity_type = node.properties.get("entity_type")
            if entity_type and entity_type in ENTITY_TYPE_STYLES:
                type_style = ENTITY_TYPE_STYLES[entity_type]
                style.update(type_style)
        
        # Calculate size based on properties
        style["size"] = self._calculate_node_size(node)
        
        # Apply custom overrides
        if primary_label in self.custom_styles:
            style.update(self.custom_styles[primary_label])
        
        return style
    
    def get_relationship_style(self, relationship: RelationshipRecord) -> Dict[str, Any]:
        """
        Get neovis.js style configuration for a relationship.
        
        Args:
            relationship: Relationship to generate style for
            
        Returns:
            Dictionary with neovis.js style properties
        """
        rel_type = relationship.type
        
        # Get base style for relationship type
        if rel_type in DEFAULT_RELATIONSHIP_STYLES:
            style = DEFAULT_RELATIONSHIP_STYLES[rel_type].copy()
        else:
            # Default fallback style
            style = {
                "color": COLORS["relationship_default"],
                "width": 1,
                "arrows": "to",
                "dashes": False,
                "font": {"size": 10, "color": "#666666"}
            }
        
        # Adjust width based on confidence if available
        confidence = relationship.properties.get("confidence")
        if confidence is not None:
            base_width = style.get("width", 1)
            style["width"] = max(1, base_width * confidence)
        
        # Apply custom overrides
        if rel_type in self.custom_styles:
            style.update(self.custom_styles[rel_type])
        
        return style
    
    def generate_neovis_config(
        self,
        nodes: List[NodeRecord],
        relationships: List[RelationshipRecord]
    ) -> Dict[str, Any]:
        """
        Generate complete neovis.js configuration object.
        
        Args:
            nodes: List of nodes in the graph
            relationships: List of relationships in the graph
            
        Returns:
            Complete neovis.js configuration dictionary
        """
        # Collect unique labels and relationship types
        node_labels = set()
        relationship_types = set()
        
        for node in nodes:
            node_labels.update(node.labels)
        
        for rel in relationships:
            relationship_types.add(rel.type)
        
        # Generate label configurations
        labels_config = {}
        for label in node_labels:
            if label == "Doc":
                labels_config[label] = {
                    "caption": "doc_id",
                    "size": "pagerank",
                    "color": COLORS["doc"],
                    "font": {"color": "white"},
                    "shape": "box"
                }
            elif label == "Entity":
                labels_config[label] = {
                    "caption": "name",
                    "size": "degree", 
                    "color": COLORS["entity_default"],
                    "font": {"color": "black"},
                    "shape": "dot"
                }
        
        # Generate relationship configurations
        relationships_config = {}
        for rel_type in relationship_types:
            if rel_type in DEFAULT_RELATIONSHIP_STYLES:
                style = DEFAULT_RELATIONSHIP_STYLES[rel_type]
                relationships_config[rel_type] = {
                    "thickness": style["width"],
                    "color": style["color"],
                    "caption": True if rel_type != "MENTIONS" else False,
                    "font": style["font"]
                }
            else:
                relationships_config[rel_type] = {
                    "thickness": 1,
                    "color": COLORS["relationship_default"],
                    "caption": True,
                    "font": {"size": 10, "color": "#666666"}
                }
        
        # Build complete config
        config = {
            "container_id": "viz",
            "server_url": None,  # Use embedded data mode
            "server_user": None,
            "server_password": None,
            "labels": labels_config,
            "relationships": relationships_config,
            "initial_cypher": None,  # Use embedded data
            "console_debug": False,
            "encrypted": False,
            "trust": "TRUST_ALL_CERTIFICATES",
            "arrows": True
        }
        
        return config
    
    def _calculate_node_size(self, node: NodeRecord) -> int:
        """
        Calculate node size based on properties and importance.
        
        Args:
            node: Node to calculate size for
            
        Returns:
            Size value for the node
        """
        base_size = 20
        
        # Doc nodes are slightly larger
        if node.primary_label == "Doc":
            base_size = 25
        
        # Adjust size based on confidence for entities
        if node.primary_label == "Entity":
            confidence = node.properties.get("confidence", 1.0)
            base_size = int(base_size * (0.7 + 0.3 * confidence))
        
        return max(15, min(40, base_size))


# Global instance for default styling
default_style_config = StyleConfig()
"""
HTML template generation with embedded graph data for visualization.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2
from neo4j.time import DateTime as Neo4jDateTime

from kg_forge.render.graph_query import GraphData, NodeRecord, RelationshipRecord, SeedConfig
from kg_forge.render.style_config import StyleConfig, default_style_config

logger = logging.getLogger(__name__)


class HtmlBuilder:
    """
    Generates self-contained HTML files with embedded graph data and neovis.js visualization.
    
    Creates static HTML files that include all necessary data and configuration
    to render interactive graph visualizations without requiring a live Neo4j connection.
    """
    
    def __init__(self, style_config: StyleConfig = None):
        """
        Initialize HTML builder with styling configuration.
        
        Args:
            style_config: Custom style configuration (uses default if None)
        """
        self.style_config = style_config or default_style_config
        self._setup_jinja_env()
    
    def _setup_jinja_env(self):
        """Set up Jinja2 environment with template loader."""
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
    
    def generate_html(
        self,
        graph_data: GraphData,
        output_path: Path,
        namespace: Optional[str] = None,
        seed_info: Optional[str] = None,
        depth: int = 2,
        max_nodes: Optional[int] = None,
        max_nodes_reached: bool = False
    ) -> None:
        """
        Generate complete HTML visualization file.
        
        Args:
            graph_data: Graph data to embed in HTML
            output_path: Path where HTML file should be written
            namespace: Namespace being visualized (for display)
            seed_info: Human-readable seed information for display
            depth: Traversal depth used (for display)
            max_nodes: Node limit applied (for display)
            max_nodes_reached: Whether node limit was reached
            
        Raises:
            IOError: If HTML file cannot be written
            jinja2.TemplateError: If template rendering fails
        """
        logger.info(f"Generating HTML visualization: {output_path}")
        
        try:
            # Prepare template variables
            template_vars = self._prepare_template_variables(
                graph_data, namespace, seed_info, depth, max_nodes, max_nodes_reached
            )
            
            # Render HTML template
            template = self.jinja_env.get_template('graph.html.j2')
            html_content = template.render(**template_vars)
            
            # Write to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_content, encoding='utf-8')
            
            file_size = output_path.stat().st_size
            logger.info(f"HTML file generated: {output_path} ({file_size:,} bytes)")
            
        except jinja2.TemplateError as e:
            logger.error(f"Template rendering error: {e}")
            raise
        except IOError as e:
            logger.error(f"Error writing HTML file: {e}")
            raise
    
    def _prepare_template_variables(
        self,
        graph_data: GraphData,
        namespace: Optional[str] = None,
        seed_info: Optional[str] = None,
        depth: int = 2,
        max_nodes: Optional[int] = None,
        max_nodes_reached: bool = False
    ) -> Dict[str, Any]:
        """
        Prepare all variables needed for template rendering.
        
        Args:
            graph_data: Graph data to embed
            namespace: Namespace being visualized
            seed_info: Human-readable seed information
            depth: Traversal depth used
            max_nodes: Node limit applied
            max_nodes_reached: Whether limit was reached
            
        Returns:
            Dictionary of template variables
        """
        # Serialize graph data for JSON embedding
        graph_data_json = self._serialize_graph_data(graph_data)
        
        # Generate neovis.js configuration
        neovis_config = self.style_config.generate_neovis_config(
            graph_data.nodes, graph_data.relationships
        )
        neovis_config_json = json.dumps(neovis_config, indent=2)
        
        # Prepare template context
        template_vars = {
            'namespace': namespace,
            'graph_data': graph_data,
            'graph_data_json': graph_data_json,
            'neovis_config_json': neovis_config_json,
            'generation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'seed_info': seed_info,
            'depth': depth,
            'max_nodes': max_nodes,
            'max_nodes_reached': max_nodes_reached
        }
        
        return template_vars
    
    def _serialize_graph_data(self, graph_data: GraphData) -> str:
        """
        Serialize graph data to JSON string for embedding in HTML.
        
        Args:
            graph_data: Graph data to serialize
            
        Returns:
            JSON string representation of graph data
        """
        # Convert to JSON-serializable format
        serialized = {
            'nodes': [self._serialize_node(node) for node in graph_data.nodes],
            'relationships': [self._serialize_relationship(rel) for rel in graph_data.relationships]
        }
        
        return json.dumps(serialized, indent=2)
    
    def _serialize_node(self, node: NodeRecord) -> Dict[str, Any]:
        """
        Serialize a node record to JSON-compatible format.
        
        Args:
            node: Node to serialize
            
        Returns:
            Dictionary representation of node
        """
        # Filter properties to keep payload manageable
        filtered_properties = self._filter_node_properties(node.properties)
        
        return {
            'id': node.id,
            'labels': node.labels,
            'properties': filtered_properties
        }
    
    def _serialize_relationship(self, relationship: RelationshipRecord) -> Dict[str, Any]:
        """
        Serialize a relationship record to JSON-compatible format.
        
        Args:
            relationship: Relationship to serialize
            
        Returns:
            Dictionary representation of relationship
        """
        return {
            'id': relationship.id,
            'start_node': relationship.start_node,
            'end_node': relationship.end_node,
            'type': relationship.type,
            'properties': self._serialize_properties(relationship.properties)
        }
    
    def _filter_node_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter node properties to include only essential ones for visualization.
        
        Args:
            properties: Original node properties
            
        Returns:
            Filtered properties dictionary
        """
        # Essential properties to always include
        essential_props = [
            'name', 'doc_id', 'entity_type', 'namespace', 
            'confidence', 'title', 'source_file'
        ]
        
        # Large properties to exclude
        exclude_props = [
            'content', 'curated_text', 'text', 'content_hash'
        ]
        
        filtered = {}
        
        for key, value in properties.items():
            # Skip excluded properties
            if key in exclude_props:
                continue
            
            # Always include essential properties
            if key in essential_props:
                filtered[key] = self._serialize_value(value)
                continue
            
            # Include other properties but limit string length
            if isinstance(value, str) and len(value) > 200:
                filtered[key] = value[:200] + "..."
            else:
                # Convert DateTime objects to ISO strings for JSON serialization
                filtered[key] = self._serialize_value(value)
        
        return filtered
    
    def generate_seed_info(self, seeds: SeedConfig) -> str:
        """
        Generate human-readable seed information for display.
        
        Args:
            seeds: Seed configuration used
            
        Returns:
            Human-readable string describing seeds
        """
        if seeds.is_empty:
            return "Recent documents"
        
        parts = []
        
        if seeds.doc_ids:
            if len(seeds.doc_ids) == 1:
                parts.append(f"Document '{seeds.doc_ids[0]}'")
            else:
                parts.append(f"{len(seeds.doc_ids)} documents")
        
        if seeds.entities:
            if len(seeds.entities) == 1:
                entity = seeds.entities[0]
                parts.append(f"Entity '{entity['name']}' ({entity['type']})")
            else:
                parts.append(f"{len(seeds.entities)} entities")
        
        return ", ".join(parts)
    
    def _serialize_value(self, value: Any) -> Any:
        """
        Serialize a single value for JSON compatibility.
        
        Args:
            value: Value to serialize
            
        Returns:
            JSON-serializable value
        """
        if isinstance(value, (Neo4jDateTime, datetime)):
            return value.isoformat()
        elif hasattr(value, '__dict__'):
            # Handle other Neo4j types that might not be JSON serializable
            return str(value)
        else:
            return value
    
    def _serialize_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize all properties in a dictionary for JSON compatibility.
        
        Args:
            properties: Properties dictionary to serialize
            
        Returns:
            Dictionary with JSON-serializable values
        """
        return {key: self._serialize_value(value) for key, value in properties.items()}
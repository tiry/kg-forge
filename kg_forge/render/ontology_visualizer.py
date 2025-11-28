"""Ontology visualization using Cytoscape.js for static HTML generation."""

import json
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from jinja2 import Environment, BaseLoader

from kg_forge.entities.models import EntityDefinition
from kg_forge.utils.logging import get_logger

logger = get_logger(__name__)


class OntologyVisualizer:
    """Generates interactive ontology visualizations using Cytoscape.js."""
    
    def __init__(self):
        """Initialize the ontology visualizer."""
        self.jinja_env = Environment(loader=BaseLoader())
    
    def generate_html(
        self,
        entity_definitions: List[EntityDefinition],
        output_path: Path,
        ontology_pack_id: str = "default",
        layout: str = "force-directed",
        include_examples: bool = False,
        theme: str = "light"
    ) -> None:
        """
        Generate HTML file with Cytoscape.js ontology visualization.
        
        Args:
            entity_definitions: List of entity definitions from ontology
            output_path: Path to write HTML file
            ontology_pack_id: ID of the ontology pack being visualized
            layout: Layout algorithm for the graph
            include_examples: Whether to include example entities as nodes
            theme: Visual theme ('light' or 'dark')
        """
        logger.info(f"Generating ontology visualization with {len(entity_definitions)} entity types")
        
        # Build graph data
        graph_data = self._build_graph_data(entity_definitions, include_examples)
        
        # Generate HTML content
        html_content = self._build_html_template(
            graph_data=graph_data,
            ontology_pack_id=ontology_pack_id,
            layout=layout,
            theme=theme,
            stats=self._calculate_stats(graph_data, entity_definitions)
        )
        
        # Write to file
        output_path.write_text(html_content, encoding='utf-8')
        logger.info(f"Ontology visualization written to: {output_path}")
    
    def _build_graph_data(
        self, 
        entity_definitions: List[EntityDefinition], 
        include_examples: bool
    ) -> Dict[str, Any]:
        """
        Build Cytoscape.js graph data from entity definitions.
        
        Args:
            entity_definitions: List of entity definitions
            include_examples: Whether to include example entities
            
        Returns:
            Dictionary with 'nodes' and 'edges' for Cytoscape.js
        """
        nodes = []
        edges = []
        
        # Track entity types for relationship validation
        entity_type_ids = {defn.id for defn in entity_definitions}
        
        # Create nodes for entity types
        for definition in entity_definitions:
            node = {
                'data': {
                    'id': definition.id,
                    'label': definition.name or definition.id,
                    'type': 'entity_type',
                    'description': definition.description or '',
                    'examples_count': len(definition.examples) if definition.examples else 0,
                    'relations_count': len(definition.relations) if definition.relations else 0
                },
                'classes': 'entity-type'
            }
            nodes.append(node)
            
            # Add example nodes if requested
            if include_examples and definition.examples:
                for i, example in enumerate(definition.examples):
                    example_id = f"{definition.id}_example_{i}"
                    example_node = {
                        'data': {
                            'id': example_id,
                            'label': example.title,
                            'type': 'example',
                            'parent_type': definition.id,
                            'description': example.description or ''
                        },
                        'classes': 'example'
                    }
                    nodes.append(example_node)
                    
                    # Connect example to its type
                    example_edge = {
                        'data': {
                            'id': f"{example_id}_to_{definition.id}",
                            'source': example_id,
                            'target': definition.id,
                            'relationship': 'instance_of',
                            'label': 'instance of'
                        },
                        'classes': 'example-relation'
                    }
                    edges.append(example_edge)
        
        # Create edges for relationships
        for definition in entity_definitions:
            if definition.relations:
                for relation in definition.relations:
                    # Validate that target entity type exists
                    if relation.target_type in entity_type_ids:
                        edge_id = f"{definition.id}_{relation.to_label}_{relation.target_type}"
                        edge = {
                            'data': {
                                'id': edge_id,
                                'source': definition.id,
                                'target': relation.target_type,
                                'relationship': relation.to_label,
                                'label': relation.to_label.replace('_', ' ').title(),
                                'reverse_label': relation.from_label.replace('_', ' ').title() if relation.from_label else ''
                            },
                            'classes': 'relation'
                        }
                        edges.append(edge)
                    else:
                        logger.warning(f"Relation target '{relation.target_type}' not found in entity types")
        
        return {
            'nodes': nodes,
            'edges': edges
        }
    
    def _calculate_stats(
        self, 
        graph_data: Dict[str, Any], 
        entity_definitions: List[EntityDefinition]
    ) -> Dict[str, Any]:
        """Calculate statistics for the ontology visualization."""
        entity_type_count = len([n for n in graph_data['nodes'] if n['data']['type'] == 'entity_type'])
        example_count = len([n for n in graph_data['nodes'] if n['data']['type'] == 'example'])
        relation_count = len([e for e in graph_data['edges'] if e['classes'] == 'relation'])
        
        # Calculate relationship density
        max_possible_relations = entity_type_count * (entity_type_count - 1)  # directed graph
        density = (relation_count / max_possible_relations * 100) if max_possible_relations > 0 else 0
        
        return {
            'entity_types': entity_type_count,
            'examples': example_count,
            'relationships': relation_count,
            'density': round(density, 1),
            'total_nodes': len(graph_data['nodes']),
            'total_edges': len(graph_data['edges'])
        }
    
    def _build_html_template(
        self,
        graph_data: Dict[str, Any],
        ontology_pack_id: str,
        layout: str,
        theme: str,
        stats: Dict[str, Any]
    ) -> str:
        """Build the complete HTML template with embedded Cytoscape.js visualization."""
        
        # Convert layout name to Cytoscape.js layout
        layout_configs = {
            'force-directed': {
                'name': 'cose',
                'animate': True,
                'randomize': False,
                'componentSpacing': 100,
                'nodeOverlap': 20,
                'idealEdgeLength': 100,
                'edgeElasticity': 100,
                'nestingFactor': 5,
                'gravity': 80,
                'numIter': 1000,
                'initialTemp': 200,
                'coolingFactor': 0.95,
                'minTemp': 1.0
            },
            'hierarchical': {
                'name': 'dagre',
                'rankDir': 'TB',
                'animate': True,
                'spacingFactor': 1.25,
                'nodeSep': 50,
                'rankSep': 100
            },
            'circular': {
                'name': 'circle',
                'animate': True,
                'radius': 200,
                'spacing': 50
            },
            'grid': {
                'name': 'grid',
                'animate': True,
                'rows': None,
                'cols': None,
                'spacing': 100
            }
        }
        
        layout_config = layout_configs.get(layout, layout_configs['force-directed'])
        
        # Theme configurations
        theme_configs = {
            'light': {
                'background': '#ffffff',
                'entity_type_bg': '#e3f2fd',
                'entity_type_border': '#1976d2',
                'entity_type_text': '#0d47a1',
                'example_bg': '#f3e5f5',
                'example_border': '#7b1fa2',
                'example_text': '#4a148c',
                'relation_color': '#424242',
                'example_relation_color': '#9c27b0',
                'text_color': '#212121',
                'panel_bg': '#f5f5f5',
                'panel_border': '#e0e0e0'
            },
            'dark': {
                'background': '#121212',
                'entity_type_bg': '#1e3a8a',
                'entity_type_border': '#3b82f6',
                'entity_type_text': '#dbeafe',
                'example_bg': '#581c87',
                'example_border': '#a855f7',
                'example_text': '#f3e8ff',
                'relation_color': '#9ca3af',
                'example_relation_color': '#c084fc',
                'text_color': '#f3f4f6',
                'panel_bg': '#1f2937',
                'panel_border': '#374151'
            }
        }
        
        theme_config = theme_configs.get(theme, theme_configs['light'])
        
        template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ontology Visualization - {{ ontology_pack_id }}</title>
    <script src="https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
    <script src="https://unpkg.com/cytoscape-cose-bilkent@4.1.0/cytoscape-cose-bilkent.js"></script>
    <script src="https://unpkg.com/cytoscape-dagre@2.5.0/cytoscape-dagre.js"></script>
    <script src="https://unpkg.com/dagre@0.8.5/dist/dagre.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background-color: {{ theme.background }};
            color: {{ theme.text_color }};
            height: 100vh;
            overflow: hidden;
        }
        
        .header {
            background-color: {{ theme.panel_bg }};
            border-bottom: 1px solid {{ theme.panel_border }};
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 1000;
        }
        
        .header h1 {
            margin: 0;
            font-size: 1.5em;
            font-weight: 600;
        }
        
        .stats {
            display: flex;
            gap: 20px;
            font-size: 0.9em;
        }
        
        .stat {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .stat-value {
            font-weight: bold;
            font-size: 1.2em;
        }
        
        .stat-label {
            color: {{ theme.text_color }}aa;
            font-size: 0.8em;
        }
        
        .container {
            display: flex;
            height: calc(100vh - 60px);
        }
        
        #cy {
            flex: 1;
            background-color: {{ theme.background }};
        }
        
        .sidebar {
            width: 300px;
            background-color: {{ theme.panel_bg }};
            border-left: 1px solid {{ theme.panel_border }};
            padding: 20px;
            overflow-y: auto;
        }
        
        .controls {
            margin-bottom: 20px;
        }
        
        .control-group {
            margin-bottom: 15px;
        }
        
        .control-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
        }
        
        .control-group select, .control-group button {
            width: 100%;
            padding: 8px;
            border: 1px solid {{ theme.panel_border }};
            border-radius: 4px;
            background-color: {{ theme.background }};
            color: {{ theme.text_color }};
        }
        
        .control-group button {
            background-color: {{ theme.entity_type_border }};
            color: white;
            cursor: pointer;
            border: none;
        }
        
        .control-group button:hover {
            opacity: 0.9;
        }
        
        .node-info {
            background-color: {{ theme.background }};
            border: 1px solid {{ theme.panel_border }};
            border-radius: 4px;
            padding: 15px;
            margin-top: 20px;
        }
        
        .node-info h3 {
            margin: 0 0 10px 0;
            color: {{ theme.entity_type_border }};
        }
        
        .node-info p {
            margin: 5px 0;
            line-height: 1.4;
        }
        
        .legend {
            margin-top: 20px;
        }
        
        .legend h4 {
            margin: 0 0 10px 0;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 8px;
            border: 2px solid;
        }
        
        .legend-entity-type {
            background-color: {{ theme.entity_type_bg }};
            border-color: {{ theme.entity_type_border }};
        }
        
        .legend-example {
            background-color: {{ theme.example_bg }};
            border-color: {{ theme.example_border }};
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Ontology: {{ ontology_pack_id }}</h1>
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{{ stats.entity_types }}</div>
                <div class="stat-label">Entity Types</div>
            </div>
            {% if stats.examples > 0 %}
            <div class="stat">
                <div class="stat-value">{{ stats.examples }}</div>
                <div class="stat-label">Examples</div>
            </div>
            {% endif %}
            <div class="stat">
                <div class="stat-value">{{ stats.relationships }}</div>
                <div class="stat-label">Relationships</div>
            </div>
            <div class="stat">
                <div class="stat-value">{{ stats.density }}%</div>
                <div class="stat-label">Density</div>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div id="cy"></div>
        
        <div class="sidebar">
            <div class="controls">
                <div class="control-group">
                    <label for="layout-select">Layout:</label>
                    <select id="layout-select">
                        <option value="force-directed" {{ 'selected' if layout == 'force-directed' }}>Force Directed</option>
                        <option value="hierarchical" {{ 'selected' if layout == 'hierarchical' }}>Hierarchical</option>
                        <option value="circular" {{ 'selected' if layout == 'circular' }}>Circular</option>
                        <option value="grid" {{ 'selected' if layout == 'grid' }}>Grid</option>
                    </select>
                </div>
                
                <div class="control-group">
                    <button id="fit-btn">Fit to View</button>
                </div>
                
                <div class="control-group">
                    <button id="reset-btn">Reset Layout</button>
                </div>
            </div>
            
            <div class="legend">
                <h4>Legend</h4>
                <div class="legend-item">
                    <div class="legend-color legend-entity-type"></div>
                    <span>Entity Type</span>
                </div>
                {% if stats.examples > 0 %}
                <div class="legend-item">
                    <div class="legend-color legend-example"></div>
                    <span>Example</span>
                </div>
                {% endif %}
            </div>
            
            <div id="node-info" class="node-info" style="display: none;">
                <h3 id="node-title"></h3>
                <p id="node-description"></p>
                <div id="node-details"></div>
            </div>
        </div>
    </div>

    <script>
        // Graph data
        const graphData = {{ graph_data | tojson }};
        
        // Layout configurations
        const layoutConfigs = {{ layout_configs | tojson }};
        
        // Initialize Cytoscape
        const cy = cytoscape({
            container: document.getElementById('cy'),
            
            elements: [...graphData.nodes, ...graphData.edges],
            
            style: [
                {
                    selector: 'node.entity-type',
                    style: {
                        'background-color': '{{ theme.entity_type_bg }}',
                        'border-color': '{{ theme.entity_type_border }}',
                        'border-width': 2,
                        'color': '{{ theme.entity_type_text }}',
                        'label': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'font-size': '12px',
                        'font-weight': 'bold',
                        'width': 'mapData(relations_count, 0, 10, 40, 80)',
                        'height': 'mapData(relations_count, 0, 10, 40, 80)',
                        'text-wrap': 'wrap',
                        'text-max-width': 80
                    }
                },
                {
                    selector: 'node.example',
                    style: {
                        'background-color': '{{ theme.example_bg }}',
                        'border-color': '{{ theme.example_border }}',
                        'border-width': 1,
                        'color': '{{ theme.example_text }}',
                        'label': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'font-size': '10px',
                        'width': 30,
                        'height': 30,
                        'text-wrap': 'wrap',
                        'text-max-width': 60
                    }
                },
                {
                    selector: 'edge.relation',
                    style: {
                        'width': 2,
                        'line-color': '{{ theme.relation_color }}',
                        'target-arrow-color': '{{ theme.relation_color }}',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'label': 'data(label)',
                        'font-size': '10px',
                        'text-rotation': 'autorotate',
                        'color': '{{ theme.text_color }}',
                        'text-background-color': '{{ theme.background }}',
                        'text-background-opacity': 0.8,
                        'text-background-padding': 2
                    }
                },
                {
                    selector: 'edge.example-relation',
                    style: {
                        'width': 1,
                        'line-color': '{{ theme.example_relation_color }}',
                        'target-arrow-color': '{{ theme.example_relation_color }}',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'straight',
                        'line-style': 'dashed'
                    }
                },
                {
                    selector: ':selected',
                    style: {
                        'border-width': 3,
                        'border-color': '#ff6b6b'
                    }
                }
            ],
            
            layout: layoutConfigs['{{ layout }}']
        });
        
        // Event handlers
        cy.on('tap', 'node', function(evt) {
            const node = evt.target;
            const data = node.data();
            
            document.getElementById('node-title').textContent = data.label;
            document.getElementById('node-description').textContent = data.description || 'No description available';
            
            let details = '';
            if (data.type === 'entity_type') {
                details = `<p><strong>Type:</strong> Entity Type</p>`;
                details += `<p><strong>ID:</strong> ${data.id}</p>`;
                if (data.relations_count > 0) {
                    details += `<p><strong>Relationships:</strong> ${data.relations_count}</p>`;
                }
                if (data.examples_count > 0) {
                    details += `<p><strong>Examples:</strong> ${data.examples_count}</p>`;
                }
            } else if (data.type === 'example') {
                details = `<p><strong>Type:</strong> Example of ${data.parent_type}</p>`;
            }
            
            document.getElementById('node-details').innerHTML = details;
            document.getElementById('node-info').style.display = 'block';
        });
        
        cy.on('tap', function(evt) {
            if (evt.target === cy) {
                document.getElementById('node-info').style.display = 'none';
            }
        });
        
        // Control handlers
        document.getElementById('layout-select').addEventListener('change', function() {
            const layout = this.value;
            cy.layout(layoutConfigs[layout]).run();
        });
        
        document.getElementById('fit-btn').addEventListener('click', function() {
            cy.fit();
        });
        
        document.getElementById('reset-btn').addEventListener('click', function() {
            const layout = document.getElementById('layout-select').value;
            cy.layout(layoutConfigs[layout]).run();
        });
        
        // Initialize fit
        cy.ready(function() {
            cy.fit();
        });
    </script>
</body>
</html>"""
        
        template_obj = self.jinja_env.from_string(template)
        return template_obj.render(
            ontology_pack_id=ontology_pack_id,
            layout=layout,
            theme=theme_config,
            stats=stats,
            graph_data=graph_data,
            layout_configs=layout_configs
        )
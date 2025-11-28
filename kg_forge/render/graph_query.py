"""
Neo4j subgraph retrieval and filtering for graph rendering.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from kg_forge.graph.neo4j_client import Neo4jClient
from kg_forge.graph.exceptions import Neo4jConnectionError as GraphConnectionError

logger = logging.getLogger(__name__)


@dataclass
class NodeRecord:
    """Represents a node in the graph data structure."""
    
    id: int
    labels: List[str]
    properties: Dict[str, Any]
    
    @property
    def primary_label(self) -> str:
        """Get the primary label for this node."""
        if "Doc" in self.labels:
            return "Doc"
        elif "Entity" in self.labels:
            return "Entity"
        return self.labels[0] if self.labels else "Unknown"
    
    @property
    def display_name(self) -> str:
        """Get the display name for this node."""
        if self.primary_label == "Doc":
            return self.properties.get("doc_id", f"Document {self.id}")
        elif self.primary_label == "Entity":
            return self.properties.get("name", f"Entity {self.id}")
        return str(self.id)


@dataclass  
class RelationshipRecord:
    """Represents a relationship in the graph data structure."""
    
    id: int
    start_node: int
    end_node: int
    type: str
    properties: Dict[str, Any]


@dataclass
class GraphData:
    """Container for complete graph data including nodes and relationships."""
    
    nodes: List[NodeRecord]
    relationships: List[RelationshipRecord]
    
    @property
    def node_count(self) -> int:
        return len(self.nodes)
    
    @property
    def relationship_count(self) -> int:
        return len(self.relationships)
    
    def is_empty(self) -> bool:
        return self.node_count == 0


@dataclass
class SeedConfig:
    """Configuration for seed node selection."""
    
    doc_ids: List[str] = None
    entities: List[Dict[str, str]] = None  # [{"name": "...", "type": "..."}]
    
    def __post_init__(self):
        if self.doc_ids is None:
            self.doc_ids = []
        if self.entities is None:
            self.entities = []
    
    @property
    def is_empty(self) -> bool:
        return len(self.doc_ids) == 0 and len(self.entities) == 0


class GraphQuery:
    """
    Neo4j subgraph retrieval with filtering and traversal logic.
    
    Provides methods to extract filtered subgraphs from Neo4j based on
    namespace, seed nodes, depth limits, and entity type filtering.
    """
    
    def __init__(self, neo4j_client: Neo4jClient):
        """Initialize with Neo4j client."""
        self.client = neo4j_client
    
    def get_subgraph(
        self,
        namespace: str,
        seeds: SeedConfig = None,
        depth: int = 2,
        max_nodes: int = 200,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None
    ) -> GraphData:
        """
        Retrieve filtered subgraph from Neo4j.
        
        Args:
            namespace: Namespace to filter by
            seeds: Seed node configuration (defaults to recent docs if empty)
            depth: Maximum traversal depth from seeds
            max_nodes: Maximum number of nodes to include
            include_types: Entity types to include (None = all)
            exclude_types: Entity types to exclude (None = none)
            
        Returns:
            GraphData containing filtered nodes and relationships
            
        Raises:
            GraphConnectionError: If Neo4j connection fails
        """
        logger.info(f"Starting subgraph query for namespace '{namespace}'")
        
        if seeds is None or seeds.is_empty:
            seeds = self._get_default_seeds(namespace)
            
        if seeds.is_empty:
            logger.warning(f"No seed nodes found for namespace '{namespace}'")
            return GraphData(nodes=[], relationships=[])
        
        try:
            # Get seed nodes from Neo4j
            seed_nodes = self._resolve_seed_nodes(namespace, seeds)
            if not seed_nodes:
                logger.warning("No valid seed nodes found, returning empty graph")
                return GraphData(nodes=[], relationships=[])
            
            # Expand subgraph from seeds
            all_nodes, all_relationships = self._expand_subgraph(
                seed_nodes, namespace, depth, include_types, exclude_types
            )
            
            # Apply node limit while preserving connectivity
            final_nodes, final_relationships = self._apply_node_limit(
                all_nodes, all_relationships, seed_nodes, max_nodes
            )
            
            logger.info(
                f"Subgraph extracted: {len(final_nodes)} nodes, "
                f"{len(final_relationships)} relationships "
                f"(from {len(all_nodes)} total nodes)"
            )
            
            return GraphData(nodes=final_nodes, relationships=final_relationships)
            
        except Exception as e:
            logger.error(f"Error querying subgraph: {e}")
            raise GraphConnectionError(f"Failed to query subgraph: {e}") from e
    
    def _get_default_seeds(self, namespace: str) -> SeedConfig:
        """Get default seed configuration based on recent documents."""
        query = """
        MATCH (d:Doc {namespace: $namespace})
        RETURN d.doc_id as doc_id
        ORDER BY d.last_processed_at DESC, d.doc_id
        LIMIT 10
        """
        
        try:
            with self.client.session() as session:
                result = session.run(query, namespace=namespace)
                doc_ids = [record["doc_id"] for record in result]
                
            logger.debug(f"Found {len(doc_ids)} recent documents for default seeds")
            return SeedConfig(doc_ids=doc_ids)
            
        except Exception as e:
            logger.warning(f"Error finding default seeds: {e}")
            return SeedConfig()
    
    def _resolve_seed_nodes(self, namespace: str, seeds: SeedConfig) -> List[NodeRecord]:
        """Resolve seed configuration to actual Neo4j nodes."""
        seed_nodes = []
        
        # Resolve document seeds
        if seeds.doc_ids:
            doc_query = """
            MATCH (d:Doc {namespace: $namespace})
            WHERE d.doc_id IN $doc_ids
            RETURN id(d) as id, labels(d) as labels, properties(d) as properties
            """
            
            with self.client.session() as session:
                result = session.run(doc_query, namespace=namespace, doc_ids=seeds.doc_ids)
                for record in result:
                    seed_nodes.append(NodeRecord(
                        id=record["id"],
                        labels=record["labels"],
                        properties=record["properties"]
                    ))
        
        # Resolve entity seeds
        if seeds.entities:
            for entity_spec in seeds.entities:
                entity_query = """
                MATCH (e:Entity {namespace: $namespace, entity_type: $entity_type, name: $name})
                RETURN id(e) as id, labels(e) as labels, properties(e) as properties
                """
                
                with self.client.session() as session:
                    result = session.run(
                        entity_query,
                        namespace=namespace,
                        entity_type=entity_spec.get("type"),
                        name=entity_spec.get("name")
                    )
                    for record in result:
                        seed_nodes.append(NodeRecord(
                            id=record["id"],
                            labels=record["labels"],
                            properties=record["properties"]
                        ))
        
        logger.debug(f"Resolved {len(seed_nodes)} seed nodes")
        return seed_nodes
    
    def _expand_subgraph(
        self,
        seed_nodes: List[NodeRecord],
        namespace: str,
        depth: int,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None
    ) -> tuple[List[NodeRecord], List[RelationshipRecord]]:
        """Expand subgraph from seed nodes using BFS traversal."""
        seed_ids = [node.id for node in seed_nodes]
        
        # Build the expansion query
        query = """
        MATCH (seed)
        WHERE id(seed) IN $seed_ids
        CALL {
            WITH seed
            MATCH path = (seed)-[*1..$depth]-(connected)
            WHERE seed.namespace = $namespace 
              AND connected.namespace = $namespace
            RETURN nodes(path) as path_nodes, relationships(path) as path_rels
        }
        WITH collect(DISTINCT path_nodes) as all_node_paths, 
             collect(DISTINCT path_rels) as all_rel_paths
        UNWIND all_node_paths as node_path
        UNWIND node_path as node
        WITH collect(DISTINCT node) as all_nodes, all_rel_paths
        UNWIND all_rel_paths as rel_path  
        UNWIND rel_path as rel
        WITH all_nodes, collect(DISTINCT rel) as all_rels
        RETURN all_nodes, all_rels
        """
        
        try:
            with self.client.session() as session:
                result = session.run(
                    query,
                    seed_ids=seed_ids,
                    namespace=namespace,
                    depth=depth
                )
                
                record = result.single()
                if not record:
                    return seed_nodes, []
                
                # Process nodes
                nodes = []
                for neo4j_node in record["all_nodes"]:
                    node = NodeRecord(
                        id=neo4j_node.id,
                        labels=list(neo4j_node.labels),
                        properties=dict(neo4j_node)
                    )
                    
                    # Apply entity type filtering
                    if self._should_include_node(node, include_types, exclude_types):
                        nodes.append(node)
                
                # Process relationships
                relationships = []
                node_ids = {node.id for node in nodes}
                
                for neo4j_rel in record["all_rels"]:
                    # Only include relationships between included nodes
                    if (neo4j_rel.start_node.id in node_ids and 
                        neo4j_rel.end_node.id in node_ids):
                        
                        rel = RelationshipRecord(
                            id=neo4j_rel.id,
                            start_node=neo4j_rel.start_node.id,
                            end_node=neo4j_rel.end_node.id,
                            type=neo4j_rel.type,
                            properties=dict(neo4j_rel)
                        )
                        relationships.append(rel)
                
                return nodes, relationships
                
        except Exception as e:
            logger.error(f"Error expanding subgraph: {e}")
            return seed_nodes, []
    
    def _should_include_node(
        self,
        node: NodeRecord,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None
    ) -> bool:
        """Check if node should be included based on type filtering."""
        # Always include Doc nodes
        if "Doc" in node.labels:
            return True
        
        # For Entity nodes, check type filtering
        if "Entity" in node.labels:
            entity_type = node.properties.get("entity_type")
            
            if exclude_types and entity_type in exclude_types:
                return False
            
            if include_types and entity_type not in include_types:
                return False
        
        return True
    
    def _apply_node_limit(
        self,
        all_nodes: List[NodeRecord],
        all_relationships: List[RelationshipRecord],
        seed_nodes: List[NodeRecord],
        max_nodes: int
    ) -> tuple[List[NodeRecord], List[RelationshipRecord]]:
        """Apply node limit while preserving connectivity and important nodes."""
        if len(all_nodes) <= max_nodes:
            return all_nodes, all_relationships
        
        logger.warning(
            f"Node limit reached: {len(all_nodes)} > {max_nodes}, "
            f"applying prioritization"
        )
        
        # Calculate node degrees
        node_degrees = {}
        for rel in all_relationships:
            node_degrees[rel.start_node] = node_degrees.get(rel.start_node, 0) + 1
            node_degrees[rel.end_node] = node_degrees.get(rel.end_node, 0) + 1
        
        # Priority ordering: seeds first, then by degree, then by ID
        seed_ids = {node.id for node in seed_nodes}
        
        def node_priority(node: NodeRecord) -> tuple:
            is_seed = node.id in seed_ids
            degree = node_degrees.get(node.id, 0)
            return (not is_seed, -degree, node.id)  # Seeds first, high degree first
        
        # Sort and limit nodes
        sorted_nodes = sorted(all_nodes, key=node_priority)
        final_nodes = sorted_nodes[:max_nodes]
        final_node_ids = {node.id for node in final_nodes}
        
        # Filter relationships to only included nodes
        final_relationships = [
            rel for rel in all_relationships
            if rel.start_node in final_node_ids and rel.end_node in final_node_ids
        ]
        
        logger.info(f"Applied node limit: kept {len(final_nodes)} nodes, "
                   f"{len(final_relationships)} relationships")
        
        return final_nodes, final_relationships
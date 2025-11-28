"""Query command for kg-forge CLI."""

import click
from typing import Optional
from rich.console import Console
from rich.table import Table
import json

from kg_forge.config.settings import get_settings
from kg_forge.graph.neo4j_client import Neo4jClient
from kg_forge.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


@click.group()
@click.option(
    "--namespace", 
    default=None,
    help="Target namespace (alphanumeric only, default from config)"
)
@click.option(
    "--format", 
    "output_format",
    type=click.Choice(["json", "text"], case_sensitive=False),
    default="text",
    help="Output format"
)
@click.option(
    "--max-results", 
    type=int,
    default=10,
    help="Maximum results to return"
)
@click.pass_context
def query(
    ctx: click.Context,
    namespace: Optional[str] = None,
    output_format: str = "text",
    max_results: int = 10
) -> None:
    """
    Query the knowledge graph for entities and documents.
    
    Use subcommands to list types, entities, documents, or find relationships.
    """
    settings = ctx.obj["settings"]
    
    # Use namespace from parameter or default from settings
    target_namespace = namespace or settings.app.default_namespace
    
    # Validate namespace
    try:
        settings.validate_namespace(target_namespace)
    except ValueError as e:
        console.print(f"[red]Invalid namespace: {e}[/red]")
        ctx.exit(1)
    
    # Initialize Neo4j client
    neo4j_client = Neo4jClient(settings)
    
    # Store query context for subcommands
    ctx.obj["query_namespace"] = target_namespace
    ctx.obj["query_format"] = output_format
    ctx.obj["query_max_results"] = max_results
    ctx.obj["neo4j_client"] = neo4j_client


@query.command("list-types")
@click.pass_context
def list_types(ctx: click.Context) -> None:
    """List all entity types in the knowledge graph."""
    namespace = ctx.obj["query_namespace"]
    output_format = ctx.obj["query_format"]
    
    logger.info(f"Listing entity types for namespace: [bold]{namespace}[/bold]")
    neo4j_client = ctx.obj["neo4j_client"]
    
    try:
        # Query distinct entity types from Neo4j
        query = """
        MATCH (e:Entity {namespace: $namespace})
        RETURN DISTINCT e.entity_type as entity_type
        ORDER BY entity_type
        """
        
        results = neo4j_client.execute_query(query, {"namespace": namespace})
        entity_types = [record["entity_type"] for record in results]
        
        if output_format == "json":
            result = {"namespace": namespace, "entity_types": entity_types}
            console.print(json.dumps(result, indent=2))
        else:
            console.print(f"[bold]Entity Types in namespace '{namespace}':[/bold]")
            if entity_types:
                for entity_type in entity_types:
                    console.print(f"  • {entity_type}")
            else:
                console.print("  [yellow]No entity types found[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Error querying entity types: {e}[/red]")
        ctx.exit(1)


@query.command("list-entities")
@click.option(
    "--type", 
    "entity_type",
    required=True,
    help="Entity type to list"
)
@click.pass_context
def list_entities(ctx: click.Context, entity_type: str) -> None:
    """List entities of a specific type."""
    namespace = ctx.obj["query_namespace"]
    output_format = ctx.obj["query_format"]
    max_results = ctx.obj["query_max_results"]
    
    logger.info(f"Listing entities of type '{entity_type}' in namespace: [bold]{namespace}[/bold]")
    neo4j_client = ctx.obj["neo4j_client"]
    
    try:
        # Query entities of specified type from Neo4j
        query = """
        MATCH (e:Entity {namespace: $namespace, entity_type: $entity_type})
        RETURN e.name as name, e.confidence as confidence
        ORDER BY e.confidence DESC, e.name
        LIMIT $max_results
        """
        
        results = neo4j_client.execute_query(query, {
            "namespace": namespace,
            "entity_type": entity_type,
            "max_results": max_results
        })
        
        entities = [
            {
                "name": record["name"],
                "confidence": float(record["confidence"]) if record["confidence"] else 1.0
            }
            for record in results
        ]
        
        if output_format == "json":
            result = {
                "namespace": namespace,
                "entity_type": entity_type,
                "max_results": max_results,
                "entities": entities
            }
            console.print(json.dumps(result, indent=2))
        else:
            console.print(f"[bold]{entity_type} entities in namespace '{namespace}':[/bold]")
            if entities:
                table = Table(show_header=True)
                table.add_column("Name")
                table.add_column("Confidence")
                
                for entity in entities:
                    table.add_row(entity["name"], f"{entity['confidence']:.2f}")
                
                console.print(table)
            else:
                console.print(f"  [yellow]No {entity_type} entities found[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Error querying entities: {e}[/red]")
        ctx.exit(1)


@query.command("list-docs")
@click.pass_context
def list_docs(ctx: click.Context) -> None:
    """List all documents in the knowledge graph."""
    namespace = ctx.obj["query_namespace"]
    output_format = ctx.obj["query_format"]
    max_results = ctx.obj["query_max_results"]
    
    logger.info(f"Listing documents in namespace: [bold]{namespace}[/bold]")
    neo4j_client = ctx.obj["neo4j_client"]
    
    try:
        # Query documents from Neo4j
        query = """
        MATCH (d:Doc {namespace: $namespace})
        RETURN d.doc_id as doc_id, d.source_file as source_path, d.title as title
        ORDER BY d.doc_id
        LIMIT $max_results
        """
        
        results = neo4j_client.execute_query(query, {
            "namespace": namespace,
            "max_results": max_results
        })
        
        documents = [
            {
                "doc_id": record["doc_id"],
                "source_path": record["source_path"] or "unknown",
                "title": record["title"] or "Untitled"
            }
            for record in results
        ]
        
        if output_format == "json":
            result = {
                "namespace": namespace,
                "max_results": max_results,
                "documents": documents
            }
            console.print(json.dumps(result, indent=2))
        else:
            console.print(f"[bold]Documents in namespace '{namespace}':[/bold]")
            if documents:
                table = Table(show_header=True)
                table.add_column("Document ID")
                table.add_column("Source Path")
                table.add_column("Title")
                
                for doc in documents:
                    table.add_row(doc["doc_id"], doc["source_path"], doc["title"])
                
                console.print(table)
            else:
                console.print("  [yellow]No documents found[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Error querying documents: {e}[/red]")
        ctx.exit(1)


@query.command("show-doc")
@click.option(
    "--id", 
    "doc_id",
    required=True,
    help="Document ID to show"
)
@click.pass_context
def show_doc(ctx: click.Context, doc_id: str) -> None:
    """Show document details."""
    namespace = ctx.obj["query_namespace"]
    output_format = ctx.obj["query_format"]
    
    logger.info(f"Showing document '{doc_id}' in namespace: [bold]{namespace}[/bold]")
    neo4j_client = ctx.obj["neo4j_client"]
    
    try:
        # Query document details and mentioned entities from Neo4j
        doc_query = """
        MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})
        RETURN d.doc_id as doc_id, d.source_file as source_path, d.title as title, 
               d.content_hash as content_hash, d.namespace as namespace
        """
        
        entities_query = """
        MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})-[:MENTIONS]->(e:Entity)
        RETURN e.name as name, e.entity_type as type
        ORDER BY e.entity_type, e.name
        """
        
        doc_results = neo4j_client.execute_query(doc_query, {
            "namespace": namespace,
            "doc_id": doc_id
        })
        
        if not doc_results:
            console.print(f"[red]Document '{doc_id}' not found in namespace '{namespace}'[/red]")
            ctx.exit(1)
            
        doc_record = doc_results[0]
        
        entities_results = neo4j_client.execute_query(entities_query, {
            "namespace": namespace,
            "doc_id": doc_id
        })
        
        entities_mentioned = [
            {"name": record["name"], "type": record["type"]}
            for record in entities_results
        ]
        
        doc_data = {
            "doc_id": doc_record["doc_id"],
            "namespace": doc_record["namespace"],
            "source_path": doc_record["source_path"] or "unknown",
            "title": doc_record["title"] or "Untitled",
            "content_hash": doc_record["content_hash"] or "unknown",
            "entities_mentioned": entities_mentioned
        }
        
        if output_format == "json":
            console.print(json.dumps(doc_data, indent=2))
        else:
            console.print(f"[bold]Document: {doc_id}[/bold]")
            console.print(f"Namespace: {namespace}")
            console.print(f"Title: {doc_data['title']}")
            console.print(f"Source Path: {doc_data['source_path']}")
            console.print(f"Content Hash: {doc_data['content_hash'][:12]}...")
            console.print("\n[bold]Entities Mentioned:[/bold]")
            if entities_mentioned:
                for entity in entities_mentioned:
                    console.print(f"  • {entity['name']} ({entity['type']})")
            else:
                console.print("  [yellow]No entities found[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Error querying document: {e}[/red]")
        ctx.exit(1)


@query.command("find-related")
@click.option(
    "--entity", 
    required=True,
    help="Entity name to find relationships for"
)
@click.option(
    "--type", 
    "entity_type",
    required=True,
    help="Entity type"
)
@click.pass_context
def find_related(ctx: click.Context, entity: str, entity_type: str) -> None:
    """Find entities related to the specified entity."""
    namespace = ctx.obj["query_namespace"]
    output_format = ctx.obj["query_format"]
    max_results = ctx.obj["query_max_results"]
    
    logger.info(f"Finding entities related to '{entity}' ({entity_type}) in namespace: [bold]{namespace}[/bold]")
    neo4j_client = ctx.obj["neo4j_client"]
    
    try:
        # Query related entities from Neo4j
        query = """
        MATCH (source:Entity {namespace: $namespace, name: $entity, entity_type: $entity_type})
        MATCH (source)-[r]-(related:Entity)
        WHERE related.namespace = $namespace
        RETURN related.name as entity, related.entity_type as type, type(r) as relationship
        ORDER BY related.entity_type, related.name
        LIMIT $max_results
        """
        
        results = neo4j_client.execute_query(query, {
            "namespace": namespace,
            "entity": entity,
            "entity_type": entity_type,
            "max_results": max_results
        })
        
        related_entities = [
            {
                "entity": record["entity"],
                "type": record["type"],
                "relationship": record["relationship"]
            }
            for record in results
        ]
        
        if output_format == "json":
            result = {
                "namespace": namespace,
                "source_entity": entity,
                "source_type": entity_type,
                "max_results": max_results,
                "related_entities": related_entities
            }
            console.print(json.dumps(result, indent=2))
        else:
            console.print(f"[bold]Entities related to '{entity}' ({entity_type}):[/bold]")
            if related_entities:
                table = Table(show_header=True)
                table.add_column("Entity")
                table.add_column("Type")
                table.add_column("Relationship")
                
                for related in related_entities:
                    table.add_row(related["entity"], related["type"], related["relationship"])
                
                console.print(table)
            else:
                console.print(f"  [yellow]No related entities found for '{entity}'[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Error querying related entities: {e}[/red]")
        ctx.exit(1)

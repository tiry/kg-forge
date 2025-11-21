"""Query command for kg-forge CLI."""

import click
from typing import Optional
from rich.console import Console
from rich.table import Table
import json

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
    
    # Store query context for subcommands
    ctx.obj["query_namespace"] = target_namespace
    ctx.obj["query_format"] = output_format
    ctx.obj["query_max_results"] = max_results


@query.command("list-types")
@click.pass_context
def list_types(ctx: click.Context) -> None:
    """List all entity types in the knowledge graph."""
    namespace = ctx.obj["query_namespace"]
    output_format = ctx.obj["query_format"]
    
    logger.info(f"Listing entity types for namespace: [bold]{namespace}[/bold]")
    
    # TODO: Implement actual query logic in later steps
    mock_types = ["Product", "Component", "Technology", "EngineeringTeam", "Topic"]
    
    if output_format == "json":
        result = {"namespace": namespace, "entity_types": mock_types}
        console.print(json.dumps(result, indent=2))
    else:
        console.print(f"[bold]Entity Types in namespace '{namespace}':[/bold]")
        for entity_type in mock_types:
            console.print(f"  • {entity_type}")
    
    console.print("[yellow]Query functionality will be implemented in Step 4[/yellow]")


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
    
    # TODO: Implement actual query logic in later steps
    mock_entities = [
        {"name": f"Sample {entity_type} 1", "confidence": 0.95},
        {"name": f"Sample {entity_type} 2", "confidence": 0.87}
    ]
    
    if output_format == "json":
        result = {
            "namespace": namespace,
            "entity_type": entity_type,
            "max_results": max_results,
            "entities": mock_entities
        }
        console.print(json.dumps(result, indent=2))
    else:
        console.print(f"[bold]{entity_type} entities in namespace '{namespace}':[/bold]")
        table = Table(show_header=True)
        table.add_column("Name")
        table.add_column("Confidence")
        
        for entity in mock_entities:
            table.add_row(entity["name"], f"{entity['confidence']:.2f}")
        
        console.print(table)
    
    console.print("[yellow]Query functionality will be implemented in Step 4[/yellow]")


@query.command("list-docs")
@click.pass_context
def list_docs(ctx: click.Context) -> None:
    """List all documents in the knowledge graph."""
    namespace = ctx.obj["query_namespace"]
    output_format = ctx.obj["query_format"]
    max_results = ctx.obj["query_max_results"]
    
    logger.info(f"Listing documents in namespace: [bold]{namespace}[/bold]")
    
    # TODO: Implement actual query logic in later steps
    mock_docs = [
        {"doc_id": "platform/intro", "source_path": "platform/intro.html"},
        {"doc_id": "platform/architecture", "source_path": "platform/architecture.html"}
    ]
    
    if output_format == "json":
        result = {
            "namespace": namespace,
            "max_results": max_results,
            "documents": mock_docs
        }
        console.print(json.dumps(result, indent=2))
    else:
        console.print(f"[bold]Documents in namespace '{namespace}':[/bold]")
        table = Table(show_header=True)
        table.add_column("Document ID")
        table.add_column("Source Path")
        
        for doc in mock_docs:
            table.add_row(doc["doc_id"], doc["source_path"])
        
        console.print(table)
    
    console.print("[yellow]Query functionality will be implemented in Step 4[/yellow]")


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
    
    # TODO: Implement actual query logic in later steps
    mock_doc = {
        "doc_id": doc_id,
        "namespace": namespace,
        "source_path": f"{doc_id}.html",
        "content_hash": "abc123...",
        "entities_mentioned": ["Product A", "Team B"]
    }
    
    if output_format == "json":
        console.print(json.dumps(mock_doc, indent=2))
    else:
        console.print(f"[bold]Document: {doc_id}[/bold]")
        console.print(f"Namespace: {namespace}")
        console.print(f"Source Path: {mock_doc['source_path']}")
        console.print(f"Content Hash: {mock_doc['content_hash']}")
        console.print("Entities Mentioned:")
        for entity in mock_doc["entities_mentioned"]:
            console.print(f"  • {entity}")
    
    console.print("[yellow]Query functionality will be implemented in Step 4[/yellow]")


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
    
    # TODO: Implement actual query logic in later steps
    mock_related = [
        {"entity": "Related Entity 1", "type": "Component", "relationship": "USES"},
        {"entity": "Related Entity 2", "type": "Technology", "relationship": "IMPLEMENTS"}
    ]
    
    if output_format == "json":
        result = {
            "namespace": namespace,
            "source_entity": entity,
            "source_type": entity_type,
            "max_results": max_results,
            "related_entities": mock_related
        }
        console.print(json.dumps(result, indent=2))
    else:
        console.print(f"[bold]Entities related to '{entity}' ({entity_type}):[/bold]")
        table = Table(show_header=True)
        table.add_column("Entity")
        table.add_column("Type")
        table.add_column("Relationship")
        
        for related in mock_related:
            table.add_row(related["entity"], related["type"], related["relationship"])
        
        console.print(table)
    
    console.print("[yellow]Query functionality will be implemented in Step 4[/yellow]")

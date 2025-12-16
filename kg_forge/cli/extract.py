"""
CLI command for testing entity extraction.
"""

import click
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

from kg_forge.models.extraction import ExtractionRequest
from kg_forge.extractors.factory import create_extractor
from kg_forge.extractors.base import ConfigurationError
from kg_forge.parsers.html_parser import ConfluenceHTMLParser
from kg_forge.utils.verbose import create_verbose_logger

console = Console()


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.pass_context
@click.option(
    "--types",
    "-t",
    multiple=True,
    help="Entity types to extract (can specify multiple times). Leave empty for all types."
)
@click.option(
    "--min-confidence",
    type=float,
    default=0.0,
    help="Minimum confidence threshold (0.0-1.0). Default: 0.0 (no filtering)"
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format"
)
@click.option(
    "--max-tokens",
    type=int,
    default=4000,
    help="Maximum tokens for LLM response. Default: 4000"
)
@click.option(
    "--entities-dir",
    type=click.Path(exists=True),
    default="entities_extract",
    help="Directory containing entity definitions"
)
def extract(
    ctx: click.Context,
    file_path: str,
    types: tuple,
    min_confidence: float,
    format: str,
    max_tokens: int,
    entities_dir: str
):
    """Extract entities from a document for testing.
    
    This command is useful for testing entity extraction without running
    the full ingestion pipeline.
    
    Examples:
    
      # Extract all entity types
      kg-forge extract test-doc.html
      
      # Extract specific types only
      kg-forge extract test-doc.html --types Product --types Team
      
      # Filter by confidence
      kg-forge extract test-doc.html --min-confidence 0.7
      
      # Output as JSON
      kg-forge extract test-doc.html --format json
      
      # With verbose output
      kg-forge --verbose extract test-doc.html
    """
    try:
        # Get settings from context
        settings = ctx.obj.get("settings")
        
        # Create verbose logger if verbose mode is enabled
        verbose_logger = None
        if settings and settings.app.verbose:
            verbose_logger = create_verbose_logger(enabled=True)
        
        # Load document
        console.print(f"[cyan]Loading document:[/cyan] {file_path}")
        parser =  ConfluenceHTMLParser()
        document = parser.parse_file(Path(file_path))
        
        # Create extractor
        console.print("[cyan]Initializing extractor...[/cyan]")
        try:
            extractor = create_extractor(
                entities_dir=entities_dir,
                verbose_logger=verbose_logger
            )
        except ConfigurationError as e:
            console.print(f"[red]Configuration Error:[/red] {e}")
            raise click.Abort()
        
        console.print(f"[green]Using model:[/green] {extractor.get_model_name()}")
        
        # Build extraction request
        entity_types = list(types) if types else []
        if entity_types:
            console.print(f"[cyan]Extracting types:[/cyan] {', '.join(entity_types)}")
        else:
            console.print("[cyan]Extracting all entity types[/cyan]")
        
        request = ExtractionRequest(
            content=document.text,
            entity_types=entity_types,
            max_tokens=max_tokens,
            min_confidence=min_confidence
        )
        
        # Extract entities
        console.print("[cyan]Extracting entities...[/cyan]")
        result = extractor.extract(request)
        
        if not result.success:
            console.print(f"[red]Extraction failed:[/red] {result.error}")
            raise click.Abort()
        
        # Filter results by requested entity types (case-insensitive)
        if entity_types:
            entity_types_lower = [t.lower() for t in entity_types]
            original_count = len(result.entities)
            result.entities = [
                e for e in result.entities
                if e.entity_type.lower() in entity_types_lower
            ]
            filtered_count = original_count - len(result.entities)
            if filtered_count > 0:
                console.print(
                    f"[dim]Filtered out {filtered_count} entities of other types[/dim]"
                )
        
        # Output results
        if format == "json":
            _output_json(result, file_path)
        else:
            _output_text(result, file_path, entity_types)
            
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


def _output_text(result, file_path: str, entity_types: list):
    """Output results in human-readable text format."""
    console.print()
    console.print(f"[bold green]✓ Extraction Complete[/bold green]")
    console.print()
    console.print(f"[cyan]File:[/cyan] {file_path}")
    console.print(f"[cyan]Model:[/cyan] {result.model_name}")
    console.print(f"[cyan]Entities found:[/cyan] {len(result.entities)}")
    
    if result.tokens_used:
        console.print(f"[cyan]Tokens used:[/cyan] {result.tokens_used}")
    
    if result.extraction_time:
        console.print(f"[cyan]Extraction time:[/cyan] {result.extraction_time:.2f}s")
    
    if not result.entities:
        console.print()
        console.print("[yellow]No entities found[/yellow]")
        return
    
    console.print()
    
    # Group entities by type
    entities_by_type = {}
    for entity in result.entities:
        if entity.entity_type not in entities_by_type:
            entities_by_type[entity.entity_type] = []
        entities_by_type[entity.entity_type].append(entity)
    
    # Display entities grouped by type
    for entity_type in sorted(entities_by_type.keys()):
        entities = entities_by_type[entity_type]
        console.print(f"[bold]{entity_type}[/bold] ({len(entities)}):")
        
        for entity in entities:
            conf_text = f" [dim](confidence: {entity.confidence:.2f})[/dim]" if entity.confidence < 1.0 else ""
            console.print(f"  • {entity.name}{conf_text}")
            
            # Show properties if any
            if entity.properties:
                for key, value in entity.properties.items():
                    if isinstance(value, list):
                        value_str = ", ".join(str(v) for v in value)
                    else:
                        value_str = str(value)
                    console.print(f"    [dim]{key}:[/dim] {value_str}")
        
        console.print()


def _output_json(result, file_path: str):
    """Output results in JSON format."""
    output = {
        "file": file_path,
        "model": result.model_name,
        "entities": [
            {
                "type": entity.entity_type,
                "name": entity.name,
                "confidence": entity.confidence,
                **entity.properties
            }
            for entity in result.entities
        ],
        "metadata": {
            "entity_count": len(result.entities),
            "extraction_time": result.extraction_time,
            "tokens_used": result.tokens_used,
            "success": result.success
        }
    }
    
    console.print(json.dumps(output, indent=2))

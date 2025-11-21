"""Ingest command for kg-forge CLI."""

import click
from pathlib import Path
from typing import Optional
from rich.console import Console

from kg_forge.utils.logging import get_logger
from kg_forge.parsers import ConfluenceHTMLParser, DocumentLoader

console = Console()
logger = get_logger(__name__)


@click.command()
@click.option(
    "--source", 
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to source directory containing HTML files"
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    help="Output directory for parsed markdown files (uses doc_id as filename)"
)
@click.option(
    "--namespace", 
    default=None,
    help="Experiment namespace (alphanumeric only, default from config)"
)
@click.option(
    "--dry-run", 
    is_flag=True,
    help="Extract entities but don't write to graph"
)
@click.option(
    "--refresh", 
    is_flag=True,
    help="Re-import even if content hash matches"
)
@click.option(
    "--interactive", "--biraj", 
    is_flag=True,
    help="Enable interactive mode"
)
@click.option(
    "--prompt-template", 
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    help="Override prompt template file"
)
@click.option(
    "--model", 
    help="Override bedrock model name"
)
@click.option(
    "--max-results", 
    type=int,
    default=10,
    help="Maximum results to return"
)
@click.pass_context
def ingest(
    ctx: click.Context,
    source: Path,
    output_dir: Optional[Path] = None,
    namespace: Optional[str] = None,
    dry_run: bool = False,
    refresh: bool = False,
    interactive: bool = False,
    prompt_template: Optional[Path] = None,
    model: Optional[str] = None,
    max_results: int = 10
) -> None:
    """
    Ingest HTML files from a source directory and extract entities.
    
    This command processes HTML files in the specified directory,
    extracts entities using LLM analysis, and stores them in the
    knowledge graph.
    
    If --output-dir is specified, parsed markdown content will be
    written to files named by document ID.
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
    
    logger.info(f"Starting ingest from {source}")
    logger.info(f"Target namespace: {target_namespace}")
    
    if dry_run:
        logger.info("Dry run mode - no changes will be persisted")
    
    if refresh:
        logger.info("Refresh mode - will re-import existing content")
    
    if interactive:
        logger.info("Interactive mode enabled")
    
    if prompt_template:
        logger.info(f"Using custom prompt template: {prompt_template}")
    
    if model:
        logger.info(f"Using custom model: {model}")
    
    # If output_dir is specified, parse and export markdown
    if output_dir:
        console.print(f"\n[bold blue]Parsing HTML and exporting markdown to:[/bold blue] {output_dir}\n")
        
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse HTML files
        parser = ConfluenceHTMLParser()
        loader = DocumentLoader(parser)
        
        try:
            documents = loader.load_from_directory(source)
            console.print(f"[green]✓ Parsed {len(documents)} documents[/green]\n")
            
            # Write markdown files
            for doc in documents:
                output_file = output_dir / f"{doc.doc_id}.md"
                
                # Create file content with metadata header
                content = f"""# {doc.title}

**Document ID:** {doc.doc_id}  
**Source:** {doc.source_file}  
**Breadcrumb:** {' → '.join(doc.breadcrumb)}  
**Content Hash:** {doc.content_hash}

---

{doc.text}
"""
                
                output_file.write_text(content, encoding='utf-8')
                console.print(f"[dim]• Wrote:[/dim] {output_file.name}")
            
            console.print(f"\n[bold green]✓ Successfully exported {len(documents)} markdown files[/bold green]")
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            ctx.exit(1)
    
    else:
        # TODO: Implement actual ingestion logic in later steps
        console.print("[yellow]Ingestion functionality will be implemented in Step 6[/yellow]")
    
    logger.info("Ingest command completed")

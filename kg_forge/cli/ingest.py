"""Ingest command for kg-forge CLI."""

import click
from pathlib import Path
from typing import Optional
from rich.console import Console

from kg_forge.utils.logging import get_logger

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
    
    logger.info(f"Starting ingest from [bold]{source}[/bold]")
    logger.info(f"Target namespace: [bold]{target_namespace}[/bold]")
    
    if dry_run:
        logger.info("[yellow]Dry run mode - no changes will be persisted[/yellow]")
    
    if refresh:
        logger.info("[blue]Refresh mode - will re-import existing content[/blue]")
    
    if interactive:
        logger.info("[magenta]Interactive mode enabled[/magenta]")
    
    if prompt_template:
        logger.info(f"Using custom prompt template: [bold]{prompt_template}[/bold]")
    
    if model:
        logger.info(f"Using custom model: [bold]{model}[/bold]")
    
    # TODO: Implement actual ingestion logic in later steps
    console.print("[yellow]Ingestion functionality will be implemented in Step 6[/yellow]")
    
    logger.info("Ingest command completed")

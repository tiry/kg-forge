"""Main CLI entry point for kg-forge."""

import click
from typing import Optional, Dict, Any
from rich.console import Console

from kg_forge import __version__
from kg_forge.config.settings import get_settings
from kg_forge.utils.logging import setup_logging, get_logger
from kg_forge.cli.ingest import ingest
from kg_forge.cli.parse import parse_html
from kg_forge.cli.query import query
from kg_forge.cli.render import render
from kg_forge.cli.entities import entities
from kg_forge.cli.db import db_group
from kg_forge.cli.extract import extract
from kg_forge.cli.pipeline import run_pipeline


# Create Rich console for output
console = Console()
logger = get_logger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="kg-forge")
@click.option(
    "--log-level", 
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Set the logging level"
)
@click.pass_context
def cli(ctx: click.Context, log_level: Optional[str] = None) -> None:
    """
    Knowledge Graph Forge - CLI tool for building and managing knowledge graphs.
    
    Extract entities from unstructured content and build knowledge graphs
    for experimentation and analysis.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Load configuration with any overrides
    config_overrides = {}
    if log_level:
        config_overrides = {"app": {"log_level": log_level}}
    
    try:
        settings = get_settings(config_overrides)
        ctx.obj["settings"] = settings
        
        # Setup logging
        setup_logging(settings.app.log_level, console)
        
        logger.debug(f"Loaded configuration: Neo4j URI={settings.neo4j.uri}")
        logger.debug(f"Default namespace: {settings.app.default_namespace}")
        
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        ctx.exit(1)


@cli.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Display version information."""
    console.print(f"[bold green]kg-forge[/bold green] version [bold]{__version__}[/bold]")


# Add command groups
cli.add_command(run_pipeline)  # End-to-end pipeline (Step 6)
cli.add_command(ingest)
cli.add_command(parse_html)
cli.add_command(extract)
cli.add_command(query)
cli.add_command(render)
cli.add_command(entities)
cli.add_command(db_group)  # Database management (start, stop, init, status, clear)


def main() -> None:
    """Entry point for the CLI application."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"[red]Error: {e}[/red]")
        exit(1)


if __name__ == "__main__":
    main()

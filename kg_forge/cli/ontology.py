"""Ontology management commands for kg-forge CLI."""

import click
from rich.console import Console
from rich.table import Table
import json

from kg_forge.config.settings import get_settings
from kg_forge.ontology_manager import get_ontology_manager
from kg_forge.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


@click.group()
@click.pass_context
def ontology(ctx: click.Context) -> None:
    """
    Manage ontology packs for entity definitions and styling.
    
    Ontology packs contain entity type definitions, prompt templates,
    and visual styling configurations. Use these commands to list,
    switch between, or validate different ontology packs.
    """
    # Store ontology manager in context for subcommands
    ctx.obj["ontology_manager"] = get_ontology_manager()


@ontology.command("list")
@click.option(
    "--format", 
    "output_format",
    type=click.Choice(["json", "text"], case_sensitive=False),
    default="text",
    help="Output format"
)
@click.pass_context
def list_ontologies(ctx: click.Context, output_format: str) -> None:
    """List all available ontology packs."""
    ontology_manager = ctx.obj["ontology_manager"]
    
    try:
        ontologies = ontology_manager.list_available_ontologies()
        
        if output_format == "json":
            console.print(json.dumps(ontologies, indent=2))
        else:
            console.print("[bold]Available Ontology Packs:[/bold]")
            if ontologies:
                table = Table(show_header=True)
                table.add_column("ID")
                table.add_column("Name")
                table.add_column("Version")
                table.add_column("Description")
                
                active_pack = ontology_manager.get_active_ontology()
                active_id = active_pack.info.id if active_pack else None
                
                for ontology in ontologies:
                    id_display = f"[bold green]{ontology['id']}[/bold green]" if ontology['id'] == active_id else ontology['id']
                    table.add_row(
                        id_display,
                        ontology['name'],
                        ontology['version'],
                        ontology['description'][:60] + "..." if len(ontology['description']) > 60 else ontology['description']
                    )
                
                console.print(table)
                
                if active_id:
                    console.print(f"\\n[green]Active ontology pack: {active_id}[/green]")
                else:
                    console.print("\\n[yellow]No active ontology pack[/yellow]")
            else:
                console.print("  [yellow]No ontology packs found[/yellow]")
                console.print("  Run 'kg-forge ontology discover' to find ontology packs.")
                
    except Exception as e:
        console.print(f"[red]Error listing ontology packs: {e}[/red]")
        ctx.exit(1)


@ontology.command("activate")
@click.argument("ontology_id")
@click.pass_context
def activate_ontology(ctx: click.Context, ontology_id: str) -> None:
    """Activate a specific ontology pack."""
    ontology_manager = ctx.obj["ontology_manager"]
    
    try:
        ontology_manager.set_active_ontology(ontology_id)
        console.print(f"[green]Activated ontology pack: {ontology_id}[/green]")
        
        # Show basic info about activated pack
        pack = ontology_manager.get_active_ontology()
        if pack:
            console.print(f"Name: {pack.info.name}")
            console.print(f"Description: {pack.info.description}")
            
            # Show entity types
            definitions = pack.get_entity_definitions()
            if definitions:
                console.print(f"Entity types: {', '.join([d.id for d in definitions])}")
        
    except Exception as e:
        console.print(f"[red]Error activating ontology pack '{ontology_id}': {e}[/red]")
        ctx.exit(1)


@ontology.command("info")
@click.argument("ontology_id", required=False)
@click.option(
    "--format", 
    "output_format",
    type=click.Choice(["json", "text"], case_sensitive=False),
    default="text",
    help="Output format"
)
@click.pass_context
def ontology_info(ctx: click.Context, ontology_id: str, output_format: str) -> None:
    """Show detailed information about an ontology pack."""
    ontology_manager = ctx.obj["ontology_manager"]
    
    try:
        if ontology_id:
            pack = ontology_manager.registry.get_pack(ontology_id)
        else:
            pack = ontology_manager.get_active_ontology()
            if not pack:
                console.print("[red]No active ontology pack. Specify an ontology ID.[/red]")
                ctx.exit(1)
        
        # Get detailed information
        info = pack.info
        definitions = pack.get_entity_definitions()
        style_config = pack.get_style_config()
        has_template = pack.get_prompt_template() is not None
        
        if output_format == "json":
            result = {
                "info": {
                    "id": info.id,
                    "name": info.name,
                    "description": info.description,
                    "version": info.version,
                    "author": info.author,
                    "homepage": info.homepage,
                    "license": info.license,
                    "tags": info.tags
                },
                "entity_types": [
                    {
                        "id": d.id,
                        "name": d.name,
                        "description": d.description,
                        "relations_count": len(d.relations),
                        "examples_count": len(d.examples)
                    } 
                    for d in definitions
                ],
                "has_prompt_template": has_template,
                "has_style_config": style_config is not None,
                "style_entity_types": list(style_config.entity_colors.keys()) if style_config else []
            }
            console.print(json.dumps(result, indent=2))
        else:
            console.print(f"[bold]Ontology Pack: {info.name}[/bold]")
            console.print(f"ID: {info.id}")
            console.print(f"Version: {info.version}")
            console.print(f"Description: {info.description}")
            if info.author:
                console.print(f"Author: {info.author}")
            if info.homepage:
                console.print(f"Homepage: {info.homepage}")
            if info.license:
                console.print(f"License: {info.license}")
            if info.tags:
                console.print(f"Tags: {', '.join(info.tags)}")
            
            console.print(f"\\n[bold]Entity Types ({len(definitions)}):[/bold]")
            if definitions:
                for definition in definitions:
                    console.print(f"  • {definition.id}: {definition.name or 'No name'}")
                    if definition.description:
                        desc_preview = definition.description[:80] + "..." if len(definition.description) > 80 else definition.description
                        console.print(f"    {desc_preview}")
            
            console.print(f"\\n[bold]Features:[/bold]")
            console.print(f"  • Prompt template: {'Yes' if has_template else 'No'}")
            console.print(f"  • Style configuration: {'Yes' if style_config else 'No'}")
            if style_config:
                styled_types = list(style_config.entity_colors.keys())
                console.print(f"  • Styled entity types: {', '.join(styled_types)}")
                
    except Exception as e:
        console.print(f"[red]Error getting ontology info: {e}[/red]")
        ctx.exit(1)


@ontology.command("validate")
@click.argument("ontology_id", required=False)
@click.pass_context
def validate_ontology(ctx: click.Context, ontology_id: str) -> None:
    """Validate an ontology pack structure and configuration."""
    ontology_manager = ctx.obj["ontology_manager"]
    
    try:
        if ontology_id:
            pack = ontology_manager.registry.get_pack(ontology_id)
        else:
            pack = ontology_manager.get_active_ontology()
            if not pack:
                console.print("[red]No active ontology pack. Specify an ontology ID.[/red]")
                ctx.exit(1)
        
        console.print(f"[bold]Validating ontology pack: {pack.info.id}[/bold]")
        
        # Run validation
        issues = pack.validate_pack()
        
        if not issues:
            console.print("[green]✓ Ontology pack is valid[/green]")
        else:
            console.print(f"[red]✗ Found {len(issues)} issue(s):[/red]")
            for issue in issues:
                console.print(f"  • {issue}")
            ctx.exit(1)
                
    except Exception as e:
        console.print(f"[red]Error validating ontology pack: {e}[/red]")
        ctx.exit(1)


@ontology.command("discover")
@click.option(
    "--directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Directory to search for ontology packs (default: ./ontology_packs)"
)
@click.pass_context
def discover_ontologies(ctx: click.Context, directory: str) -> None:
    """Discover and register ontology packs from a directory."""
    settings = ctx.obj["settings"]
    ontology_manager = ctx.obj["ontology_manager"]
    
    if directory:
        from pathlib import Path
        search_dir = Path(directory)
    else:
        search_dir = ontology_manager.ontology_packs_dir
    
    console.print(f"[bold]Discovering ontology packs in: {search_dir}[/bold]")
    
    try:
        # Clear existing registry and rediscover
        ontology_manager.registry.clear()
        discovered = ontology_manager.registry.discover_packs(search_dir)
        
        if discovered:
            console.print(f"[green]Discovered {len(discovered)} ontology pack(s):[/green]")
            for pack in discovered:
                console.print(f"  • {pack.info.id}: {pack.info.name}")
        else:
            console.print(f"[yellow]No ontology packs found in {search_dir}[/yellow]")
            console.print("Make sure ontology packs have proper structure with pack.yaml and entities/ directory.")
            
    except Exception as e:
        console.print(f"[red]Error discovering ontology packs: {e}[/red]")
        ctx.exit(1)
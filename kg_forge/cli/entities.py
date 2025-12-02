"""CLI commands for entity definitions management."""

import click
import sys
from pathlib import Path
from typing import Optional

from kg_forge.entities.loader import EntityDefinitionsLoader
from kg_forge.entities.template import PromptTemplateBuilder


def get_entities_dir() -> Path:
    """Get path to entities directory."""
    # Default to entities_extract in project root
    project_root = Path(__file__).parent.parent.parent
    return project_root / "entities_extract"


@click.group()
def entities():
    """Manage entity type definitions."""
    pass


@entities.command(name="list")
@click.option(
    "--entities-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to entities directory (default: entities_extract/)",
)
def list_entities(entities_dir: Optional[Path]):
    """List all entity type definitions."""
    if entities_dir is None:
        entities_dir = get_entities_dir()
    
    try:
        loader = EntityDefinitionsLoader(entities_dir)
        definitions = loader.load_all()
        
        if definitions.count() == 0:
            click.echo("No entity definitions found.")
            return
        
        click.echo(f"\nEntity Type Definitions ({definitions.count()} found):\n")
        
        # Header
        click.echo(f"{'ID':<20} {'Name':<30} {'Relations':<12} {'Examples':<10}")
        click.echo("─" * 75)
        
        # List each entity
        for entity_id in definitions.get_all_ids():
            definition = definitions.get_by_type(entity_id)
            name = definition.name or "(no name)"
            rel_count = len(definition.relations)
            ex_count = len(definition.examples)
            
            click.echo(f"{entity_id:<20} {name:<30} {rel_count:<12} {ex_count:<10}")
        
        click.echo()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@entities.command(name="show")
@click.argument("entity_type")
@click.option(
    "--entities-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to entities directory (default: entities_extract/)",
)
def show_entity(entity_type: str, entities_dir: Optional[Path]):
    """Show details for a specific entity type."""
    if entities_dir is None:
        entities_dir = get_entities_dir()
    
    try:
        loader = EntityDefinitionsLoader(entities_dir)
        definitions = loader.load_all()
        
        # Find entity (case-insensitive)
        entity_type_lower = entity_type.lower()
        definition = definitions.get_by_type(entity_type_lower)
        
        if definition is None:
            click.echo(f"Error: Entity type '{entity_type}' not found.", err=True)
            click.echo(f"\nAvailable types: {', '.join(definitions.get_all_ids())}")
            sys.exit(1)
        
        # Display details
        click.echo(f"\nEntity Type: {definition.entity_type_id}")
        if definition.name:
            click.echo(f"Name: {definition.name}")
        click.echo(f"Source: {definition.source_file}\n")
        
        if definition.description:
            click.echo("Description:")
            click.echo(definition.description)
            click.echo()
        
        if definition.relations:
            click.echo(f"Relations ({len(definition.relations)}):")
            for rel in definition.relations:
                click.echo(f"  → {rel.target_entity_type} : {rel.forward_label} : {rel.reverse_label}")
            click.echo()
        
        if definition.examples:
            click.echo(f"Examples ({len(definition.examples)}):")
            for example in definition.examples:
                click.echo(f"  • {example.name}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@entities.command(name="validate")
@click.option(
    "--entities-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to entities directory (default: entities_extract/)",
)
def validate_entities(entities_dir: Optional[Path]):
    """Validate all entity definitions."""
    if entities_dir is None:
        entities_dir = get_entities_dir()
    
    try:
        loader = EntityDefinitionsLoader(entities_dir)
        definitions = loader.load_all()
        
        click.echo(f"\nValidating {definitions.count()} entity definitions...\n")
        
        # Run validation
        warnings = definitions.validate_definitions()
        
        if not warnings:
            click.echo("✓ All entity definitions are valid!")
            click.echo()
            return
        
        # Display warnings
        click.echo(f"Found {len(warnings)} warnings:\n")
        for warning in warnings:
            click.echo(f"  ⚠ {warning}")
        click.echo()
        
        click.echo("Note: These are warnings, not errors. The definitions will still work.")
        click.echo()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@entities.command(name="template")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: stdout)",
)
@click.option(
    "--entities-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to entities directory (default: entities_extract/)",
)
def show_template(output: Optional[Path], entities_dir: Optional[Path]):
    """Show the merged prompt template with entity definitions."""
    if entities_dir is None:
        entities_dir = get_entities_dir()
    
    try:
        # Load entity definitions
        loader = EntityDefinitionsLoader(entities_dir)
        definitions = loader.load_all()
        
        # Get template path
        builder = PromptTemplateBuilder()
        template_path = builder.get_default_template_path(entities_dir)
        
        if not template_path.exists():
            click.echo(f"Error: Template file not found: {template_path}", err=True)
            sys.exit(1)
        
        # Merge definitions into template
        merged_template = builder.merge_definitions(template_path, definitions)
        
        # Output
        if output:
            output.write_text(merged_template, encoding='utf-8')
            click.echo(f"Template written to: {output}")
        else:
            click.echo(merged_template)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

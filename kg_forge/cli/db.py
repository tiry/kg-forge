"""Database management CLI commands."""

import click
from rich.console import Console
from rich.table import Table
from rich import box

from kg_forge.config.settings import get_settings
from kg_forge.graph.factory import (
    get_graph_client,
    get_schema_manager
)
from kg_forge.graph.exceptions import GraphError, ConnectionError as GraphConnectionError

console = Console()


@click.group(name="db")
def db_group():
    """Database management commands."""
    pass


@db_group.command(name="init")
@click.option(
    "--namespace",
    default="default",
    help="Namespace to initialize (default: default)"
)
@click.option(
    "--drop-existing",
    is_flag=True,
    help="Drop existing data in namespace before initializing"
)
def init_database(namespace: str, drop_existing: bool):
    """Initialize database schema and optionally clear namespace data.
    
    Creates constraints and indexes required for the knowledge graph.
    Optionally clears existing data for the specified namespace.
    """
    try:
        # Get configuration and client
        config = get_settings()
        
        # Validate namespace
        config.validate_namespace(namespace)
        
        client = get_graph_client(config)
        schema_mgr = get_schema_manager(client)
        
        # Connect to database
        console.print(f"[blue]Connecting to Neo4j at {config.neo4j.uri}...[/blue]")
        client.connect()
        
        # Clear namespace if requested
        if drop_existing:
            console.print(f"[yellow]Clearing existing data for namespace '{namespace}'...[/yellow]")
            deleted_count = schema_mgr.clear_namespace(namespace)
            console.print(f"[green]✓[/green] Deleted {deleted_count} nodes")
        
        # Create schema
        console.print("[blue]Creating database schema...[/blue]")
        schema_mgr.create_schema()
        console.print("[green]✓[/green] Schema created successfully")
        
        # Verify schema
        console.print("[blue]Verifying schema...[/blue]")
        if schema_mgr.verify_schema():
            console.print("[green]✓[/green] Schema verification passed")
        else:
            console.print("[yellow]⚠[/yellow] Schema verification failed - some constraints or indexes may be missing")
        
        console.print(f"\n[green]✓ Database initialized successfully for namespace '{namespace}'[/green]")
        
        client.close()
        
    except ValueError as e:
        console.print(f"[red]✗ Error:[/red] {e}", style="bold red")
        raise click.Abort()
    except GraphConnectionError as e:
        console.print(f"[red]✗ Connection Error:[/red] {e}", style="bold red")
        console.print("\n[yellow]Hint:[/yellow] Make sure Neo4j is running. Try: kg-forge neo4j-start")
        raise click.Abort()
    except GraphError as e:
        console.print(f"[red]✗ Database Error:[/red] {e}", style="bold red")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Unexpected Error:[/red] {e}", style="bold red")
        raise click.Abort()


@db_group.command(name="status")
@click.option(
    "--namespace",
    default=None,
    help="Show statistics for specific namespace"
)
def database_status(namespace: str):
    """Show database connection status and statistics."""
    try:
        # Get configuration and client
        config = get_settings()
        client = get_graph_client(config)
        schema_mgr = get_schema_manager(client)
        
        # Connect to database
        console.print(f"[blue]Connecting to Neo4j at {config.neo4j.uri}...[/blue]")
        client.connect()
        
        # Connection status
        console.print(f"[green]✓[/green] Connected to Neo4j at {config.neo4j.uri}\n")
        
        # Schema status
        console.print("[blue]Schema Status:[/blue]")
        if schema_mgr.verify_schema():
            console.print("  [green]✓[/green] All constraints and indexes present")
        else:
            console.print("  [yellow]⚠[/yellow] Schema incomplete - run 'kg-forge db init' to create schema")
        
        # Statistics
        console.print("\n[blue]Database Statistics:[/blue]")
        stats = schema_mgr.get_statistics(namespace)
        
        if namespace:
            console.print(f"  Namespace: {namespace}")
            
            # Node counts
            if stats.get('nodes'):
                console.print("\n  Nodes:")
                for label, count in stats['nodes'].items():
                    console.print(f"    {label}: {count}")
            else:
                console.print("  No nodes found")
            
            # Relationship counts
            if stats.get('relationships'):
                console.print("\n  Relationships:")
                for rel_type, count in stats['relationships'].items():
                    console.print(f"    {rel_type}: {count}")
            else:
                console.print("  No relationships found")
        else:
            total_nodes = stats.get('total_nodes', 0)
            console.print(f"  Total Nodes: {total_nodes}")
            console.print(f"\n  {stats.get('message', '')}")
        
        client.close()
        
    except GraphConnectionError as e:
        console.print(f"[red]✗ Connection Error:[/red] {e}", style="bold red")
        console.print("\n[yellow]Hint:[/yellow] Make sure Neo4j is running. Try: kg-forge neo4j-start")
        raise click.Abort()
    except GraphError as e:
        console.print(f"[red]✗ Database Error:[/red] {e}", style="bold red")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Unexpected Error:[/red] {e}", style="bold red")
        raise click.Abort()


@db_group.command(name="clear")
@click.option(
    "--namespace",
    required=True,
    help="Namespace to clear"
)
@click.option(
    "--confirm",
    is_flag=True,
    help="Confirm deletion without interactive prompt"
)
def clear_namespace(namespace: str, confirm: bool):
    """Clear all data for a specific namespace.
    
    This will delete all nodes and relationships for the specified namespace.
    Use with caution!
    """
    try:
        # Get configuration and client
        config = get_settings()
        
        # Validate namespace
        config.validate_namespace(namespace)
        
        # Confirm deletion
        if not confirm:
            console.print(f"[yellow]⚠ WARNING:[/yellow] This will delete all data in namespace '{namespace}'")
            if not click.confirm("Are you sure you want to continue?"):
                console.print("Operation cancelled")
                return
        
        client = get_graph_client(config)
        schema_mgr = get_schema_manager(client)
        
        # Connect to database
        console.print(f"[blue]Connecting to Neo4j at {config.neo4j.uri}...[/blue]")
        client.connect()
        
        # Clear namespace
        console.print(f"[blue]Clearing namespace '{namespace}'...[/blue]")
        deleted_count = schema_mgr.clear_namespace(namespace)
        
        console.print(f"[green]✓[/green] Deleted {deleted_count} nodes from namespace '{namespace}'")
        
        client.close()
        
    except ValueError as e:
        console.print(f"[red]✗ Error:[/red] {e}", style="bold red")
        raise click.Abort()
    except GraphConnectionError as e:
        console.print(f"[red]✗ Connection Error:[/red] {e}", style="bold red")
        console.print("\n[yellow]Hint:[/yellow] Make sure Neo4j is running. Try: kg-forge neo4j-start")
        raise click.Abort()
    except GraphError as e:
        console.print(f"[red]✗ Database Error:[/red] {e}", style="bold red")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Unexpected Error:[/red] {e}", style="bold red")
        raise click.Abort()

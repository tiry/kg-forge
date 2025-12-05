"""Database management CLI commands."""

import click
import subprocess
import time
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


@db_group.command(name="start")
def start_database():
    """
    Start Neo4j database instance using docker-compose.
    
    This command starts Neo4j in a Docker container and waits for it
    to be ready for connections.
    """
    console.print("[blue]Starting Neo4j database with docker-compose...[/blue]")
    
    try:
        # Start Neo4j using docker-compose
        result = subprocess.run(
            ["docker-compose", "up", "-d", "neo4j"],
            capture_output=True,
            text=True,
            check=True
        )
        
        console.print("[green]✓[/green] Neo4j container started")
        
        # Wait for Neo4j to be ready
        console.print("[blue]Waiting for Neo4j to be ready...[/blue]")
        max_wait = 30  # seconds
        waited = 0
        
        while waited < max_wait:
            try:
                # Check if Neo4j is responding
                health_check = subprocess.run(
                    ["docker", "exec", "kg-forge-neo4j", "wget", "--spider", "-q", "http://localhost:7474"],
                    capture_output=True,
                    timeout=2
                )
                if health_check.returncode == 0:
                    settings = get_settings()
                    console.print(f"[green]✓[/green] Neo4j is ready at {settings.neo4j.uri}")
                    console.print(f"[blue]Browser UI:[/blue] http://localhost:7474")
                    console.print(f"[blue]Credentials:[/blue] neo4j / password")
                    return
            except subprocess.TimeoutExpired:
                pass
            
            time.sleep(2)
            waited += 2
            console.print(f"[yellow].[/yellow]", end="")
        
        console.print(f"\n[yellow]⚠[/yellow] Neo4j started but may still be initializing")
        console.print(f"[blue]Check status with:[/blue] docker logs kg-forge-neo4j")
        
    except FileNotFoundError:
        console.print("[red]✗ docker-compose not found[/red]")
        console.print("Please install Docker and docker-compose")
        raise click.Abort()
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Failed to start Neo4j:[/red] {e.stderr}")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Unexpected error:[/red] {e}")
        raise click.Abort()


@db_group.command(name="stop")
def stop_database():
    """
    Stop Neo4j database instance using docker-compose.
    
    This command cleanly stops the Neo4j Docker container.
    """
    console.print("[blue]Stopping Neo4j database...[/blue]")
    
    try:
        # Stop Neo4j using docker-compose
        result = subprocess.run(
            ["docker-compose", "stop", "neo4j"],
            capture_output=True,
            text=True,
            check=True
        )
        
        console.print("[green]✓[/green] Neo4j container stopped")
        console.print("[blue]Data is preserved in Docker volumes[/blue]")
        console.print("[blue]To remove data:[/blue] docker-compose down -v")
        
    except FileNotFoundError:
        console.print("[red]✗ docker-compose not found[/red]")
        console.print("Please install Docker and docker-compose")
        raise click.Abort()
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Failed to stop Neo4j:[/red] {e.stderr}")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Unexpected error:[/red] {e}")
        raise click.Abort()


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

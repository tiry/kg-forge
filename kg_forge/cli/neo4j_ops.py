"""Neo4j operations CLI commands."""

import logging
from typing import Optional, Dict, Any

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..config.settings import get_settings
from ..graph import Neo4jClient, SchemaManager, Neo4jConnectionError, SchemaError

logger = logging.getLogger(__name__)
console = Console()


@click.group()
def neo4j():
    """Neo4j database operations and management."""
    pass


@neo4j.command("init-schema")
@click.option(
    "--force", 
    is_flag=True,
    help="Force schema recreation even if constraints/indexes exist"
)
@click.option(
    "--output", 
    type=click.Choice(["table", "json", "raw"]),
    default="table",
    help="Output format"
)
def init_schema(force: bool, output: str):
    """Initialize Neo4j database schema (constraints and indexes)."""
    try:
        settings = get_settings()
        
        with Neo4jClient(settings) as client:
            schema_manager = SchemaManager(client)
            
            logger.info("Initializing Neo4j schema")
            schema_manager.initialize_schema(force=force)
            
            # Get validation results
            validation = schema_manager.validate_schema()
            
            if output == "json":
                import json
                result = {
                    "status": "success",
                    "message": "Schema initialized successfully",
                    "validation": validation
                }
                print(json.dumps(result, indent=2))
                
            elif output == "raw":
                print("Schema initialized successfully")
                print(f"Constraints valid: {validation['constraints_valid']}")
                print(f"Indexes valid: {validation['indexes_valid']}")
                
            else:  # table format
                console.print("✅ [green]Schema initialized successfully[/green]")
                
                # Show validation results in table
                table = Table(title="Schema Validation")
                table.add_column("Component", style="bold")
                table.add_column("Status", justify="center")
                table.add_column("Details")
                
                constraints_status = "✅ Valid" if validation["constraints_valid"] else "❌ Invalid"
                indexes_status = "✅ Valid" if validation["indexes_valid"] else "❌ Invalid"
                
                table.add_row("Constraints", constraints_status, f"{len(schema_manager.get_required_constraints())} required")
                table.add_row("Indexes", indexes_status, f"{len(schema_manager.get_required_indexes())} required")
                
                console.print(table)
            
    except Neo4jConnectionError as e:
        _handle_connection_error(e, output)
        raise click.ClickException(f"Neo4j connection failed: {e}")
        
    except SchemaError as e:
        _handle_schema_error(e, output)
        raise click.ClickException(f"Schema initialization failed: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error during schema initialization: {e}")
        if output == "json":
            import json
            error_result = {"status": "error", "message": str(e)}
            print(json.dumps(error_result, indent=2))
        else:
            console.print(f"❌ [red]Error: {e}[/red]")
        raise click.ClickException(f"Schema initialization failed: {e}")


@neo4j.command("test-connection")
@click.option(
    "--output",
    type=click.Choice(["table", "json", "raw"]),
    default="table", 
    help="Output format"
)
def test_connection(output: str):
    """Test connectivity to Neo4j database."""
    try:
        settings = get_settings()
        
        with Neo4jClient(settings) as client:
            success = client.test_connection()
            
            if success:
                # Get basic database info
                schema_info = client.get_schema_info()
                node_counts = client.get_node_counts()
                
                if output == "json":
                    import json
                    result = {
                        "status": "success",
                        "connected": True,
                        "database": settings.neo4j.database,
                        "uri": settings.neo4j.uri,
                        "node_counts": node_counts,
                        "schema": {
                            "constraints": len(schema_info.get("constraints", [])),
                            "indexes": len(schema_info.get("indexes", []))
                        }
                    }
                    print(json.dumps(result, indent=2))
                    
                elif output == "raw":
                    print("Connection: SUCCESS")
                    print(f"Database: {settings.neo4j.database}")
                    print(f"URI: {settings.neo4j.uri}")
                    print(f"Docs: {node_counts.get('docs', 0)}")
                    print(f"Entities: {node_counts.get('entities', 0)}")
                    
                else:  # table format
                    console.print("✅ [green]Neo4j connection successful[/green]")
                    
                    table = Table(title="Database Information")
                    table.add_column("Property", style="bold")
                    table.add_column("Value")
                    
                    table.add_row("Database", settings.neo4j.database)
                    table.add_row("URI", settings.neo4j.uri)
                    table.add_row("Username", settings.neo4j.username)
                    table.add_row("Doc Nodes", str(node_counts.get("docs", 0)))
                    table.add_row("Entity Nodes", str(node_counts.get("entities", 0)))
                    table.add_row("Constraints", str(len(schema_info.get("constraints", []))))
                    table.add_row("Indexes", str(len(schema_info.get("indexes", []))))
                    
                    console.print(table)
            else:
                _handle_connection_failure(output)
                raise click.ClickException("Neo4j connection test failed")
                
    except Neo4jConnectionError as e:
        _handle_connection_error(e, output)
        raise click.ClickException(f"Neo4j connection failed: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error during connection test: {e}")
        if output == "json":
            import json
            error_result = {"status": "error", "connected": False, "message": str(e)}
            print(json.dumps(error_result, indent=2))
        else:
            console.print(f"❌ [red]Connection failed: {e}[/red]")
        raise click.ClickException(f"Connection test failed: {e}")


@neo4j.command("status")
@click.option(
    "--namespace",
    default="default",
    help="Namespace to check status for"
)
@click.option(
    "--output",
    type=click.Choice(["table", "json", "raw"]),
    default="table",
    help="Output format"
)
def status(namespace: str, output: str):
    """Show Neo4j database status and statistics."""
    try:
        settings = get_settings()
        
        with Neo4jClient(settings) as client:
            # Get schema validation
            schema_manager = SchemaManager(client)
            validation = schema_manager.validate_schema()
            
            # Get node counts
            node_counts = client.get_node_counts(namespace)
            
            # Get entity types
            entity_types = client.get_entity_types(namespace)
            
            # Get schema info
            schema_info = client.get_schema_info()
            
            if output == "json":
                import json
                result = {
                    "status": "success",
                    "namespace": namespace,
                    "schema_valid": validation["schema_valid"],
                    "node_counts": node_counts,
                    "entity_types": entity_types,
                    "schema": {
                        "constraints": len(schema_info.get("constraints", [])),
                        "indexes": len(schema_info.get("indexes", []))
                    },
                    "validation": validation
                }
                print(json.dumps(result, indent=2))
                
            elif output == "raw":
                print(f"Namespace: {namespace}")
                print(f"Schema Valid: {validation['schema_valid']}")
                print(f"Docs: {node_counts.get('docs', 0)}")
                print(f"Entities: {node_counts.get('entities', 0)}")
                print(f"Entity Types: {len(entity_types)}")
                print(f"Constraints: {len(schema_info.get('constraints', []))}")
                print(f"Indexes: {len(schema_info.get('indexes', []))}")
                
            else:  # table format
                # Overall status
                schema_status = "✅ Valid" if validation["schema_valid"] else "❌ Invalid"
                console.print(f"[bold]Neo4j Database Status[/bold] - Namespace: [cyan]{namespace}[/cyan]")
                console.print(f"Schema: {schema_status}")
                
                # Node counts table
                counts_table = Table(title="Node Counts")
                counts_table.add_column("Type", style="bold")
                counts_table.add_column("Count", justify="right")
                
                counts_table.add_row("Documents", str(node_counts.get("docs", 0)))
                counts_table.add_row("Entities", str(node_counts.get("entities", 0)))
                
                console.print(counts_table)
                
                # Entity types if any exist
                if entity_types:
                    types_table = Table(title="Entity Types")
                    types_table.add_column("Entity Type", style="bold")
                    
                    for entity_type in entity_types:
                        types_table.add_row(entity_type)
                        
                    console.print(types_table)
                
                # Schema validation details
                if not validation["schema_valid"]:
                    validation_table = Table(title="Schema Issues")
                    validation_table.add_column("Issue Type", style="bold red")
                    validation_table.add_column("Missing Items")
                    
                    if validation["missing_constraints"]:
                        validation_table.add_row(
                            "Constraints", 
                            ", ".join(validation["missing_constraints"])
                        )
                    
                    if validation["missing_indexes"]:
                        validation_table.add_row(
                            "Indexes",
                            ", ".join(validation["missing_indexes"])
                        )
                        
                    console.print(validation_table)
                    console.print("[yellow]Run 'kg-forge neo4j init-schema' to fix schema issues[/yellow]")
                    
    except Neo4jConnectionError as e:
        _handle_connection_error(e, output)
        raise click.ClickException(f"Neo4j connection failed: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error getting database status: {e}")
        if output == "json":
            import json
            error_result = {"status": "error", "message": str(e)}
            print(json.dumps(error_result, indent=2))
        else:
            console.print(f"❌ [red]Error: {e}[/red]")
        raise click.ClickException(f"Status command failed: {e}")


@neo4j.command("clear-database")
@click.option(
    "--namespace",
    help="Clear only specified namespace (if not provided, clears entire database)"
)
@click.option(
    "--yes", 
    is_flag=True,
    help="Skip confirmation prompt"
)
@click.option(
    "--output",
    type=click.Choice(["table", "json", "raw"]),
    default="table",
    help="Output format"
)
def clear_database(namespace: Optional[str], yes: bool, output: str):
    """Clear database content (nodes and relationships)."""
    
    # Confirmation prompt
    if not yes:
        if namespace:
            msg = f"This will delete ALL nodes and relationships in namespace '{namespace}'"
        else:
            msg = "This will delete ALL nodes and relationships in the entire database"
            
        if not click.confirm(f"{msg}. Are you sure?"):
            console.print("Operation cancelled")
            return
    
    try:
        settings = get_settings()
        
        with Neo4jClient(settings) as client:
            deleted_count = client.clear_database(namespace)
            
            if output == "json":
                import json
                result = {
                    "status": "success",
                    "message": f"Database cleared successfully",
                    "namespace": namespace,
                    "deleted_nodes": deleted_count
                }
                print(json.dumps(result, indent=2))
                
            elif output == "raw":
                scope = f"namespace '{namespace}'" if namespace else "entire database"
                print(f"Cleared {scope}")
                print(f"Deleted nodes: {deleted_count}")
                
            else:  # table format
                scope = f"namespace '[cyan]{namespace}[/cyan]'" if namespace else "[red]entire database[/red]"
                console.print(f"✅ [green]Cleared {scope}[/green]")
                console.print(f"Deleted [bold]{deleted_count}[/bold] nodes")
                
    except Neo4jConnectionError as e:
        _handle_connection_error(e, output)
        raise click.ClickException(f"Neo4j connection failed: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error clearing database: {e}")
        if output == "json":
            import json
            error_result = {"status": "error", "message": str(e)}
            print(json.dumps(error_result, indent=2))
        else:
            console.print(f"❌ [red]Error: {e}[/red]")
        raise click.ClickException(f"Database clear failed: {e}")


@neo4j.command("start")
@click.option(
    "--detach", "-d",
    is_flag=True,
    help="Run container in detached mode"
)
def start(detach: bool):
    """Start Neo4j Docker container."""
    try:
        import subprocess
        
        # Check if container exists
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=neo4j-kg-forge", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if "neo4j-kg-forge" in result.stdout:
            # Container exists, start it
            console.print("Starting existing Neo4j container...")
            subprocess.run(["docker", "start", "neo4j-kg-forge"], check=True)
        else:
            # Create and start new container
            console.print("Creating new Neo4j container...")
            cmd = [
                "docker", "run",
                "--name", "neo4j-kg-forge",
                "-p", "7474:7474",
                "-p", "7687:7687", 
                "-e", "NEO4J_AUTH=neo4j/password",
                "-e", "NEO4J_PLUGINS=[\"apoc\"]",
                "neo4j:5.15"
            ]
            
            if not click.confirm("This will create a new Neo4j container. Continue?"):
                console.print("Operation cancelled")
                return
                
            if detach:
                cmd.append("-d")
                subprocess.run(cmd, check=True)
                console.print("✅ [green]Neo4j container started in detached mode[/green]")
            else:
                console.print("Starting Neo4j container (Ctrl+C to stop)...")
                subprocess.run(cmd, check=True)
        
        console.print("✅ [green]Neo4j container started[/green]")
        console.print("🌐 Web interface: http://localhost:7474")
        console.print("📡 Bolt connection: bolt://localhost:7687")
        console.print("🔐 Default credentials: neo4j/password")
        
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [red]Failed to start Neo4j container: {e}[/red]")
        raise click.ClickException("Failed to start Neo4j container")
        
    except FileNotFoundError:
        console.print("❌ [red]Docker not found. Please install Docker to use this command.[/red]")
        raise click.ClickException("Docker not available")


@neo4j.command("stop")
def stop():
    """Stop Neo4j Docker container."""
    try:
        import subprocess
        
        console.print("Stopping Neo4j container...")
        subprocess.run(["docker", "stop", "neo4j-kg-forge"], check=True)
        console.print("✅ [green]Neo4j container stopped[/green]")
        
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [red]Failed to stop Neo4j container: {e}[/red]")
        raise click.ClickException("Failed to stop Neo4j container")
        
    except FileNotFoundError:
        console.print("❌ [red]Docker not found. Please install Docker to use this command.[/red]")
        raise click.ClickException("Docker not available")


def _handle_connection_error(error: Neo4jConnectionError, output_format: str) -> None:
    """Handle Neo4j connection errors with appropriate output format."""
    if output_format == "json":
        import json
        error_result = {
            "status": "error",
            "connected": False,
            "error_type": "connection_error",
            "message": str(error)
        }
        print(json.dumps(error_result, indent=2))
    else:
        console.print(f"❌ [red]Neo4j Connection Error: {error}[/red]")
        console.print("\n[yellow]Troubleshooting tips:[/yellow]")
        console.print("• Check if Neo4j is running: [cyan]kg-forge neo4j start[/cyan]")
        console.print("• Verify connection settings in [cyan]kg_forge.yaml[/cyan]")
        console.print("• Test connection manually: [cyan]kg-forge neo4j test-connection[/cyan]")


def _handle_connection_failure(output_format: str) -> None:
    """Handle general connection test failures."""
    if output_format == "json":
        import json
        error_result = {
            "status": "error", 
            "connected": False,
            "message": "Connection test failed"
        }
        print(json.dumps(error_result, indent=2))
    else:
        console.print("❌ [red]Neo4j connection test failed[/red]")


def _handle_schema_error(error: SchemaError, output_format: str) -> None:
    """Handle schema-related errors."""
    if output_format == "json":
        import json
        error_result = {
            "status": "error",
            "error_type": "schema_error", 
            "message": str(error)
        }
        print(json.dumps(error_result, indent=2))
    else:
        console.print(f"❌ [red]Schema Error: {error}[/red]")

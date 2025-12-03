"""Neo4j operations commands for kg-forge CLI."""

import click
import subprocess
import time
from pathlib import Path
from typing import Optional
from rich.console import Console

from kg_forge.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


@click.command("neo4j-start")
@click.pass_context
def neo4j_start(ctx: click.Context) -> None:
    """
    Start Neo4j database instance using docker-compose.
    
    This command starts Neo4j in a Docker container and waits for it
    to be ready for connections.
    """
    settings = ctx.obj["settings"]
    
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
                    console.print(f"[green]✓[/green] Neo4j is ready at {settings.neo4j.uri}")
                    console.print(f"[blue]Browser UI:[/blue] http://localhost:7474")
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
        ctx.exit(1)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Failed to start Neo4j:[/red] {e.stderr}")
        ctx.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Unexpected error:[/red] {e}")
        ctx.exit(1)


@click.command("neo4j-stop")
@click.pass_context
def neo4j_stop(ctx: click.Context) -> None:
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
        ctx.exit(1)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Failed to stop Neo4j:[/red] {e.stderr}")
        ctx.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Unexpected error:[/red] {e}")
        ctx.exit(1)


@click.command("export-entities")
@click.option(
    "--output-dir", 
    type=click.Path(path_type=Path),
    default="entities_extract/",
    help="Directory to write entity markdown files"
)
@click.option(
    "--namespace", 
    default=None,
    help="Source namespace (alphanumeric only, default from config)"
)
@click.pass_context
def export_entities(
    ctx: click.Context,
    output_dir: Path,
    namespace: Optional[str] = None
) -> None:
    """
    Export entities from the knowledge graph to markdown files.
    
    This command extracts entity definitions from the Neo4j database
    and writes them back to markdown format in the entities_extract/ directory.
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
    
    logger.info(f"Exporting entities from namespace: [bold]{target_namespace}[/bold]")
    logger.info(f"Output directory: [bold]{output_dir}[/bold]")
    
    # Ensure output directory exists
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]Error creating output directory: {e}[/red]")
        ctx.exit(1)
    
    # TODO: Implement actual export logic in later steps
    console.print("[yellow]Entity export functionality will be implemented in Step 4[/yellow]")
    
    # For now, create a placeholder file to show the structure
    placeholder_content = f"""# Exported Entities

This directory will contain entity definitions exported from the knowledge graph.

**Namespace:** {target_namespace}
**Export Date:** (will be implemented)

## Entity Types

(Entity types will be listed here)

## Export Format

Each entity type will be exported as a separate markdown file following the format:

```markdown
# ID: <entity_type>
## Name: <Entity Type Display Name>
## Description: <Description for LLM extraction>
## Relations
  - <linked_entity_type> : <to_label> : <from_label>
## Examples:

### <example 1>
<additional description>
```
"""
    
    try:
        readme_path = output_dir / "README.md"
        with open(readme_path, 'w') as f:
            f.write(placeholder_content)
        console.print(f"[green]Placeholder README created at {readme_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error creating placeholder file: {e}[/red]")
        ctx.exit(1)
    
    logger.info("Export entities command completed")

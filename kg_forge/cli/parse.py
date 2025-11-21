"""Parse HTML command."""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from kg_forge.parsers import ConfluenceHTMLParser, DocumentLoader

console = Console()


@click.command(name="parse")
@click.option(
    "--source",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to HTML file or directory containing HTML files",
)
@click.option(
    "--show-content",
    is_flag=True,
    help="Display markdown content (can be long)",
)
@click.option(
    "--show-links",
    is_flag=True,
    help="Display extracted links",
)
def parse_html(source: Path, show_content: bool, show_links: bool):
    """
    Parse HTML files and display extracted information.
    
    This command demonstrates the HTML parser by showing what gets extracted
    from Confluence HTML exports: title, breadcrumb, links, and markdown content.
    """
    console.print(f"\n[bold blue]Parsing HTML from:[/bold blue] {source}\n")
    
    # Initialize parser and loader
    parser = ConfluenceHTMLParser()
    loader = DocumentLoader(parser)
    
    # Load documents
    try:
        if source.is_file():
            console.print("[yellow]Parsing single file...[/yellow]\n")
            documents = [parser.parse_file(source)]
        else:
            console.print("[yellow]Parsing directory...[/yellow]\n")
            documents = loader.load_from_directory(source)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return
    
    console.print(f"[green]✓ Successfully parsed {len(documents)} document(s)[/green]\n")
    
    # Display each document
    for i, doc in enumerate(documents, 1):
        console.print(f"[bold cyan]Document {i}:[/bold cyan] {doc.title}")
        console.print(f"  [dim]ID:[/dim] {doc.doc_id}")
        console.print(f"  [dim]Source:[/dim] {doc.source_file}")
        console.print(f"  [dim]Hash:[/dim] {doc.content_hash[:16]}...")
        
        # Breadcrumb
        if doc.breadcrumb:
            breadcrumb_str = " → ".join(doc.breadcrumb)
            console.print(f"  [dim]Path:[/dim] {breadcrumb_str}")
        
        # Links
        console.print(f"  [dim]Links:[/dim] {len(doc.links)} found")
        if show_links and doc.links:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Type", style="dim")
            table.add_column("Text")
            table.add_column("URL", style="cyan")
            
            for link in doc.links[:10]:  # Show first 10
                table.add_row(link.link_type, link.text, link.url)
            
            console.print(table)
            if len(doc.links) > 10:
                console.print(f"  [dim]... and {len(doc.links) - 10} more links[/dim]")
        
        # Content
        content_lines = doc.text.split('\n')
        console.print(f"  [dim]Content:[/dim] {len(content_lines)} lines, {len(doc.text)} characters")
        
        if show_content:
            console.print("\n[bold]Markdown Content:[/bold]")
            # Show first 50 lines
            preview = '\n'.join(content_lines[:50])
            console.print(f"[dim]{preview}[/dim]")
            if len(content_lines) > 50:
                console.print(f"\n[dim]... {len(content_lines) - 50} more lines[/dim]")
        
        console.print()  # Blank line between documents
    
    # Summary
    console.print("[bold green]Summary:[/bold green]")
    console.print(f"  Total documents: {len(documents)}")
    console.print(f"  Total links: {sum(len(doc.links) for doc in documents)}")
    console.print(f"  Total content: {sum(len(doc.text) for doc in documents):,} characters")

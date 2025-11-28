"""
CLI command for testing LLM entity extraction.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from kg_forge.config.settings import get_settings
from kg_forge.entities.definitions import EntityDefinitionLoader
from kg_forge.llm.prompt_builder import PromptBuilder
from kg_forge.llm.bedrock_extractor import BedrockLLMExtractor
from kg_forge.llm.fake_extractor import FakeLLMExtractor
from kg_forge.llm.exceptions import LLMError, ParseError, ValidationError, ExtractionAbortError


console = Console()


@click.command()
@click.argument('input_file', type=click.Path(exists=True, path_type=Path))
@click.option('--model', type=str, help='Override Bedrock model name from config')
@click.option('--fake-llm', is_flag=True, help='Use fake LLM instead of Bedrock (for testing)')
@click.option('--output-format', type=click.Choice(['json', 'text']), default='text',
              help='Output format (default: text)')
@click.option('--namespace', type=str, help='Namespace for entity definitions (default: "default")')
@click.option('--entities-dir', type=click.Path(exists=True, path_type=Path),
              help='Override entity definitions directory')
@click.option('--template-file', type=click.Path(exists=True, path_type=Path),
              help='Override prompt template file')
def llm_test(input_file: Path, model: Optional[str], fake_llm: bool, output_format: str,
             namespace: Optional[str], entities_dir: Optional[Path], template_file: Optional[Path]):
    """
    Test LLM entity extraction on a document.
    
    INPUT_FILE: Path to text file containing curated document content.
    """
    # Use quiet mode for JSON output
    quiet_mode = output_format == 'json'
    
    # Suppress logging in quiet mode
    if quiet_mode:
        logging.getLogger().setLevel(logging.WARNING)
        # Also suppress specific loggers that might be used
        logging.getLogger('kg_forge').setLevel(logging.WARNING)
        logging.getLogger('kg_forge.entities').setLevel(logging.WARNING)
        logging.getLogger('kg_forge.entities.definitions').setLevel(logging.WARNING)
    
    try:
        # Load configuration
        config = get_settings()
        
        # Set default namespace
        if not namespace:
            namespace = config.app.default_namespace
        
        # Set default entities directory
        if not entities_dir:
            entities_dir = Path(config.app.entities_extract_dir)
            if not entities_dir.exists():
                if not quiet_mode:
                    console.print(f"[red]Error: Entities directory not found: {entities_dir}[/red]")
                sys.exit(1)
        
        # Set default template file
        if not template_file:
            template_file = entities_dir / "prompt_template.md"
            if not template_file.exists():
                if not quiet_mode:
                    console.print(f"[red]Error: Template file not found: {template_file}[/red]")
                sys.exit(1)
        
        # Read input document content
        try:
            document_content = input_file.read_text(encoding='utf-8')
        except Exception as e:
            if not quiet_mode:
                console.print(f"[red]Error reading input file: {e}[/red]")
            sys.exit(1)
        
        # Initialize entity loader and prompt builder
        entity_loader = EntityDefinitionLoader()
        prompt_builder = PromptBuilder(entity_loader)
        
        # Build extraction prompt
        if not quiet_mode:
            console.print("[blue]Building extraction prompt...[/blue]")
        try:
            prompt = prompt_builder.build_prompt(document_content, entities_dir, template_file)
        except Exception as e:
            if not quiet_mode:
                console.print(f"[red]Error building prompt: {e}[/red]")
            sys.exit(1)
        
        # Initialize LLM client
        if not quiet_mode:
            console.print(f"[blue]Initializing LLM client (fake: {fake_llm})...[/blue]")
        try:
            if fake_llm:
                llm_client = FakeLLMExtractor()
            else:
                # Use model override or config default
                model_name = model or config.aws.bedrock_model_name
                llm_client = BedrockLLMExtractor(
                    model_name=model_name,
                    region=config.aws.default_region,
                    access_key_id=config.aws.access_key_id,
                    secret_access_key=config.aws.secret_access_key,
                    session_token=config.aws.session_token,
                    profile_name=config.aws.profile_name,
                    max_tokens=config.aws.bedrock_max_tokens,
                    temperature=config.aws.bedrock_temperature
                )
        except Exception as e:
            if not quiet_mode:
                console.print(f"[red]Error initializing LLM client: {e}[/red]")
            sys.exit(1)
        
        # Perform entity extraction
        if not quiet_mode:
            console.print("[blue]Extracting entities...[/blue]")
        try:
            result = llm_client.extract_entities(prompt)
            if not quiet_mode:
                console.print(f"[green]Extraction successful! Found {len(result.entities)} entities.[/green]")
            
        except (LLMError, ParseError, ValidationError, ExtractionAbortError) as e:
            if not quiet_mode:
                console.print(f"[red]Extraction failed: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            if not quiet_mode:
                console.print(f"[red]Unexpected error during extraction: {e}[/red]")
            sys.exit(1)
        
        # Display results
        if output_format == 'json':
            # Output as JSON
            output_data = {
                "entities": [
                    {
                        "type": entity.type,
                        "name": entity.name,
                        "confidence": entity.confidence
                    }
                    for entity in result.entities
                ]
            }
            # Print directly to stdout for valid JSON output
            print(json.dumps(output_data, indent=2))
        else:
            # Output as formatted text table
            if result.entities:
                table = Table(title="Extracted Entities")
                table.add_column("Type", style="cyan")
                table.add_column("Name", style="green")
                table.add_column("Confidence", style="yellow")
                
                for entity in result.entities:
                    table.add_row(entity.type, entity.name, f"{entity.confidence:.2f}")
                
                console.print(table)
            else:
                console.print("[yellow]No entities extracted.[/yellow]")
        
        if not quiet_mode:
            console.print(f"[green]✓ LLM test completed successfully[/green]")
        
    except KeyboardInterrupt:
        if not quiet_mode:
            console.print("[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        if not quiet_mode:
            console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)
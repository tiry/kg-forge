"""CLI command for running the end-to-end pipeline."""

import click
import logging

from kg_forge.pipeline import PipelineOrchestrator, PipelineError, register_default_hooks
from kg_forge.models.pipeline import PipelineConfig
from kg_forge.extractors.factory import create_extractor
from kg_forge.graph.factory import get_graph_client
from kg_forge.config.settings import Settings

logger = logging.getLogger(__name__)


@click.command('pipeline')
@click.argument('source_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    '--namespace',
    default='default',
    help='Graph namespace for organizing entities'
)
@click.option(
    '--types', '-t',
    multiple=True,
    help='Entity types to extract (can specify multiple times). If not specified, extracts all types.'
)
@click.option(
    '--min-confidence',
    default=0.0,
    type=float,
    help='Minimum confidence threshold for extracted entities (0.0-1.0)'
)
@click.option(
    '--skip-processed/--reprocess',
    default=True,
    help='Skip already processed documents based on content hash'
)
@click.option(
    '--batch-size',
    default=10,
    type=int,
    help='Number of documents to process in each batch'
)
@click.option(
    '--max-failures',
    default=5,
    type=int,
    help='Maximum consecutive failures before aborting pipeline'
)
@click.option(
    '--interactive/--no-interactive',
    '--biraj',
    default=False,
    is_flag=True,
    help='Enable interactive mode for human-in-the-loop entity merging and validation'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Extract entities but do not write to graph (useful for testing)'
)
def run_pipeline(
    source_dir: str,
    namespace: str,
    types: tuple,
    min_confidence: float,
    skip_processed: bool,
    batch_size: int,
    max_failures: int,
    interactive: bool,
    dry_run: bool
):
    """
    Run the complete knowledge graph construction pipeline.
    
    This command orchestrates the end-to-end process:
    
    \b
    1. Load HTML documents from SOURCE_DIR
    2. Extract entities using LLM
    3. Apply normalization hooks (enabled by default)
    4. Ingest entities into Neo4j graph database
    5. Run deduplication hooks (optional, interactive mode)
    
    \b
    Examples:
        # Basic usage
        kg-forge pipeline test_data/
        
        # Specify namespace and entity types
        kg-forge pipeline test_data/ --namespace confluence --types product --types component
        
        # Interactive mode for entity merging
        kg-forge pipeline test_data/ --interactive
        
        # Dry run to test extraction without writing to graph
        kg-forge pipeline test_data/ --dry-run
        
        # Reprocess all documents (ignore cache)
        kg-forge pipeline test_data/ --reprocess
    """
    # Display banner
    click.echo("=" * 70)
    click.echo("🚀  Knowledge Graph Pipeline")
    click.echo("=" * 70)
    click.echo(f"📂 Source:       {source_dir}")
    click.echo(f"🏷️  Namespace:    {namespace}")
    
    if types:
        click.echo(f"🔖 Entity types: {', '.join(types)}")
    else:
        click.echo("🔖 Entity types: all")
    
    click.echo(f"📊 Min confidence: {min_confidence}")
    click.echo(f"♻️  Skip processed: {'Yes' if skip_processed else 'No'}")
    
    if interactive:
        click.echo("👤 Interactive:  ENABLED (human-in-the-loop)")
    
    if dry_run:
        click.echo("🧪 Dry run:      ENABLED (no writes to graph)")
    
    click.echo("=" * 70)
    click.echo()
    
    # Create configuration
    config = PipelineConfig(
        namespace=namespace,
        source_dir=source_dir,
        entity_types=list(types) if types else None,
        min_confidence=min_confidence,
        skip_processed=skip_processed,
        batch_size=batch_size,
        max_failures=max_failures,
        interactive=interactive,
        dry_run=dry_run
    )
    
    # Initialize components
    try:
        click.echo("⚙️  Initializing components...")
        settings = Settings()
        extractor = create_extractor()
        graph_client = get_graph_client(settings)
        
        # Connect to database (unless dry run)
        if not dry_run:
            graph_client.connect()
        
        # Register hooks based on interactive flag
        register_default_hooks(interactive=interactive)
        
        click.echo("✅ Components initialized")
        click.echo()
    except Exception as e:
        click.echo(f"\n❌ Initialization failed: {e}", err=True)
        raise click.Abort()
    
    # Run pipeline
    orchestrator = PipelineOrchestrator(config, extractor, graph_client)
    
    try:
        stats = orchestrator.run()
        
        # Display results
        click.echo()
        click.echo("=" * 70)
        click.echo("📊 Pipeline Results")
        click.echo("=" * 70)
        click.echo(f"📄 Total documents:     {stats.total_documents}")
        click.echo(f"✅ Processed:           {stats.processed}")
        click.echo(f"⏭️  Skipped:             {stats.skipped}")
        click.echo(f"❌ Failed:              {stats.failed}")
        click.echo(f"📈 Success rate:        {stats.success_rate:.1f}%")
        click.echo(f"🏷️  Total entities:      {stats.total_entities}")
        click.echo(f"🔗 Total relationships: {stats.total_relationships}")
        click.echo(f"⏱️  Duration:            {stats.duration:.2f}s")
        click.echo("=" * 70)
        
        # Show errors if any
        if stats.errors:
            click.echo()
            click.echo("⚠️  Errors encountered:")
            click.echo()
            
            # Show first 10 errors
            for i, error in enumerate(stats.errors[:10], 1):
                click.echo(f"  {i}. {error}")
            
            if len(stats.errors) > 10:
                remaining = len(stats.errors) - 10
                click.echo(f"  ... and {remaining} more error(s)")
            
            click.echo()
        
        # Exit with error code if there were failures
        if stats.failed > 0:
            click.echo(f"⚠️  Pipeline completed with {stats.failed} failure(s)")
            raise click.Exit(1)
        else:
            click.echo()
            click.echo("✨ Pipeline completed successfully!")
            
    except PipelineError as e:
        click.echo(f"\n❌ Pipeline error: {e}", err=True)
        raise click.Abort()
    except KeyboardInterrupt:
        click.echo("\n\n⚠️  Pipeline interrupted by user", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"\n❌ Unexpected error: {e}", err=True)
        logger.exception("Pipeline failed with unexpected error")
        raise click.Abort()
    finally:
        # Always close database connection
        if not dry_run and graph_client:
            try:
                graph_client.close()
            except:
                pass

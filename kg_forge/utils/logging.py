"""Logging configuration for kg-forge."""

import logging
import sys
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console


def setup_logging(log_level: str = "INFO", rich_console: Optional[Console] = None) -> None:
    """
    Setup logging configuration with Rich handler for enhanced output.
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        rich_console: Optional Rich console instance
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create console if not provided
    if rich_console is None:
        rich_console = Console(stderr=True)
    
    # Setup Rich handler
    rich_handler = RichHandler(
        console=rich_console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        markup=True
    )
    
    # Configure logging format
    formatter = logging.Formatter(
        fmt="%(message)s",
        datefmt="[%X]"
    )
    rich_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add Rich handler
    root_logger.addHandler(rich_handler)
    
    # Setup application logger
    app_logger = logging.getLogger("kg_forge")
    app_logger.setLevel(numeric_level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f"kg_forge.{name}")

"""Verbose logging utilities for CLI commands."""

import sys
from typing import Optional, Dict, Any
import logging


class VerboseLogger:
    """
    Handles verbose output formatting across CLI commands.
    
    Provides structured, formatted output for debugging and transparency
    in CLI operations, particularly for LLM interactions.
    """
    
    # Unicode box drawing characters
    THICK_LINE = "━" * 60
    THIN_LINE = "─" * 60
    
    def __init__(self, enabled: bool, logger: Optional[logging.Logger] = None):
        """
        Initialize VerboseLogger.
        
        Args:
            enabled: Whether verbose mode is enabled
            logger: Optional logger instance (defaults to stderr)
        """
        self.enabled = enabled
        self.logger = logger
    
    def _print(self, message: str, file=None):
        """
        Print message to appropriate output stream.
        
        Args:
            message: Message to print
            file: File stream (defaults to stderr for verbose output)
        """
        if not self.enabled:
            return
        
        if file is None:
            file = sys.stderr
        
        print(message, file=file)
    
    def section_header(self, title: str, icon: str = ""):
        """
        Print a section header with thick line separators.
        
        Args:
            title: Section title
            icon: Optional emoji or icon prefix
        """
        if not self.enabled:
            return
        
        header_text = f"{icon} {title}" if icon else title
        self._print(self.THICK_LINE)
        self._print(header_text)
        self._print(self.THICK_LINE)
    
    def subsection_header(self, title: str, icon: str = ""):
        """
        Print a subsection header with thin line separators.
        
        Args:
            title: Subsection title
            icon: Optional emoji or icon prefix
        """
        if not self.enabled:
            return
        
        header_text = f"{icon} {title}" if icon else title
        self._print("")
        self._print(self.THIN_LINE)
        self._print(header_text)
        self._print(self.THIN_LINE)
    
    def llm_request(
        self,
        entity_type: str,
        model: str,
        prompt: str,
        tokens: Optional[int] = None
    ):
        """
        Log LLM request details.
        
        Args:
            entity_type: Type of entity being extracted
            model: LLM model identifier
            prompt: Full prompt text
            tokens: Optional estimated token count
        """
        if not self.enabled:
            return
        
        self.section_header("LLM EXTRACTION REQUEST", "🔍")
        self._print(f"Entity Type: {entity_type}")
        self._print(f"Model: {model}")
        
        if tokens:
            self._print(f"Estimated Tokens: ~{tokens:,}")
        
        self.subsection_header("PROMPT", "📤")
        self._print(prompt)
    
    def llm_response(
        self,
        response: str,
        elapsed_time: float,
        tokens: Optional[Dict[str, int]] = None,
        status: str = "success"
    ):
        """
        Log LLM response details.
        
        Args:
            response: Raw LLM response text
            elapsed_time: Time taken for the request (seconds)
            tokens: Optional token usage dict with 'input', 'output', 'total' keys
            status: Request status ('success', 'error', etc.)
        """
        if not self.enabled:
            return
        
        status_icon = "✓" if status == "success" else "✗"
        header = f"LLM RESPONSE (took {elapsed_time:.1f}s)"
        
        self.section_header(header, "📥")
        
        if tokens:
            input_tokens = tokens.get('input', 0)
            output_tokens = tokens.get('output', 0)
            total_tokens = tokens.get('total', input_tokens + output_tokens)
            self._print(
                f"Tokens Used: {input_tokens:,} input + {output_tokens:,} output = {total_tokens:,} total"
            )
        
        self._print(f"Status: {status_icon} {status.title()}")
        
        self.subsection_header("RAW RESPONSE", "📄")
        self._print(response)
        self._print(self.THICK_LINE)
        self._print("")  # Empty line after section
    
    def operation(self, operation_name: str, details: Dict[str, Any]):
        """
        Log a generic operation with details.
        
        This is a flexible method for logging various operations
        in different commands (future extensibility).
        
        Args:
            operation_name: Name of the operation
            details: Dictionary of operation details
        """
        if not self.enabled:
            return
        
        self.section_header(operation_name.upper(), "⚙️")
        
        for key, value in details.items():
            self._print(f"{key}: {value}")
        
        self._print(self.THICK_LINE)
        self._print("")
    
    def info(self, message: str):
        """
        Log an informational message.
        
        Args:
            message: Message to log
        """
        if not self.enabled:
            return
        
        self._print(f"ℹ️  {message}")
    
    def warning(self, message: str):
        """
        Log a warning message.
        
        Args:
            message: Warning message
        """
        if not self.enabled:
            return
        
        self._print(f"⚠️  {message}")
    
    def error(self, message: str):
        """
        Log an error message.
        
        Args:
            message: Error message
        """
        if not self.enabled:
            return
        
        self._print(f"❌ {message}")


def create_verbose_logger(
    enabled: bool,
    logger: Optional[logging.Logger] = None
) -> VerboseLogger:
    """
    Factory function to create a VerboseLogger instance.
    
    Args:
        enabled: Whether verbose mode is enabled
        logger: Optional logger instance
    
    Returns:
        VerboseLogger instance
    """
    return VerboseLogger(enabled=enabled, logger=logger)

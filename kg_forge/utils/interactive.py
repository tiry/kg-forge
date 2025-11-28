"""
Interactive session utilities for CLI user interaction.
"""

import sys
from typing import List, Optional, Dict, Any


class InteractiveSession:
    """
    Provides utilities for interactive user prompts and confirmations.
    
    Used when --interactive/--biraj flag is enabled to allow user
    interaction during batch processing hooks.
    """
    
    def __init__(self, enabled: bool = True):
        """
        Initialize interactive session.
        
        Args:
            enabled: Whether interactive prompts are enabled
        """
        self.enabled = enabled
    
    def prompt(self, message: str, default: Optional[str] = None) -> str:
        """
        Prompt user for text input.
        
        Args:
            message: Prompt message to display
            default: Default value if user enters nothing
            
        Returns:
            User input or default value
        """
        if not self.enabled:
            return default or ""
        
        try:
            if default:
                response = input(f"{message} [{default}]: ").strip()
                return response if response else default
            else:
                return input(f"{message}: ").strip()
                
        except (KeyboardInterrupt, EOFError):
            print("\nInteractive session cancelled")
            return default or ""
    
    def confirm(self, message: str, default: bool = False) -> bool:
        """
        Prompt user for yes/no confirmation.
        
        Args:
            message: Confirmation message to display
            default: Default value if user enters nothing
            
        Returns:
            True for yes, False for no
        """
        if not self.enabled:
            return default
        
        default_text = "Y/n" if default else "y/N"
        
        try:
            response = input(f"{message} [{default_text}]: ").strip().lower()
            
            if not response:
                return default
            
            return response in ['y', 'yes', 'true', '1']
            
        except (KeyboardInterrupt, EOFError):
            print("\nInteractive session cancelled")
            return default
    
    def select_from_list(self, message: str, choices: List[str], 
                        default: Optional[int] = None) -> Optional[str]:
        """
        Prompt user to select from a list of choices.
        
        Args:
            message: Selection message to display
            choices: List of choices to select from
            default: Default choice index (0-based)
            
        Returns:
            Selected choice or None if cancelled
        """
        if not self.enabled or not choices:
            if default is not None and 0 <= default < len(choices):
                return choices[default]
            return None
        
        print(f"\n{message}")
        for i, choice in enumerate(choices):
            marker = " (default)" if i == default else ""
            print(f"  {i + 1}. {choice}{marker}")
        
        try:
            response = input("Enter choice (number): ").strip()
            
            if not response and default is not None:
                return choices[default]
            
            try:
                choice_num = int(response) - 1
                if 0 <= choice_num < len(choices):
                    return choices[choice_num]
                else:
                    print(f"Invalid choice. Please select 1-{len(choices)}")
                    return None
                    
            except ValueError:
                print("Invalid input. Please enter a number.")
                return None
                
        except (KeyboardInterrupt, EOFError):
            print("\nInteractive session cancelled")
            return None
    
    def display_table(self, title: str, data: List[Dict[str, Any]], 
                     max_rows: int = 20) -> None:
        """
        Display tabular data with optional pagination.
        
        Args:
            title: Table title
            data: List of dictionaries to display as rows
            max_rows: Maximum rows to display before pagination
        """
        if not self.enabled or not data:
            return
        
        print(f"\n{title}")
        print("-" * len(title))
        
        # Display headers
        if data:
            headers = list(data[0].keys())
            print(" | ".join(f"{h:15}" for h in headers))
            print("-" * (len(headers) * 18 - 3))
        
        # Display rows with pagination
        for i, row in enumerate(data):
            if i > 0 and i % max_rows == 0:
                if not self.confirm("Continue displaying results?", default=True):
                    break
            
            values = [str(row.get(h, ""))[:15] for h in headers]
            print(" | ".join(f"{v:15}" for v in values))
    
    def print_info(self, message: str) -> None:
        """Print informational message."""
        if self.enabled:
            print(f"INFO: {message}")
    
    def print_warning(self, message: str) -> None:
        """Print warning message."""
        if self.enabled:
            print(f"WARNING: {message}")
    
    def print_error(self, message: str) -> None:
        """Print error message."""
        if self.enabled:
            print(f"ERROR: {message}")
    
    def pause(self, message: str = "Press Enter to continue...") -> None:
        """Pause execution for user input."""
        if self.enabled:
            try:
                input(message)
            except (KeyboardInterrupt, EOFError):
                print("\nContinuing...")
"""
Content hashing utilities for idempotent ingest.
"""

import hashlib
import json
from typing import Any, Dict

from kg_forge.models.document import ParsedDocument


def compute_content_hash(document: ParsedDocument) -> str:
    """
    Compute MD5 hash of curated document content for change detection.
    
    Args:
        document: CuratedDocument object from Step 2
        
    Returns:
        MD5 hash string (32 characters)
        
    Notes:
        - Hashes the curated text content, title, and metadata
        - Excludes timestamps and file paths that might change
        - Provides stable hash for idempotent ingest
    """
    # Create a dictionary with content that should trigger re-processing when changed
    hashable_content = {
        'title': document.title or '',
        'content': document.text or '',
        'breadcrumb': document.breadcrumb or [],
        # Include links as they're part of the content structure
        'links': sorted([
            {
                'text': link.text,
                'url': link.url,
                'type': link.link_type
            }
            for link in document.links
        ], key=lambda x: (x['text'], x['url']))
    }
    
    # Convert to JSON string for consistent hashing
    content_json = json.dumps(hashable_content, sort_keys=True, separators=(',', ':'))
    
    # Compute MD5 hash
    return hashlib.md5(content_json.encode('utf-8')).hexdigest()


def compute_string_hash(content: str) -> str:
    """
    Compute MD5 hash of a string (utility function).
    
    Args:
        content: String content to hash
        
    Returns:
        MD5 hash string (32 characters)
    """
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def compute_dict_hash(data: Dict[str, Any]) -> str:
    """
    Compute MD5 hash of a dictionary (utility function).
    
    Args:
        data: Dictionary to hash
        
    Returns:
        MD5 hash string (32 characters)
    """
    # Convert to JSON string for consistent hashing
    content_json = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.md5(content_json.encode('utf-8')).hexdigest()
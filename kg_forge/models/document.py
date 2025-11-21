"""Document models for parsed HTML content."""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class DocumentLink(BaseModel):
    """Represents a link found in the document."""

    url: str = Field(..., description="Link URL")
    text: str = Field(..., description="Link text/anchor")
    link_type: str = Field(..., description="Link type: 'internal' or 'external'")


class ParsedDocument(BaseModel):
    """Parsed Confluence HTML document compatible with LlamaIndex."""

    # Core LlamaIndex-compatible fields
    doc_id: str = Field(..., description="Unique document identifier from filename")
    text: str = Field(..., description="Content in Markdown format")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    # Additional fields for our use case
    title: str = Field(..., description="Document title")
    breadcrumb: List[str] = Field(
        default_factory=list, description="Breadcrumb path"
    )
    links: List[DocumentLink] = Field(
        default_factory=list, description="Links found in document"
    )
    content_hash: str = Field(..., description="SHA-256 hash of markdown content")
    source_file: str = Field(..., description="Original HTML filename")
    parsed_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when document was parsed"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "doc_id": "3352431259",
                "title": "Content Lake",
                "text": "# Content Lake\n\nThis is the content...",
                "breadcrumb": ["Thierry Delprat", "Thierry Delprat Home"],
                "links": [
                    {
                        "url": "index.html",
                        "text": "Home",
                        "link_type": "internal",
                    }
                ],
                "content_hash": "abc123...",
                "source_file": "Content-Lake_3352431259.html",
                "metadata": {},
            }
        }
    )

    def to_llamaindex_document(self) -> Dict[str, Any]:
        """
        Convert to LlamaIndex Document format.

        Returns:
            Dict compatible with LlamaIndex Document class
        """
        # Prepare metadata dict with all our custom fields
        metadata = {
            "title": self.title,
            "breadcrumb": self.breadcrumb,
            "links": [link.model_dump() for link in self.links],
            "content_hash": self.content_hash,
            "source_file": self.source_file,
            "parsed_at": self.parsed_at.isoformat(),
            **self.metadata,  # Include any additional metadata
        }

        # Return dict compatible with LlamaIndex Document
        return {"doc_id": self.doc_id, "text": self.text, "metadata": metadata}

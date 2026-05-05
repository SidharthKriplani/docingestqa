class DocIngestQAError(Exception):
    """Base exception for DocIngestQA."""


class InvalidChunkInputError(DocIngestQAError):
    """Raised when chunk input cannot be read or validated."""


class InvalidManifestError(DocIngestQAError):
    """Raised when a source manifest is malformed."""

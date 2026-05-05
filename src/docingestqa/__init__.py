"""DocIngestQA — pre-indexing QA auditor for RAG document ingestion chunks."""

from docingestqa._version import __version__
from docingestqa.auditor import IngestionAuditor
from docingestqa.config import AuditConfig
from docingestqa.models import CheckResult, Chunk, DocumentSpec, Issue
from docingestqa.checks import (
    check_chunk_length,
    check_chunk_overlap,
    check_document_coverage,
    check_duplicates,
    check_encoding_health,
    check_input_summary,
    check_metadata_completeness,
    check_ocr_noise,
    check_page_coverage,
    check_source_distribution,
    check_split_quality,
)

__all__ = [
    "__version__",
    "IngestionAuditor",
    "AuditConfig",
    "CheckResult",
    "Chunk",
    "DocumentSpec",
    "Issue",
    "check_chunk_length",
    "check_chunk_overlap",
    "check_document_coverage",
    "check_duplicates",
    "check_encoding_health",
    "check_input_summary",
    "check_metadata_completeness",
    "check_ocr_noise",
    "check_page_coverage",
    "check_source_distribution",
    "check_split_quality",
]

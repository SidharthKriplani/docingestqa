from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
from docingestqa.config import AuditConfig
from docingestqa.readers import read_chunks, read_manifest
from docingestqa.report import IngestionAuditReport, build_payload


@dataclass(frozen=True)
class IngestionAuditor:
    """Audit already-ingested document chunks before indexing them.

    Parameters
    ----------
    chunks_path:
        Path to JSONL, JSON, or CSV containing generated chunks.
    documents_path:
        Optional path to a source manifest JSON.
        Without this, metadata/chunk-level checks still run, but document/page coverage
        checks return INSUFFICIENT_INPUT.
    config:
        Threshold configuration. Defaults are conservative.
    """

    chunks_path: str | Path
    documents_path: str | Path | None = None
    config: AuditConfig = AuditConfig()

    def run(self) -> IngestionAuditReport:
        chunks = read_chunks(self.chunks_path)
        manifest = read_manifest(self.documents_path)
        checks = [
            check_input_summary(chunks, manifest),
            check_metadata_completeness(chunks, self.config),
            check_document_coverage(chunks, manifest),
            check_page_coverage(chunks, manifest),
            check_chunk_length(chunks, self.config),
            check_ocr_noise(chunks, self.config),
            check_duplicates(chunks, self.config),
            check_source_distribution(chunks),
            check_chunk_overlap(chunks, self.config),
            check_encoding_health(chunks, self.config),
            check_split_quality(chunks, self.config),
        ]
        payload = build_payload(
            checks=checks,
            chunk_count=len(chunks),
            manifest_count=len(manifest),
            chunks_path=str(self.chunks_path),
            documents_path=str(self.documents_path) if self.documents_path is not None else None,
        )
        return IngestionAuditReport(payload)

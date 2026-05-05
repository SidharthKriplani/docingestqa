from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class AuditConfig:
    """Thresholds for all ingestion quality checks. All fields have safe defaults."""

    # chunk length
    min_chunk_chars: int = 80
    max_chunk_chars: int = 2_000

    # OCR / noise
    noisy_text_ratio_threshold: float = 0.35
    replacement_char_threshold: int = 2
    repeated_char_run_threshold: int = 8
    warn_noisy_chunk_rate: float = 0.05
    fail_noisy_chunk_rate: float = 0.20

    # metadata
    warn_missing_metadata_rate: float = 0.0
    fail_missing_metadata_rate: float = 0.20

    # empty chunks
    warn_empty_chunk_rate: float = 0.0
    fail_empty_chunk_rate: float = 0.05

    # duplicates
    near_duplicate_jaccard_threshold: float = 0.88
    ngram_size: int = 5
    max_duplicate_examples: int = 25
    warn_duplicate_pair_count: int = 1
    fail_duplicate_pair_count: int = 20

    # chunk overlap (v0.2)
    overlap_ngram_size: int = 4
    overlap_jaccard_warn_threshold: float = 0.40
    overlap_jaccard_fail_threshold: float = 0.70
    warn_overlap_pair_count: int = 3
    fail_overlap_pair_count: int = 15

    # encoding health (v0.2)
    null_byte_fail_threshold: int = 1
    mojibake_warn_rate: float = 0.05
    mojibake_fail_rate: float = 0.20

    # split quality (v0.2)
    warn_bad_split_rate: float = 0.10
    fail_bad_split_rate: float = 0.30

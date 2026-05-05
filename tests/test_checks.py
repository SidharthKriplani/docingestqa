from __future__ import annotations

from docingestqa.checks import (
    check_chunk_length,
    check_chunk_overlap,
    check_document_coverage,
    check_duplicates,
    check_encoding_health,
    check_metadata_completeness,
    check_ocr_noise,
    check_page_coverage,
    check_split_quality,
)
from docingestqa.config import AuditConfig
from docingestqa.models import Chunk, DocumentSpec


def test_metadata_completeness_warns_missing_source_or_page():
    chunks = [Chunk(text="hello", source="a.pdf", page=1), Chunk(text="missing source and page")]
    result = check_metadata_completeness(chunks, AuditConfig())
    assert result.status == "FAIL"
    assert result.metrics["missing_source_count"] == 1
    assert result.metrics["missing_page_count"] == 1


def test_document_coverage_detects_missing_and_orphan_sources():
    chunks = [Chunk(text="hello", source="a.pdf", page=1), Chunk(text="legacy", source="legacy.pdf", page=1)]
    manifest = [DocumentSpec(source="a.pdf", pages=1), DocumentSpec(source="b.pdf", pages=1)]
    result = check_document_coverage(chunks, manifest)
    assert result.status == "FAIL"
    assert "b.pdf" in result.metrics["missing_documents"]
    assert "legacy.pdf" in result.metrics["orphan_sources"]


def test_page_coverage_detects_missing_pages_and_extra_pages():
    chunks = [Chunk(text="p1", source="a.pdf", page=1), Chunk(text="p4", source="a.pdf", page=4)]
    manifest = [DocumentSpec(source="a.pdf", pages=3)]
    result = check_page_coverage(chunks, manifest)
    assert result.status == "FAIL"
    assert result.metrics["missing_page_total"] == 2
    assert result.metrics["extra_page_total"] == 1


def test_chunk_length_detects_empty_short_and_long():
    chunks = [
        Chunk(text="", source="a.pdf", page=1),
        Chunk(text="short", source="a.pdf", page=1),
        Chunk(text="x" * 101, source="a.pdf", page=1),
    ]
    result = check_chunk_length(chunks, AuditConfig(min_chunk_chars=10, max_chunk_chars=100))
    assert result.status == "FAIL"
    assert result.metrics["empty_chunk_count"] == 1
    assert result.metrics["short_chunk_count"] == 1
    assert result.metrics["long_chunk_count"] == 1


def test_ocr_noise_flags_replacement_characters():
    chunks = [Chunk(text="valid sentence"), Chunk(text="��� broken text")]
    result = check_ocr_noise(chunks, AuditConfig(replacement_char_threshold=2))
    assert result.status == "FAIL"
    assert result.metrics["noisy_chunk_count"] == 1


def test_duplicates_detects_exact_duplicate_pairs():
    chunks = [
        Chunk(text="This is a longer duplicated policy sentence for testing.", chunk_id="a"),
        Chunk(text="This is a longer duplicated policy sentence for testing.", chunk_id="b"),
    ]
    result = check_duplicates(chunks, AuditConfig())
    assert result.status == "WARN"
    assert result.metrics["duplicate_pair_count"] == 1


# ── v0.2 tests ────────────────────────────────────────────────────────────────

def test_chunk_overlap_flags_high_overlap_consecutive_chunks():
    """Consecutive chunks from the same source with near-identical text should be flagged."""
    # Nearly identical — only last sentence differs; shares most 4-grams
    base = ("The system stores user credentials using bcrypt with a cost factor of 12. "
            "Password reset tokens are single-use and expire after 30 minutes. "
            "All authentication events are written to the audit log.")
    text_b = ("The system stores user credentials using bcrypt with a cost factor of 12. "
              "Password reset tokens are single-use and expire after 30 minutes. "
              "Failed login attempts beyond five trigger a 15-minute account lockout.")
    chunks = [
        Chunk(text=base, source="spec.pdf", page=2, chunk_id="c1"),
        Chunk(text=text_b, source="spec.pdf", page=2, chunk_id="c2"),
    ]
    cfg = AuditConfig(overlap_jaccard_warn_threshold=0.40, overlap_jaccard_fail_threshold=0.70,
                      warn_overlap_pair_count=1, fail_overlap_pair_count=5)
    result = check_chunk_overlap(chunks, cfg)
    assert result.status in ("WARN", "FAIL")
    assert result.metrics["total_flagged_pairs"] >= 1


def test_chunk_overlap_passes_for_distinct_chunks():
    chunks = [
        Chunk(text="Revenue grew 14 percent driven by enterprise sales.", source="a.pdf", page=1),
        Chunk(text="Operating expenses decreased due to automation initiatives.", source="a.pdf", page=2),
    ]
    result = check_chunk_overlap(chunks, AuditConfig())
    assert result.status == "PASS"
    assert result.metrics["total_flagged_pairs"] == 0


def test_encoding_health_detects_mojibake():
    """Chunks containing mojibake patterns (Ã© etc.) should be flagged."""
    chunks = [
        Chunk(text="Normal text without issues.", source="a.pdf", page=1),
        Chunk(text="The metric was significant (Ã© = 0.92, p < 0.001).", source="b.pdf", page=3),
    ]
    result = check_encoding_health(chunks, AuditConfig())
    assert result.status in ("WARN", "FAIL")
    assert result.metrics["mojibake_chunks"] == 1


def test_encoding_health_passes_clean_chunks():
    chunks = [
        Chunk(text="Clean UTF-8 text with no issues.", source="a.pdf", page=1),
        Chunk(text="Another perfectly fine chunk.", source="a.pdf", page=2),
    ]
    result = check_encoding_health(chunks, AuditConfig())
    assert result.status == "PASS"
    assert result.metrics["total_flagged"] == 0


def test_split_quality_flags_mid_sentence_start():
    """Chunks that begin with a lowercase word should be flagged as mid-sentence starts."""
    chunks = [
        Chunk(text="and must be acknowledged before accessing production systems.", source="a.pdf", page=2),
        Chunk(text="This is a properly started sentence.", source="a.pdf", page=3),
    ]
    result = check_split_quality(chunks, AuditConfig())
    assert result.status in ("WARN", "FAIL")
    assert result.metrics["mid_sentence_starts"] >= 1


def test_split_quality_flags_navigation_fragments():
    """Bare page numbers and TOC markers should be flagged as navigation fragments."""
    chunks = [
        Chunk(text="42", source="manual.pdf", page=5),
        Chunk(text="Table of Contents", source="manual.pdf", page=1),
        Chunk(text="This is a normal chunk with real content.", source="manual.pdf", page=2),
    ]
    result = check_split_quality(chunks, AuditConfig())
    assert result.metrics["navigation_fragments"] == 2


def test_split_quality_passes_clean_chunks():
    chunks = [
        Chunk(text="All employees must complete annual compliance training by December 31st.", source="a.pdf", page=1),
        Chunk(text="The review cycle occurs twice per year in June and December.", source="a.pdf", page=2),
    ]
    result = check_split_quality(chunks, AuditConfig())
    assert result.status == "PASS"


# ── edge case tests ───────────────────────────────────────────────────────────

def test_empty_chunk_list_metadata_completeness():
    """Empty chunk list: no missing metadata → PASS with zero counts."""
    result = check_metadata_completeness([], AuditConfig())
    assert result.status == "PASS"
    assert result.metrics["missing_source_count"] == 0
    assert result.metrics["missing_page_count"] == 0


def test_empty_chunk_list_duplicates():
    """Empty chunk list produces no duplicate pairs."""
    result = check_duplicates([], AuditConfig())
    assert result.metrics["duplicate_pair_count"] == 0


def test_single_chunk_no_overlap():
    """A single chunk has no pairs to compare — overlap check must not crash."""
    chunks = [Chunk(text="The system stores credentials securely using bcrypt.", source="a.pdf", page=1)]
    result = check_chunk_overlap(chunks, AuditConfig())
    assert result.metrics["total_flagged_pairs"] == 0


def test_all_chunks_missing_metadata():
    """When every chunk lacks source and page, rate hits 1.0 → FAIL."""
    chunks = [Chunk(text="orphan chunk one"), Chunk(text="orphan chunk two")]
    result = check_metadata_completeness(chunks, AuditConfig())
    assert result.status == "FAIL"
    assert result.metrics["missing_source_count"] == 2
    assert result.metrics["missing_page_count"] == 2


def test_ocr_noise_clean_chunks_passes():
    """Chunks with no replacement characters → PASS."""
    chunks = [
        Chunk(text="Clean text without any OCR artifacts.", source="a.pdf", page=1),
        Chunk(text="Another well-extracted sentence from the document.", source="a.pdf", page=2),
    ]
    result = check_ocr_noise(chunks, AuditConfig())
    assert result.status == "PASS"
    assert result.metrics["noisy_chunk_count"] == 0


def test_chunk_length_all_valid_passes():
    """Chunks within min/max bounds produce a PASS result."""
    chunks = [
        Chunk(text="A" * 50, source="a.pdf", page=1),
        Chunk(text="B" * 80, source="a.pdf", page=2),
    ]
    result = check_chunk_length(chunks, AuditConfig(min_chunk_chars=10, max_chunk_chars=100))
    assert result.status == "PASS"
    assert result.metrics["empty_chunk_count"] == 0
    assert result.metrics["short_chunk_count"] == 0
    assert result.metrics["long_chunk_count"] == 0

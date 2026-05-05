from __future__ import annotations

from collections import Counter, defaultdict
from itertools import islice

from docingestqa.config import AuditConfig
from docingestqa.models import CheckResult, Chunk, DocumentSpec, Issue
from docingestqa.text_utils import (
    bom_detected,
    char_entropy,
    control_char_count,
    ends_mid_sentence,
    has_repeated_char_run,
    is_navigation_fragment,
    jaccard,
    mojibake_count,
    normalize_text,
    null_byte_count,
    printable_noise_ratio,
    replacement_char_count,
    stable_hash,
    starts_mid_sentence,
    token_ngrams,
)


# ── v0.1 checks ──────────────────────────────────────────────────────────────

def check_input_summary(chunks: list[Chunk], manifest: list[DocumentSpec]) -> CheckResult:
    sources = {c.source for c in chunks if c.source}
    expected_sources = {d.source for d in manifest}
    status = "PASS" if chunks else "FAIL"
    summary = f"Loaded {len(chunks)} chunks across {len(sources)} observed sources."
    if manifest:
        summary += f" Manifest expects {len(expected_sources)} sources."
    return CheckResult(
        check="input_summary",
        status=status,
        summary=summary,
        metrics={
            "chunk_count": len(chunks),
            "observed_source_count": len(sources),
            "manifest_source_count": len(expected_sources),
        },
        recommendation="No chunks were loaded; verify the chunk export path." if not chunks else None,
    )


def check_metadata_completeness(chunks: list[Chunk], config: AuditConfig) -> CheckResult:
    missing_source = [c for c in chunks if not c.source]
    missing_page = [c for c in chunks if c.page is None]
    missing_any_ids = {c.display_id() for c in missing_source + missing_page}
    rate = len(missing_any_ids) / len(chunks) if chunks else 0.0

    issues: list[Issue] = []
    for c in missing_source[:50]:
        issues.append(Issue(check="metadata_completeness", severity="HIGH",
                            message="Chunk is missing source metadata.",
                            chunk_id=c.chunk_id, evidence={"text_preview": c.text[:120]}))
    for c in missing_page[:50]:
        issues.append(Issue(check="metadata_completeness", severity="MEDIUM",
                            message="Chunk is missing page metadata.",
                            source=c.source, chunk_id=c.chunk_id,
                            evidence={"text_preview": c.text[:120]}))

    if rate > config.fail_missing_metadata_rate:
        status = "FAIL"
    elif rate > config.warn_missing_metadata_rate:
        status = "WARN"
    else:
        status = "PASS"

    return CheckResult(
        check="metadata_completeness", status=status,
        summary=f"{len(missing_any_ids)} of {len(chunks)} chunks are missing source or page metadata.",
        issues=issues,
        metrics={"missing_source_count": len(missing_source),
                 "missing_page_count": len(missing_page),
                 "missing_any_metadata_rate": round(rate, 4)},
        recommendation="Populate source and page metadata before indexing; citations will be unreliable otherwise."
        if status != "PASS" else None,
    )


def check_document_coverage(chunks: list[Chunk], manifest: list[DocumentSpec]) -> CheckResult:
    if not manifest:
        return CheckResult(check="document_coverage", status="INSUFFICIENT_INPUT",
                           summary="No source manifest provided; cannot verify expected document coverage.",
                           metrics={"expected_document_count": 0},
                           recommendation="Provide source_manifest.json with expected source names and page counts.")

    observed = {c.source for c in chunks if c.source}
    expected = {d.source for d in manifest}
    missing = sorted(expected - observed)
    orphans = sorted(observed - expected)

    issues = [Issue(check="document_coverage", severity="HIGH",
                    message="Expected document has no chunks.", source=s) for s in missing]
    issues += [Issue(check="document_coverage", severity="MEDIUM",
                     message="Chunk source not in manifest.", source=s) for s in orphans]

    status = "FAIL" if missing else "WARN" if orphans else "PASS"
    return CheckResult(
        check="document_coverage", status=status,
        summary=f"{len(missing)} missing expected documents, {len(orphans)} orphan chunk sources.",
        issues=issues,
        metrics={"missing_documents": missing, "orphan_sources": orphans,
                 "expected_document_count": len(expected), "observed_source_count": len(observed)},
        recommendation="Re-run ingestion for missing documents or fix source naming mismatches."
        if status != "PASS" else None,
    )


def check_page_coverage(chunks: list[Chunk], manifest: list[DocumentSpec]) -> CheckResult:
    docs_with_pages = [d for d in manifest if d.pages]
    if not docs_with_pages:
        return CheckResult(check="page_coverage", status="INSUFFICIENT_INPUT",
                           summary="No expected page counts provided; cannot verify page coverage.",
                           metrics={"documents_with_page_counts": 0},
                           recommendation="Add pages to source_manifest.json for PDFs.")

    pages_by_source: dict[str, set[int]] = defaultdict(set)
    for c in chunks:
        if c.source and c.page is not None:
            pages_by_source[c.source].add(c.page)

    issues: list[Issue] = []
    missing_total = extra_total = 0
    for doc in docs_with_pages:
        expected = set(range(1, int(doc.pages) + 1))
        observed = pages_by_source.get(doc.source, set())
        missing = sorted(expected - observed)
        extra = sorted(p for p in observed if p > int(doc.pages))
        missing_total += len(missing)
        extra_total += len(extra)
        if missing:
            issues.append(Issue(check="page_coverage", severity="HIGH",
                                message="Document has pages missing from the chunk set.",
                                source=doc.source,
                                evidence={"missing_pages": missing[:100], "expected_pages": doc.pages}))
        if extra:
            issues.append(Issue(check="page_coverage", severity="MEDIUM",
                                message="Chunk page metadata exceeds expected page count.",
                                source=doc.source,
                                evidence={"extra_pages": extra[:100], "expected_pages": doc.pages}))

    status = "FAIL" if missing_total else "WARN" if extra_total else "PASS"
    return CheckResult(
        check="page_coverage", status=status,
        summary=f"{missing_total} missing pages and {extra_total} out-of-range pages detected.",
        issues=issues,
        metrics={"documents_checked": len(docs_with_pages),
                 "missing_page_total": missing_total, "extra_page_total": extra_total},
        recommendation="Inspect parser logs for missing pages before indexing." if status != "PASS" else None,
    )


def check_chunk_length(chunks: list[Chunk], config: AuditConfig) -> CheckResult:
    short = [c for c in chunks if 0 < len(c.text.strip()) < config.min_chunk_chars]
    long_ = [c for c in chunks if len(c.text.strip()) > config.max_chunk_chars]
    empty = [c for c in chunks if not c.text.strip()]
    empty_rate = len(empty) / len(chunks) if chunks else 0.0

    issues: list[Issue] = []
    for c in empty[:50]:
        issues.append(Issue(check="chunk_length", severity="HIGH", message="Empty chunk.",
                            source=c.source, page=c.page, chunk_id=c.chunk_id))
    for c in short[:50]:
        issues.append(Issue(check="chunk_length", severity="MEDIUM",
                            message="Very short chunk; may be header, footer, or extraction artifact.",
                            source=c.source, page=c.page, chunk_id=c.chunk_id,
                            evidence={"chars": len(c.text.strip()), "text_preview": c.text[:120]}))
    for c in long_[:50]:
        issues.append(Issue(check="chunk_length", severity="MEDIUM",
                            message="Very long chunk; retrieval may be noisy.",
                            source=c.source, page=c.page, chunk_id=c.chunk_id,
                            evidence={"chars": len(c.text.strip()), "text_preview": c.text[:120]}))

    if empty_rate > config.fail_empty_chunk_rate:
        status = "FAIL"
    elif empty or short or long_:
        status = "WARN"
    else:
        status = "PASS"

    lengths = [len(c.text.strip()) for c in chunks]
    return CheckResult(
        check="chunk_length", status=status,
        summary=f"{len(empty)} empty, {len(short)} short, {len(long_)} long chunks.",
        issues=issues,
        metrics={"min_chunk_chars": min(lengths) if lengths else None,
                 "max_chunk_chars": max(lengths) if lengths else None,
                 "avg_chunk_chars": round(sum(lengths) / len(lengths), 1) if lengths else None,
                 "empty_chunk_count": len(empty), "short_chunk_count": len(short),
                 "long_chunk_count": len(long_),
                 "configured_min": config.min_chunk_chars, "configured_max": config.max_chunk_chars},
        recommendation="Review chunking boundaries; empty/short chunks produce weak retrieval contexts."
        if status != "PASS" else None,
    )


def check_ocr_noise(chunks: list[Chunk], config: AuditConfig) -> CheckResult:
    issues: list[Issue] = []
    noisy = 0
    for c in chunks:
        text = c.text or ""
        noise_ratio = printable_noise_ratio(text)
        repl = replacement_char_count(text)
        repeated = has_repeated_char_run(text)
        if noise_ratio > config.noisy_text_ratio_threshold or repl >= config.replacement_char_threshold or repeated:
            noisy += 1
            issues.append(Issue(check="ocr_noise",
                                severity="HIGH" if repl >= config.replacement_char_threshold else "MEDIUM",
                                message="Potential OCR/extraction noise detected.",
                                source=c.source, page=c.page, chunk_id=c.chunk_id,
                                evidence={"noise_ratio": round(noise_ratio, 4), "replacement_chars": repl,
                                          "repeated_run": repeated,
                                          "char_entropy": round(char_entropy(text), 4),
                                          "text_preview": text[:120]}))

    rate = noisy / len(chunks) if chunks else 0.0
    if rate > config.fail_noisy_chunk_rate:
        status = "FAIL"
    elif rate > config.warn_noisy_chunk_rate or noisy:
        status = "WARN"
    else:
        status = "PASS"
    return CheckResult(
        check="ocr_noise", status=status,
        summary=f"{noisy} of {len(chunks)} chunks show possible OCR/extraction noise.",
        issues=issues[:100],
        metrics={"noisy_chunk_count": noisy, "noisy_chunk_rate": round(rate, 4)},
        recommendation="Inspect noisy pages and consider OCR cleanup or parser config changes."
        if status != "PASS" else None,
    )


def check_duplicates(chunks: list[Chunk], config: AuditConfig) -> CheckResult:
    exact_groups: dict[str, list[Chunk]] = defaultdict(list)
    for c in chunks:
        normalized = normalize_text(c.text)
        if normalized:
            exact_groups[stable_hash(normalized)].append(c)

    pairs: list[tuple[Chunk, Chunk, str, float]] = []
    for group in exact_groups.values():
        if len(group) > 1:
            for i in range(len(group) - 1):
                pairs.append((group[i], group[i + 1], "exact", 1.0))

    fingerprints = [(c, token_ngrams(c.text, config.ngram_size)) for c in chunks]
    for i, (left, lngs) in enumerate(fingerprints):
        if not lngs:
            continue
        for right, rngs in fingerprints[i + 1:]:
            if not rngs or stable_hash(left.text) == stable_hash(right.text):
                continue
            score = jaccard(lngs, rngs)
            if score >= config.near_duplicate_jaccard_threshold:
                pairs.append((left, right, "near", score))

    issues = [
        Issue(check="duplicate_chunks",
              severity="MEDIUM" if dt == "near" else "HIGH",
              message=f"{dt.title()} duplicate chunk pair.",
              source=l.source, page=l.page, chunk_id=l.chunk_id,
              evidence={"left_id": l.chunk_id, "right_id": r.chunk_id,
                        "right_source": r.source, "similarity": round(sc, 4)})
        for l, r, dt, sc in pairs[:config.max_duplicate_examples]
    ]

    n = len(pairs)
    status = "FAIL" if n >= config.fail_duplicate_pair_count else "WARN" if n >= config.warn_duplicate_pair_count else "PASS"
    return CheckResult(
        check="duplicate_chunks", status=status,
        summary=f"{n} exact/near-duplicate chunk pairs detected.",
        issues=issues,
        metrics={"duplicate_pair_count": n},
        recommendation="Deduplicate before indexing to avoid repeated retrieval evidence."
        if status != "PASS" else None,
    )


def check_source_distribution(chunks: list[Chunk]) -> CheckResult:
    counts = Counter(c.source or "(missing_source)" for c in chunks)
    if not counts:
        return CheckResult(check="source_distribution", status="FAIL",
                           summary="No chunks available.", metrics={},
                           recommendation="Verify chunk input path.")
    top_source, top_count = counts.most_common(1)[0]
    total = sum(counts.values())
    dominance = top_count / total if total else 0.0
    status = "WARN" if dominance > 0.80 and len(counts) > 1 else "PASS"
    issues = []
    if status == "WARN":
        issues.append(Issue(check="source_distribution", severity="MEDIUM",
                            message="One source dominates; ingestion may be imbalanced.",
                            source=top_source,
                            evidence={"chunk_count": top_count, "dominance_rate": round(dominance, 4)}))
    return CheckResult(
        check="source_distribution", status=status,
        summary=f"{len(counts)} sources; largest has {dominance:.1%} of chunks.",
        issues=issues,
        metrics={"chunks_by_source": dict(counts), "dominant_source": top_source,
                 "dominance_rate": round(dominance, 4)},
        recommendation="Check whether source imbalance is expected." if status != "PASS" else None,
    )


# ── v0.2 checks ──────────────────────────────────────────────────────────────

def check_chunk_overlap(chunks: list[Chunk], config: AuditConfig) -> CheckResult:
    """Detect consecutive chunks with high content overlap (sliding-window splitter artifacts).

    Sliding-window chunkers intentionally overlap adjacent chunks, but high overlap
    rates signal that the window step is too small, producing near-identical context
    pairs that waste embedding space and skew retrieval scores.
    """
    by_source: dict[str, list[Chunk]] = defaultdict(list)
    for c in chunks:
        key = c.source or "__no_source__"
        by_source[key].append(c)

    issues: list[Issue] = []
    warn_pairs = fail_pairs = 0

    for source, source_chunks in by_source.items():
        # sort by page then original order for consecutive comparison
        ordered = sorted(source_chunks, key=lambda c: (c.page or 0, source_chunks.index(c)))
        for i in range(len(ordered) - 1):
            left, right = ordered[i], ordered[i + 1]
            lng = token_ngrams(left.text, config.overlap_ngram_size)
            rng = token_ngrams(right.text, config.overlap_ngram_size)
            if not lng or not rng:
                continue
            score = jaccard(lng, rng)
            if score >= config.overlap_jaccard_fail_threshold:
                fail_pairs += 1
                issues.append(Issue(
                    check="chunk_overlap", severity="HIGH",
                    message=f"High content overlap between consecutive chunks ({score:.1%}).",
                    source=left.source, page=left.page, chunk_id=left.chunk_id,
                    evidence={"left_id": left.chunk_id, "right_id": right.chunk_id,
                              "overlap_score": round(score, 4),
                              "left_preview": left.text[:80], "right_preview": right.text[:80]}))
            elif score >= config.overlap_jaccard_warn_threshold:
                warn_pairs += 1
                issues.append(Issue(
                    check="chunk_overlap", severity="MEDIUM",
                    message=f"Moderate content overlap between consecutive chunks ({score:.1%}).",
                    source=left.source, page=left.page, chunk_id=left.chunk_id,
                    evidence={"left_id": left.chunk_id, "right_id": right.chunk_id,
                              "overlap_score": round(score, 4)}))

    total_flagged = fail_pairs + warn_pairs
    if fail_pairs >= config.fail_overlap_pair_count:
        status = "FAIL"
    elif total_flagged >= config.warn_overlap_pair_count:
        status = "WARN"
    else:
        status = "PASS"

    return CheckResult(
        check="chunk_overlap", status=status,
        summary=f"{fail_pairs} high-overlap and {warn_pairs} moderate-overlap consecutive chunk pairs.",
        issues=issues[:config.max_duplicate_examples],
        metrics={"high_overlap_pairs": fail_pairs, "moderate_overlap_pairs": warn_pairs,
                 "total_flagged_pairs": total_flagged,
                 "warn_threshold": config.overlap_jaccard_warn_threshold,
                 "fail_threshold": config.overlap_jaccard_fail_threshold},
        recommendation="Reduce window step size or deduplicate overlapping chunks before indexing."
        if status != "PASS" else None,
    )


def check_encoding_health(chunks: list[Chunk], config: AuditConfig) -> CheckResult:
    """Detect encoding corruption: null bytes, BOM markers, control characters, and mojibake.

    Mojibake (latin-1 decoded as UTF-8) is a common PDF pipeline failure that produces
    garbled text like 'Ã©' instead of 'é'. These chunks retrieve but generate wrong answers.
    """
    issues: list[Issue] = []
    null_chunks = bom_chunks = mojibake_chunks = 0

    for c in chunks:
        text = c.text or ""
        null_count = null_byte_count(text)
        has_bom = bom_detected(text)
        moji = mojibake_count(text)
        ctrl = control_char_count(text)

        flagged = False
        evidence: dict = {}

        if null_count >= config.null_byte_fail_threshold:
            null_chunks += 1
            flagged = True
            evidence["null_bytes"] = null_count

        if has_bom:
            bom_chunks += 1
            flagged = True
            evidence["bom"] = True

        if moji > 0:
            mojibake_chunks += 1
            flagged = True
            evidence["mojibake_sequences"] = moji
            evidence["text_preview"] = text[:120]

        if ctrl > 0:
            evidence["control_chars"] = ctrl
            flagged = True

        if flagged:
            severity = "HIGH" if null_count >= config.null_byte_fail_threshold else "MEDIUM"
            issues.append(Issue(
                check="encoding_health", severity=severity,
                message="Encoding corruption detected (null bytes, BOM, mojibake, or control chars).",
                source=c.source, page=c.page, chunk_id=c.chunk_id, evidence=evidence))

    total_flagged = len(issues)
    mojibake_rate = mojibake_chunks / len(chunks) if chunks else 0.0

    if null_chunks >= config.null_byte_fail_threshold or mojibake_rate >= config.mojibake_fail_rate:
        status = "FAIL"
    elif mojibake_rate >= config.mojibake_warn_rate or bom_chunks or total_flagged:
        status = "WARN"
    else:
        status = "PASS"

    return CheckResult(
        check="encoding_health", status=status,
        summary=f"{total_flagged} chunks have encoding issues ({null_chunks} null-byte, "
                f"{bom_chunks} BOM, {mojibake_chunks} mojibake).",
        issues=issues[:50],
        metrics={"null_byte_chunks": null_chunks, "bom_chunks": bom_chunks,
                 "mojibake_chunks": mojibake_chunks, "mojibake_rate": round(mojibake_rate, 4),
                 "total_flagged": total_flagged},
        recommendation="Re-run document parsing with explicit UTF-8 encoding. "
                       "Check for latin-1/windows-1252 source files."
        if status != "PASS" else None,
    )


def check_split_quality(chunks: list[Chunk], config: AuditConfig) -> CheckResult:
    """Detect poor chunk boundary decisions: mid-sentence splits and navigation fragments.

    Mid-sentence starts/ends indicate the splitter cut across sentence boundaries,
    producing chunks that lack context for both retrieval and answer generation.
    Navigation fragments (bare page numbers, TOC entries) carry no semantic content.
    """
    issues: list[Issue] = []
    mid_start = mid_end = nav_fragments = 0

    for c in chunks:
        text = c.text.strip()
        if not text:
            continue

        chunk_issues = []

        if starts_mid_sentence(text):
            mid_start += 1
            chunk_issues.append("starts mid-sentence")

        if ends_mid_sentence(text):
            mid_end += 1
            chunk_issues.append("ends mid-sentence")

        if is_navigation_fragment(text):
            nav_fragments += 1
            chunk_issues.append("navigation fragment")

        if chunk_issues:
            issues.append(Issue(
                check="split_quality",
                severity="MEDIUM",
                message=f"Poor split boundary: {', '.join(chunk_issues)}.",
                source=c.source, page=c.page, chunk_id=c.chunk_id,
                evidence={"flags": chunk_issues, "text_preview": text[:120]}))

    total_flagged = len(issues)
    bad_rate = total_flagged / len(chunks) if chunks else 0.0

    if bad_rate >= config.fail_bad_split_rate:
        status = "FAIL"
    elif bad_rate >= config.warn_bad_split_rate or total_flagged:
        status = "WARN"
    else:
        status = "PASS"

    return CheckResult(
        check="split_quality", status=status,
        summary=f"{total_flagged} chunks have poor split boundaries "
                f"({mid_start} mid-sentence starts, {mid_end} mid-sentence ends, "
                f"{nav_fragments} navigation fragments).",
        issues=issues[:50],
        metrics={"mid_sentence_starts": mid_start, "mid_sentence_ends": mid_end,
                 "navigation_fragments": nav_fragments, "total_flagged": total_flagged,
                 "bad_split_rate": round(bad_rate, 4)},
        recommendation="Tune splitter to respect sentence boundaries; remove navigation-only chunks."
        if status != "PASS" else None,
    )


ALL_CHECKS = [
    check_input_summary,
    check_metadata_completeness,
    check_document_coverage,
    check_page_coverage,
    check_chunk_length,
    check_ocr_noise,
    check_duplicates,
    check_source_distribution,
    check_chunk_overlap,
    check_encoding_health,
    check_split_quality,
]

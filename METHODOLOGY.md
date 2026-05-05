# DocIngestQA Methodology

DocIngestQA audits chunk outputs after parsing/chunking and before indexing. The design principle is simple: ingestion failures should be caught before the vector store receives bad chunks.

## Boundary

DocIngestQA operates on:

1. a chunk export (`jsonl`, `json`, or `csv`), and
2. an optional source manifest listing expected documents and page counts.

It does not parse original PDFs or generate embeddings in v0.1.0. This keeps the package dependency-light and makes it easy to plug into any ingestion pipeline.

## Status model

Each check returns one of:

- `PASS`: no issue detected under configured thresholds
- `WARN`: issue detected; review before indexing
- `FAIL`: serious issue detected; indexing should be blocked or manually approved
- `INSUFFICIENT_INPUT`: required input missing for the check

The overall report status is the worst status across checks using this priority:

`FAIL > WARN > INSUFFICIENT_INPUT > PASS`

## Checks

### Metadata completeness

Missing `source` or `page` metadata weakens citation quality. A chunk without a source cannot produce a trustworthy source citation. A chunk without page metadata can still be retrieved, but page-level attribution becomes unreliable.

### Document coverage

Compares observed chunk sources against the source manifest. It detects:

- expected source documents with no chunks
- orphan chunk sources not listed in the manifest

### Page coverage

For manifest entries with page counts, DocIngestQA expects at least one chunk per page. This is intentionally coarse: it does not prove that the page was fully captured, only that it is represented in the chunk set.

### Chunk length

Empty chunks are usually ingestion bugs. Very short chunks are often headers, footers, table fragments, or poor boundaries. Very long chunks can reduce retrieval focus.

### OCR noise

The v0 noise heuristic flags:

- Unicode replacement characters (`�`)
- high non-standard printable character ratio
- repeated-character runs such as `999999999`

These are heuristic review signals, not OCR quality scores.

### Duplicate chunks

DocIngestQA detects:

- exact duplicates with normalized SHA-1 hashes
- near duplicates with token n-gram Jaccard similarity

This catches repeated pages, copied boilerplate, and chunker loops. v0 does not use embeddings for semantic duplicate detection.

### Source distribution

A single source dominating the chunk set may be legitimate for uneven documents, but it can also reveal a bad extraction run where one document expanded into too many fragments.

### Chunk overlap (v0.2)

Sliding-window chunkers intentionally produce overlapping adjacent chunks. Moderate overlap is normal and expected. The `chunk_overlap` check flags cases where the overlap has become so large (Jaccard ≥ 0.40 on 4-grams between consecutive chunks from the same source) that the two chunks are nearly identical — indicating that the window step is too small relative to the window size. This wastes embedding budget and skews retrieval rankings by effectively duplicating the same context.

Chunks from different sources are never compared, as cross-source similarity is irrelevant to this artifact.

### Encoding health (v0.2)

Encoding corruption is a common silent failure in PDF ingestion pipelines. Three patterns are detected:

**Null bytes** (`\x00`): produced by binary artifacts or broken text extraction. A single null byte in a chunk is a FAIL — null bytes are almost never intentional in prose.

**BOM markers** (U+FEFF): indicate that a text file was decoded without stripping the byte-order mark, which can confuse downstream tokenizers.

**Mojibake**: garbled text produced when a UTF-8 document is decoded as latin-1 or windows-1252. The classic pattern is `Ã©` appearing in place of `é` (the UTF-8 bytes 0xC3 0xA9 reinterpreted as two latin-1 characters). DocIngestQA detects these using a regex that covers the most common mojibake patterns for 2-byte and 3-byte UTF-8 sequences. Mojibake chunks retrieve correctly but generate wrong answers.

### Split quality (v0.2)

Poor split boundaries reduce both retrieval precision and generation quality:

**Mid-sentence starts**: a chunk that begins with a lowercase word or conjunction (`and ...`, `but ...`) indicates the splitter cut mid-sentence. The chunk lacks the sentence subject and cannot stand alone.

**Mid-sentence ends**: a chunk that ends without terminal punctuation (period, question mark, exclamation mark, ellipsis) indicates a continuation that was truncated. The answer generation model may hallucinate the missing conclusion.

**Navigation fragments**: very short chunks (< 60 characters) that match patterns like bare integers, `Table of Contents`, `Index`, or `Page N of M` contain no semantic content and should be filtered before indexing.

## Why this is pre-indexing QA, not RAG evaluation

RAG evaluation asks: did retrieval and generation work for a query?

DocIngestQA asks: did the chunk corpus have obvious structural defects before retrieval was even possible?

Both layers are useful. They should not be conflated.

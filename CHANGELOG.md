# Changelog

## 0.2.0

- Added `check_chunk_overlap`: detects consecutive chunks from the same source with high token n-gram Jaccard similarity — flags sliding-window splitter artifacts
- Added `check_encoding_health`: detects null bytes, BOM markers, control characters, and mojibake patterns (Ã©, Â©, etc.) caused by UTF-8/latin-1 decoding mismatches
- Added `check_split_quality`: detects mid-sentence starts, mid-sentence ends, and navigation fragments (bare page numbers, TOC entries)
- Added CLI: `python -m docingestqa chunks.jsonl --manifest source_manifest.json --out outputs/`
- Added `[project.scripts]` entry point so `docingestqa` is available as a shell command after install
- Added `examples/generate_demo_data.py` for reproducible demo data generation
- Bumped `pyproject.toml` to `0.2.0`; development status raised from Alpha to Beta
- Fixed `datetime.UTC` import for Python 3.10 compatibility
- Fixed `_MOJIBAKE_RE` character class range for Python 3.10 regex engine

## 0.1.0

Initial local v0 release.

- Added `IngestionAuditor`
- Added JSONL/JSON/CSV chunk readers
- Added source manifest support
- Added metadata completeness check
- Added document coverage check
- Added page coverage check
- Added chunk length check
- Added OCR/extraction noise check
- Added exact and near duplicate chunk detection
- Added source distribution check
- Added JSON, Markdown, and HTML report outputs
- Added demo assets and end-to-end demo
- Added pytest suite and GitHub Actions CI

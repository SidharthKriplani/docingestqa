# Contributing

DocIngestQA is intentionally narrow: it audits generated chunks before indexing.

Good first contributions:

- More chunk input adapters
- Better OCR/noise heuristics
- More tests for malformed chunk exports
- CLI wrapper around `IngestionAuditor`
- Examples for common ingestion pipelines

Please avoid expanding v0 into a parser, retriever, vector database, chatbot, or answer evaluator. Those are adjacent systems, not this package's core boundary.

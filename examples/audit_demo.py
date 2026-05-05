from __future__ import annotations

from pathlib import Path

from docingestqa import AuditConfig, IngestionAuditor

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "examples" / "assets"
OUTPUTS = ROOT / "outputs"


def main() -> None:
    auditor = IngestionAuditor(
        chunks_path=ASSETS / "chunks.jsonl",
        documents_path=ASSETS / "source_manifest.json",
        config=AuditConfig(min_chunk_chars=80, max_chunk_chars=500),
    )
    report = auditor.run()
    OUTPUTS.mkdir(exist_ok=True)
    report.to_json(OUTPUTS / "ingestion_audit.json")
    report.to_markdown(OUTPUTS / "ingestion_audit.md")
    report.to_html(OUTPUTS / "ingestion_audit.html")

    summary = report.to_dict()["executive_summary"]
    print("DocIngestQA demo complete")
    print(f"Overall status: {summary['overall_status']}")
    print(f"Chunks audited: {summary['chunk_count']}")
    print(f"Check counts: {summary['check_counts']}")
    print(f"Outputs: {OUTPUTS}")


if __name__ == "__main__":
    main()

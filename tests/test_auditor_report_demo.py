from __future__ import annotations

from pathlib import Path

from docingestqa import IngestionAuditor

ROOT = Path(__file__).resolve().parents[1]


def test_auditor_runs_end_to_end_on_demo_assets():
    report = IngestionAuditor(
        chunks_path=ROOT / "examples" / "assets" / "chunks.jsonl",
        documents_path=ROOT / "examples" / "assets" / "source_manifest.json",
    ).run()
    payload = report.to_dict()
    assert payload["schema_version"] in ("0.1", "0.2")
    assert payload["executive_summary"]["chunk_count"] == 64
    assert payload["executive_summary"]["overall_status"] == "FAIL"
    assert "interpretation_note" in payload


def test_report_outputs_json_markdown_html(tmp_path):
    report = IngestionAuditor(
        chunks_path=ROOT / "examples" / "assets" / "chunks.jsonl",
        documents_path=ROOT / "examples" / "assets" / "source_manifest.json",
    ).run()
    json_out = report.to_json(tmp_path / "audit.json")
    md_out = report.to_markdown(tmp_path / "audit.md")
    html_out = report.to_html(tmp_path / "audit.html")
    assert "metadata_completeness" in json_out
    assert "# DocIngestQA Audit Report" in md_out
    assert "<html" in html_out
    assert (tmp_path / "audit.json").exists()
    assert (tmp_path / "audit.md").exists()
    assert (tmp_path / "audit.html").exists()


def test_warning_and_failed_check_helpers():
    report = IngestionAuditor(
        chunks_path=ROOT / "examples" / "assets" / "chunks.jsonl",
        documents_path=ROOT / "examples" / "assets" / "source_manifest.json",
    ).run()
    assert report.failed_checks()
    assert report.warning_checks()
    assert report.issue_table()

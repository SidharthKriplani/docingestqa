from __future__ import annotations

import json
from dataclasses import dataclass
import sys
from datetime import datetime, timezone

# datetime.UTC was added in Python 3.11; use timezone.utc for 3.10 compatibility
UTC = timezone.utc
from pathlib import Path
from typing import Any

from jinja2 import Template

from docingestqa._version import __version__
from docingestqa.models import CheckResult

MANDATORY_INTERPRETATION_NOTE = (
    "DocIngestQA reports deterministic ingestion quality signals for already-generated chunks. "
    "It does not parse documents, evaluate retrieval relevance, verify answer faithfulness, or prove that a RAG system is correct. "
    "Use these outputs as pre-indexing review signals before loading chunks into a vector database."
)

_STATUS_ORDER = {"FAIL": 0, "WARN": 1, "INSUFFICIENT_INPUT": 2, "PASS": 3}


@dataclass(frozen=True)
class IngestionAuditReport:
    """Structured audit report with JSON/Markdown/HTML renderers."""

    payload: dict[str, Any]

    @property
    def status(self) -> str:
        return self.payload["executive_summary"]["overall_status"]

    def to_dict(self) -> dict[str, Any]:
        return self.payload

    def to_json(self, path: str | Path | None = None, *, indent: int = 2) -> str:
        rendered = json.dumps(self.payload, indent=indent, ensure_ascii=False)
        if path:
            _write(path, rendered)
        return rendered

    def to_markdown(self, path: str | Path | None = None) -> str:
        rendered = _render_markdown(self.payload)
        if path:
            _write(path, rendered)
        return rendered

    def to_html(self, path: str | Path | None = None) -> str:
        rendered = _render_html(self.payload)
        if path:
            _write(path, rendered)
        return rendered

    def failed_checks(self) -> list[dict[str, Any]]:
        return [check for check in self.payload["checks"] if check["status"] == "FAIL"]

    def warning_checks(self) -> list[dict[str, Any]]:
        return [check for check in self.payload["checks"] if check["status"] == "WARN"]

    def issue_table(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for check in self.payload["checks"]:
            for issue in check["issues"]:
                rows.append({"check": check["check"], **issue})
        return rows


def build_payload(
    *,
    checks: list[CheckResult],
    chunk_count: int,
    manifest_count: int,
    chunks_path: str,
    documents_path: str | None,
) -> dict[str, Any]:
    check_dicts = [check.to_dict() for check in checks]
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "INSUFFICIENT_INPUT": 0}
    for check in check_dicts:
        counts[check["status"]] += 1

    overall_status = _overall_status(checks)
    top_risks = _top_risks(checks)
    return {
        "schema_version": "0.1",
        "metadata": {
            "package": "docingestqa",
            "version": __version__,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "chunks_path": chunks_path,
            "documents_path": documents_path,
        },
        "executive_summary": {
            "overall_status": overall_status,
            "chunk_count": chunk_count,
            "manifest_document_count": manifest_count,
            "check_counts": counts,
            "top_risks": top_risks,
        },
        "checks": check_dicts,
        "interpretation_note": MANDATORY_INTERPRETATION_NOTE,
    }


def _overall_status(checks: list[CheckResult]) -> str:
    if not checks:
        return "INSUFFICIENT_INPUT"
    return min((check.status for check in checks), key=lambda status: _STATUS_ORDER[status])


def _top_risks(checks: list[CheckResult]) -> list[str]:
    risks: list[str] = []
    for check in checks:
        if check.status in {"FAIL", "WARN"}:
            risks.append(f"{check.check}: {check.summary}")
    return risks[:5]


def _write(path: str | Path, content: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DocIngestQA Audit Report",
        "",
        f"**Overall status:** `{payload['executive_summary']['overall_status']}`",
        f"**Chunks audited:** {payload['executive_summary']['chunk_count']}",
        f"**Manifest documents:** {payload['executive_summary']['manifest_document_count']}",
        "",
        "## Check counts",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status, count in payload["executive_summary"]["check_counts"].items():
        lines.append(f"| {status} | {count} |")

    lines.extend(["", "## Top risks", ""])
    risks = payload["executive_summary"]["top_risks"]
    if risks:
        for risk in risks:
            lines.append(f"- {risk}")
    else:
        lines.append("No WARN/FAIL checks detected.")

    lines.extend(["", "## Checks", ""])
    for check in payload["checks"]:
        lines.extend(
            [
                f"### {check['check']} — `{check['status']}`",
                "",
                check["summary"],
                "",
            ]
        )
        if check.get("recommendation"):
            lines.extend([f"**Recommendation:** {check['recommendation']}", ""])
        if check.get("metrics"):
            lines.extend(["**Metrics:**", "", "```json"])
            lines.append(json.dumps(check["metrics"], indent=2, ensure_ascii=False))
            lines.extend(["```", ""])
        if check.get("issues"):
            lines.extend(["**Issues:**", "", "| Severity | Source | Page | Chunk | Message |", "|---|---|---:|---|---|"])
            for issue in check["issues"][:30]:
                lines.append(
                    f"| {issue['severity']} | {issue.get('source') or ''} | "
                    f"{issue.get('page') or ''} | {issue.get('chunk_id') or ''} | "
                    f"{issue['message']} |"
                )
            if len(check["issues"]) > 30:
                lines.append(f"\n_... {len(check['issues']) - 30} more issues omitted from Markdown preview._")
            lines.append("")
    lines.extend(["## Interpretation note", "", payload["interpretation_note"], ""])
    return "\n".join(lines)


def _render_html(payload: dict[str, Any]) -> str:
    template = Template(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>DocIngestQA Audit Report</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #172033; }
    .badge { display: inline-block; padding: 0.25rem 0.55rem; border-radius: 999px; background: #eef2ff; font-weight: 700; }
    .FAIL { background: #fee2e2; }
    .WARN { background: #fef3c7; }
    .PASS { background: #dcfce7; }
    .INSUFFICIENT_INPUT { background: #e5e7eb; }
    section { border-top: 1px solid #e5e7eb; padding-top: 1rem; margin-top: 1.5rem; }
    table { border-collapse: collapse; width: 100%; margin-top: 0.75rem; }
    th, td { border: 1px solid #e5e7eb; padding: 0.45rem; text-align: left; vertical-align: top; }
    th { background: #f8fafc; }
    pre { background: #0f172a; color: #e2e8f0; padding: 1rem; overflow-x: auto; border-radius: 8px; }
    .note { background: #f8fafc; padding: 1rem; border-left: 4px solid #64748b; }
  </style>
</head>
<body>
  <h1>DocIngestQA Audit Report</h1>
  <p><strong>Overall status:</strong> <span class="badge {{ payload.executive_summary.overall_status }}">{{ payload.executive_summary.overall_status }}</span></p>
  <p><strong>Chunks audited:</strong> {{ payload.executive_summary.chunk_count }} · <strong>Manifest documents:</strong> {{ payload.executive_summary.manifest_document_count }}</p>

  <h2>Top risks</h2>
  {% if payload.executive_summary.top_risks %}
    <ul>{% for risk in payload.executive_summary.top_risks %}<li>{{ risk }}</li>{% endfor %}</ul>
  {% else %}
    <p>No WARN/FAIL checks detected.</p>
  {% endif %}

  <h2>Checks</h2>
  {% for check in payload.checks %}
    <section>
      <h3>{{ check.check }} <span class="badge {{ check.status }}">{{ check.status }}</span></h3>
      <p>{{ check.summary }}</p>
      {% if check.recommendation %}<p><strong>Recommendation:</strong> {{ check.recommendation }}</p>{% endif %}
      {% if check.metrics %}<pre>{{ check.metrics | tojson(indent=2) }}</pre>{% endif %}
      {% if check.issues %}
        <table>
          <thead><tr><th>Severity</th><th>Source</th><th>Page</th><th>Chunk</th><th>Message</th></tr></thead>
          <tbody>
          {% for issue in check.issues[:50] %}
            <tr><td>{{ issue.severity }}</td><td>{{ issue.source or "" }}</td><td>{{ issue.page or "" }}</td><td>{{ issue.chunk_id or "" }}</td><td>{{ issue.message }}</td></tr>
          {% endfor %}
          </tbody>
        </table>
      {% endif %}
    </section>
  {% endfor %}
  <h2>Interpretation note</h2>
  <p class="note">{{ payload.interpretation_note }}</p>
</body>
</html>
"""
    )
    return template.render(payload=payload)

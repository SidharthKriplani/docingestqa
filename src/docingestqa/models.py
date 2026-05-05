from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Status = Literal["PASS", "WARN", "FAIL", "INSUFFICIENT_INPUT"]
Severity = Literal["LOW", "MEDIUM", "HIGH"]


@dataclass(frozen=True)
class DocumentSpec:
    """Expected source-document coverage.

    pages can be omitted for source types where page coverage is unknown.
    """

    source: str
    pages: int | None = None
    title: str | None = None


@dataclass(frozen=True)
class Chunk:
    """Normalized chunk representation used by all checks."""

    text: str
    source: str | None = None
    page: int | None = None
    chunk_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def display_id(self) -> str:
        if self.chunk_id:
            return self.chunk_id
        src = self.source or "unknown_source"
        page = self.page if self.page is not None else "unknown_page"
        return f"{src}::p{page}"


@dataclass(frozen=True)
class Issue:
    """A specific chunk/document-level issue found by a check."""

    check: str
    severity: Severity
    message: str
    source: str | None = None
    page: int | None = None
    chunk_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CheckResult:
    """One quality check result."""

    check: str
    status: Status
    summary: str
    issues: list[Issue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "status": self.status,
            "summary": self.summary,
            "metrics": self.metrics,
            "issues": [issue.to_dict() for issue in self.issues],
            "recommendation": self.recommendation,
        }

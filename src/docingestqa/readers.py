from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from docingestqa.exceptions import InvalidChunkInputError, InvalidManifestError
from docingestqa.models import Chunk, DocumentSpec


def read_manifest(path: str | Path | None) -> list[DocumentSpec]:
    """Read expected source-document manifest.

    Supported forms:
    - None: returns [] and coverage checks become INSUFFICIENT_INPUT where needed.
    - directory: if source_manifest.json exists, read it; otherwise infer text/md files as one-page docs.
    - JSON file with either {"documents": [...]} or [...].
    """
    if path is None:
        return []

    manifest_path = Path(path)
    if manifest_path.is_dir():
        candidate = manifest_path / "source_manifest.json"
        if candidate.exists():
            return read_manifest(candidate)
        return _infer_manifest_from_directory(manifest_path)

    if not manifest_path.exists():
        raise InvalidManifestError(f"Manifest path does not exist: {manifest_path}")

    if manifest_path.suffix.lower() != ".json":
        raise InvalidManifestError("Only JSON source manifests are supported in v0.1.0")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidManifestError(f"Malformed manifest JSON: {manifest_path}") from exc

    records = payload.get("documents", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise InvalidManifestError("Manifest must be a list or an object with a 'documents' list")

    specs: list[DocumentSpec] = []
    for idx, record in enumerate(records):
        if not isinstance(record, dict) or not record.get("source"):
            raise InvalidManifestError(f"Document record {idx} is missing required 'source'")
        pages = record.get("pages")
        if pages is not None:
            try:
                pages = int(pages)
            except (TypeError, ValueError) as exc:
                raise InvalidManifestError(f"Document {record['source']} has invalid pages value") from exc
            if pages < 1:
                raise InvalidManifestError(f"Document {record['source']} pages must be >= 1")
        specs.append(DocumentSpec(source=str(record["source"]), pages=pages, title=record.get("title")))
    return specs


def read_chunks(path: str | Path) -> list[Chunk]:
    """Read chunks from JSONL, JSON, or CSV.

    Required chunk text field: one of text, chunk_text, content.
    Metadata fields are preserved in Chunk.metadata.
    """
    chunk_path = Path(path)
    if not chunk_path.exists():
        raise InvalidChunkInputError(f"Chunk path does not exist: {chunk_path}")

    suffix = chunk_path.suffix.lower()
    if suffix == ".jsonl":
        records = _read_jsonl(chunk_path)
    elif suffix == ".json":
        records = _read_json(chunk_path)
    elif suffix == ".csv":
        records = _read_csv(chunk_path)
    else:
        raise InvalidChunkInputError("Supported chunk formats: .jsonl, .json, .csv")

    chunks: list[Chunk] = []
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            raise InvalidChunkInputError(f"Chunk record {idx} is not an object")
        text = _first_present(record, ["text", "chunk_text", "content"])
        if text is None:
            raise InvalidChunkInputError(f"Chunk record {idx} missing text/chunk_text/content field")
        source = _first_present(record, ["source", "document", "doc_id", "filename"])
        page = _parse_page(_first_present(record, ["page", "page_number", "page_num"]))
        chunk_id = _first_present(record, ["chunk_id", "id"])
        metadata = {key: value for key, value in record.items() if key not in {
            "text", "chunk_text", "content", "source", "document", "doc_id", "filename",
            "page", "page_number", "page_num", "chunk_id", "id",
        }}
        chunks.append(
            Chunk(
                text=str(text),
                source=str(source) if source not in (None, "") else None,
                page=page,
                chunk_id=str(chunk_id) if chunk_id not in (None, "") else f"chunk_{idx:04d}",
                metadata=metadata,
            )
        )
    return chunks


def _infer_manifest_from_directory(path: Path) -> list[DocumentSpec]:
    specs: list[DocumentSpec] = []
    for file_path in sorted(path.iterdir()):
        if file_path.name.startswith(".") or file_path.is_dir():
            continue
        if file_path.suffix.lower() in {".txt", ".md"}:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            pages = max(1, text.count("\f") + 1)
            specs.append(DocumentSpec(source=file_path.name, pages=pages, title=file_path.stem))
        elif file_path.suffix.lower() in {".pdf", ".docx", ".html"}:
            specs.append(DocumentSpec(source=file_path.name, pages=None, title=file_path.stem))
    return specs


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise InvalidChunkInputError(f"Malformed JSONL at line {line_no}: {path}") from exc
    return records


def _read_json(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidChunkInputError(f"Malformed chunk JSON: {path}") from exc
    records = payload.get("chunks", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise InvalidChunkInputError("Chunk JSON must be a list or an object with a 'chunks' list")
    return records


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _first_present(record: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _parse_page(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page >= 1 else None

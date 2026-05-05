from __future__ import annotations

import json

import pytest

from docingestqa.exceptions import InvalidChunkInputError, InvalidManifestError
from docingestqa.readers import read_chunks, read_manifest


def test_read_chunks_jsonl(tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_text(
        '{"chunk_id":"c1","source":"a.pdf","page":1,"text":"hello world"}\n',
        encoding="utf-8",
    )
    chunks = read_chunks(path)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "c1"
    assert chunks[0].source == "a.pdf"
    assert chunks[0].page == 1


def test_read_chunks_json_with_aliases(tmp_path):
    path = tmp_path / "chunks.json"
    path.write_text(
        json.dumps({"chunks": [{"id": "x", "filename": "doc.pdf", "page_number": "2", "content": "abc"}]}),
        encoding="utf-8",
    )
    chunks = read_chunks(path)
    assert chunks[0].chunk_id == "x"
    assert chunks[0].source == "doc.pdf"
    assert chunks[0].page == 2
    assert chunks[0].text == "abc"


def test_read_chunks_requires_text(tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_text('{"source":"a.pdf"}\n', encoding="utf-8")
    with pytest.raises(InvalidChunkInputError):
        read_chunks(path)


def test_read_manifest_json(tmp_path):
    path = tmp_path / "source_manifest.json"
    path.write_text('{"documents":[{"source":"a.pdf","pages":3}]}', encoding="utf-8")
    docs = read_manifest(path)
    assert len(docs) == 1
    assert docs[0].source == "a.pdf"
    assert docs[0].pages == 3


def test_manifest_rejects_invalid_pages(tmp_path):
    path = tmp_path / "source_manifest.json"
    path.write_text('{"documents":[{"source":"a.pdf","pages":0}]}', encoding="utf-8")
    with pytest.raises(InvalidManifestError):
        read_manifest(path)

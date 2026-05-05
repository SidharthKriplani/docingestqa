"""CLI: python -m docingestqa chunks.jsonl [--manifest manifest.json] [--out outputs/]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docingestqa.auditor import IngestionAuditor
from docingestqa._version import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="docingestqa",
        description="Pre-indexing QA auditor for RAG document ingestion chunks.",
    )
    parser.add_argument("chunks", help="Path to chunks file (.jsonl, .json, or .csv)")
    parser.add_argument("--manifest", "-m", default=None,
                        help="Path to source manifest JSON (optional but recommended)")
    parser.add_argument("--out", "-o", default="outputs",
                        help="Output directory for audit reports (default: outputs/)")
    parser.add_argument("--version", action="version", version=f"docingestqa {__version__}")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"docingestqa {__version__}")
    print(f"  chunks   : {args.chunks}")
    print(f"  manifest : {args.manifest or '(none)'}")
    print(f"  output   : {out}/")
    print()

    report = IngestionAuditor(
        chunks_path=args.chunks,
        documents_path=args.manifest,
    ).run()

    report.to_json(out / "ingestion_audit.json")
    report.to_markdown(out / "ingestion_audit.md")
    report.to_html(out / "ingestion_audit.html")

    summary = report.payload["executive_summary"]
    counts = summary["check_counts"]
    status = summary["overall_status"]

    print(f"Overall status : {status}")
    print(f"Chunks audited : {summary['chunk_count']}")
    print(f"Checks         : {counts['PASS']} PASS  {counts['WARN']} WARN  "
          f"{counts['FAIL']} FAIL  {counts['INSUFFICIENT_INPUT']} INSUFFICIENT_INPUT")
    print()
    if summary["top_risks"]:
        print("Top risks:")
        for risk in summary["top_risks"]:
            print(f"  - {risk}")
    print()
    print(f"Reports written to {out}/")

    sys.exit(1 if status == "FAIL" else 0)


if __name__ == "__main__":
    main()

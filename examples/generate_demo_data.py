"""
generate_demo_data.py
---------------------
Creates examples/assets/chunks.jsonl and examples/assets/source_manifest.json
with realistic, seeded defects for the docingestqa v0.2 demo.

Defects deliberately injected:
  - Missing pages (docs 2 and 5 have page gaps)
  - OCR noise (replacement chars, repeated junk)
  - Exact + near duplicates
  - High consecutive overlap (sliding-window artifact)
  - Encoding corruption: mojibake sequences
  - Mid-sentence splits (starts / ends abruptly)
  - Navigation fragments (bare page numbers, TOC entries)
  - Missing source metadata (a handful of orphan chunks)
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path


def cid() -> str:
    return str(uuid.uuid4())[:8]


ASSETS = Path(__file__).parent / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Source manifest: 10 documents, each with expected page count
# ---------------------------------------------------------------------------
MANIFEST = [
    {"source": "annual_report_2024.pdf", "pages": 12},
    {"source": "onboarding_guide.pdf", "pages": 8},
    {"source": "product_spec_v3.pdf", "pages": 6},
    {"source": "privacy_policy.pdf", "pages": 5},
    {"source": "research_paper.pdf", "pages": 10},
    {"source": "user_manual.pdf", "pages": 7},
    {"source": "compliance_checklist.pdf", "pages": 4},
    {"source": "technical_architecture.pdf", "pages": 9},
    {"source": "release_notes_v2.pdf", "pages": 3},
    {"source": "faq_document.pdf", "pages": 6},
]

# ---------------------------------------------------------------------------
# Helper: build a normal clean chunk
# ---------------------------------------------------------------------------
def chunk(text: str, source: str, page: int, chunk_id: str | None = None) -> dict:
    return {
        "chunk_id": chunk_id or cid(),
        "source": source,
        "page": page,
        "text": text,
    }


# ---------------------------------------------------------------------------
# Build chunk list
# ---------------------------------------------------------------------------
chunks: list[dict] = []

# ── annual_report_2024.pdf (12 pages, mostly clean) ──────────────────────
src = "annual_report_2024.pdf"
chunks += [
    chunk("The fiscal year 2024 saw record revenue growth of 34 percent across all business units. "
          "Management attributes this success to strong execution and favorable market conditions.", src, 1),
    chunk("Operating expenses increased by 12 percent year-over-year, primarily driven by headcount "
          "expansion in the engineering and sales divisions.", src, 2),
    chunk("Net income for the year reached $4.2 billion, compared to $3.1 billion in 2023. "
          "The board has approved a 15 percent increase in the annual dividend.", src, 3),
    chunk("Capital expenditures totaled $800 million, focused on data center infrastructure and "
          "cloud migration projects that are expected to reduce long-term operating costs.", src, 4),
    chunk("The company maintained strong liquidity with $6.5 billion in cash and short-term investments. "
          "Debt levels remained stable with a net-debt-to-EBITDA ratio of 1.2x.", src, 5),
    chunk("Forward-looking statements: management expects continued growth in the 18 to 22 percent "
          "range for fiscal 2025, contingent on macroeconomic stability.", src, 6),
    # pages 7–12 omitted intentionally → missing page coverage defect (minor)
    chunk("The audit committee reviewed all financial disclosures and found no material misstatements. "
          "External auditors PwC issued an unqualified opinion.", src, 12),
]

# ── onboarding_guide.pdf (8 pages; pages 4–5 missing) ────────────────────
src = "onboarding_guide.pdf"
chunks += [
    chunk("Welcome to the team. This guide covers your first 30 days at the company. "
          "Please read each section carefully before your first day.", src, 1),
    chunk("Your workstation will be provisioned by IT on your first morning. "
          "You will receive credentials for Slack, Jira, and the internal wiki by email.", src, 2),
    chunk("On day one you will complete mandatory compliance training modules. "
          "These typically take two to three hours and must be finished within your first week.", src, 3),
    # pages 4 and 5 deliberately skipped → missing page defect
    chunk("Performance review cycles occur twice per year, in June and December. "
          "Your manager will schedule a 30-minute kickoff meeting before each cycle.", src, 6),
    chunk("Benefits enrollment must be completed within 30 days of your start date. "
          "Contact HR at benefits@company.com for assistance.", src, 7),
    chunk("Congratulations on completing the onboarding guide. Reach out to your buddy "
          "or HR partner with any questions.", src, 8),
]

# ── product_spec_v3.pdf (6 pages, includes a duplicate + overlap pair) ────
src = "product_spec_v3.pdf"
dup_text = ("The authentication module uses OAuth 2.0 with PKCE for all public clients. "
            "Token expiry is set to 3600 seconds with a refresh window of 86400 seconds.")
chunks += [
    chunk("Product Specification v3 defines the functional and non-functional requirements "
          "for the platform release scheduled for Q2 2025.", src, 1),
    chunk(dup_text, src, 2),
    chunk(dup_text, src, 2, chunk_id="dup_exact_pair"),   # exact duplicate
    # consecutive high-overlap pair (sliding-window artifact)
    chunk("The rate limiter enforces a maximum of 1000 API calls per minute per client. "
          "Clients exceeding this limit receive a 429 Too Many Requests response with retry-after header.", src, 3),
    chunk("The rate limiter enforces a maximum of 1000 API calls per minute per client. "
          "Retry-after header indicates the number of seconds before the next request may be sent.", src, 3),
    chunk("Error responses follow RFC 7807 Problem Details format with machine-readable type URIs "
          "and human-readable detail strings.", src, 5),
    chunk("All endpoints are versioned under /api/v3/. Breaking changes require a major version bump "
          "and a minimum six-month deprecation window.", src, 6),
]

# ── privacy_policy.pdf (5 pages, clean) ───────────────────────────────────
src = "privacy_policy.pdf"
chunks += [
    chunk("This Privacy Policy describes how we collect, use, and share information about you "
          "when you use our services.", src, 1),
    chunk("We collect information you provide directly to us, such as when you create an account, "
          "make a purchase, or contact our support team.", src, 2),
    chunk("We may share your information with third-party service providers who perform services "
          "on our behalf, such as payment processing and data analytics.", src, 3),
    chunk("You have the right to access, correct, or delete your personal information at any time. "
          "Submit requests to privacy@company.com.", src, 4),
    chunk("We retain your data for as long as necessary to provide our services, "
          "or as required by law.", src, 5),
]

# ── research_paper.pdf (10 pages; page 7 missing; contains mojibake) ──────
src = "research_paper.pdf"
# Mojibake: latin-1 characters that appear when UTF-8 is decoded as latin-1 then re-encoded
# These are actual garbled string literals — no escape trickery needed here
MOJI_1 = "The proposed method achieves state-of-the-art results on the GLUE benchmark. " \
          "As shown in Table 2, our model outperforms the baseline by 3.4 percentage points " \
          "(Ã© = 0.92, p < 0.001)."
MOJI_2 = "Previous work by Vaswani et al. (âAttention Is All You Needâ) " \
          "introduced the transformer architecture that underpins modern LLM development."
chunks += [
    chunk("Abstract: We present a novel approach to document retrieval that leverages "
          "dense passage representations and cross-attention re-ranking.", src, 1),
    chunk("Section 1. Introduction. Information retrieval systems have evolved significantly "
          "with the advent of pre-trained language models.", src, 2),
    chunk("Section 2. Related Work. Dense retrieval methods such as DPR and ANCE have shown "
          "promising results on open-domain QA benchmarks.", src, 3),
    chunk("Section 3. Methodology. We fine-tune a dual-encoder model on MS MARCO using "
          "in-batch negatives with hard negative mining.", src, 4),
    chunk("Section 4. Experiments. All experiments were run on 8x A100 GPUs with a batch size "
          "of 256. Training converged after approximately 3 epochs.", src, 5),
    chunk(MOJI_1, src, 6),          # mojibake injection
    # page 7 deliberately skipped
    chunk(MOJI_2, src, 8),          # mojibake injection
    chunk("Section 6. Conclusion. We have presented a retrieval system that improves over "
          "prior work on both in-domain and out-of-domain benchmarks.", src, 9),
    chunk("References. [1] Karpukhin et al., 2020. [2] Xiong et al., 2021. [3] Vaswani et al., 2017.", src, 10),
]

# ── user_manual.pdf (7 pages, contains OCR noise + navigation fragments) ──
src = "user_manual.pdf"
chunks += [
    chunk("Chapter 1: Getting Started. Install the software using the provided installer package. "
          "Administrator privileges are required.", src, 1),
    chunk("Chapter 2: Configuration. Open Settings from the main menu and select the Preferences tab. "
          "Configure your profile and notification settings.", src, 2),
    # OCR noise chunk
    chunk("Chapt3r 3: Advanc3d F3atur3s. Th3 syst3m supp0rts b4tch pr0c3ssing " +
          "���" + " f0r l4rg3 d4ta s3ts.", src, 3),
    # navigation fragment
    chunk("4", src, 4),
    chunk("Chapter 5: Troubleshooting. If the application fails to start, check the log file "
          "at /var/log/app/app.log for error messages.", src, 5),
    chunk("Table of Contents", src, 6),   # navigation fragment
    chunk("Chapter 7: Appendix. Full list of keyboard shortcuts and configuration parameters "
          "is provided in this appendix.", src, 7),
]

# ── compliance_checklist.pdf (4 pages, contains mid-sentence splits) ──────
src = "compliance_checklist.pdf"
chunks += [
    chunk("All employees must complete annual compliance training by December 31st of each year. "
          "Managers are responsible for tracking completion in the HR system.", src, 1),
    # starts mid-sentence (lowercase start)
    chunk("and must be acknowledged before accessing any production systems. "
          "The acknowledgement is logged with a timestamp for audit purposes.", src, 2),
    # ends mid-sentence (no terminal punctuation)
    chunk("Data classification levels range from Public to Restricted. All files containing "
          "customer PII must be stored in the approved secure data", src, 3),
    chunk("Access reviews are conducted quarterly. Any accounts not used in 90 days are "
          "automatically suspended pending manager review.", src, 4),
]

# ── technical_architecture.pdf (9 pages, mostly clean, near-dup pair) ─────
src = "technical_architecture.pdf"
near_dup_a = ("The microservices architecture uses an event-driven pattern with Apache Kafka "
              "as the central message bus. Services publish domain events and subscribe to "
              "relevant topics for loose coupling.")
near_dup_b = ("The microservices architecture uses an event-driven approach with Apache Kafka "
              "as the primary message broker. Services publish domain events and subscribe to "
              "relevant topics to achieve loose coupling between components.")
chunks += [
    chunk("System Architecture Overview. The platform is built on a microservices architecture "
          "deployed on Kubernetes with 12 core services.", src, 1),
    chunk(near_dup_a, src, 2),
    chunk(near_dup_b, src, 3),   # near-duplicate of above
    chunk("The API gateway handles authentication, rate limiting, and request routing. "
          "It is implemented using Kong with custom plugins.", src, 4),
    chunk("Data storage uses PostgreSQL for transactional data, Redis for caching, "
          "and S3-compatible object storage for files and blobs.", src, 5),
    chunk("The observability stack includes Prometheus for metrics, Loki for logs, "
          "and Tempo for distributed traces, all visualized in Grafana.", src, 6),
    chunk("Deployments are managed via Helm charts stored in a separate GitOps repository. "
          "ArgoCD handles continuous delivery and drift detection.", src, 7),
    chunk("Disaster recovery objectives: RTO of 4 hours and RPO of 1 hour for all Tier 1 services. "
          "Cross-region failover is tested quarterly.", src, 8),
    chunk("Security controls include mTLS for service-to-service communication, secrets managed "
          "in HashiCorp Vault, and weekly automated vulnerability scans.", src, 9),
]

# ── release_notes_v2.pdf (3 pages, clean) ────────────────────────────────
src = "release_notes_v2.pdf"
chunks += [
    chunk("Release v2.0.0 — Major Changes. This release introduces the new async job processing "
          "engine, replacing the legacy synchronous queue.", src, 1),
    chunk("Bug fixes: resolved 14 open issues including the memory leak in the export service "
          "and the race condition in the session manager.", src, 2),
    chunk("Deprecations: the /api/v1/ endpoint family will be removed in v3.0. "
          "Migrate to /api/v2/ before upgrading.", src, 3),
]

# ── faq_document.pdf (6 pages, chunk with missing source metadata) ────────
src = "faq_document.pdf"
chunks += [
    chunk("Q: How do I reset my password? A: Click 'Forgot Password' on the login page. "
          "You will receive a reset link within 5 minutes.", src, 1),
    chunk("Q: Can I use the product on multiple devices? A: Yes, your subscription covers "
          "up to 5 simultaneous devices.", src, 2),
    chunk("Q: What payment methods are accepted? A: We accept Visa, Mastercard, PayPal, "
          "and bank transfers for enterprise accounts.", src, 3),
    chunk("Q: Is my data backed up? A: All data is backed up every 6 hours to geographically "
          "redundant storage.", src, 4),
    chunk("Q: How do I contact support? A: Reach us at support@company.com or via live chat "
          "between 9 AM and 6 PM UTC.", src, 5),
    # chunk with missing source metadata
    {
        "chunk_id": cid(),
        "source": None,
        "page": None,
        "text": "This chunk was exported without source metadata due to a pipeline misconfiguration.",
    },
]

# ── extra: repeated-run OCR noise chunk (no source) ──────────────────────
chunks.append({
    "chunk_id": cid(),
    "source": None,
    "page": None,
    "text": "Syst3m err0r: " + "x" * 15 + " check the log fil3 for details.",
})

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
chunks_path = ASSETS / "chunks.jsonl"
manifest_path = ASSETS / "source_manifest.json"

with open(chunks_path, "w", encoding="utf-8") as f:
    for c in chunks:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(MANIFEST, f, indent=2, ensure_ascii=False)

print(f"Wrote {len(chunks)} chunks to {chunks_path}")
print(f"Wrote {len(MANIFEST)} documents to {manifest_path}")

# quick sanity
sources = {c["source"] for c in chunks if c.get("source")}
print(f"Sources covered: {sorted(sources)}")

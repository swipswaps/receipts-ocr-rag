===============================================================================
DEV LOG RAG - FIND WORKING CODE AND FIX PATTERNS IN CHAT/TERMINAL LOGS
===============================================================================

This system is a developer-log RAG engine. It ingests chat transcripts,
terminal sessions, receipts, and other documents. It extracts code blocks,
error messages, commands, and success indicators, then searches for working
fixes and recurring failure patterns with full provenance.

It is designed to become the Knowledge and Evidence substrate for an
Agentic CRM, using the architecture principles from Comp AI (evidence over
self-reported confidence, durable tasks, sandboxing), MCP for tool
interoperability, and LiteLLM for model routing.

===============================================================================
HOW IT WORKS
===============================================================================

1. Upload logs (chat transcripts, terminal sessions, receipts, any .txt .log .json)
2. The system automatically extracts:
   - Code blocks (from markdown code fences or shell commands)
   - Error messages (Python tracebacks, shell errors, generic errors)
   - Commands (lines starting with $, #, > or common command names)
   - Success indicators (whether a command or code block worked)
   - Provenance metadata (timestamps, source hashes, file spans)
3. You can then:
   - Search for working code that fixed specific errors
   - Find commands that succeeded
   - See repeated errors and how they were solved
   - Browse common patterns across all logs
   - View the Evidence Graph (via the /rag/graph endpoint)

===============================================================================
QUICK START (DOCKER)
===============================================================================

Start the system:
cd /home/owner/Documents/your-repo/receipts-ocr-rag
docker compose up -d

Open the interface:
http://localhost:3000

Upload your logs using the drop zone or file picker.

Backend health check:
curl http://localhost:5001/

===============================================================================
WHAT THE STATS TELL YOU
===============================================================================

Entries - number of log files processed
Code Blocks - number of code snippets extracted
Errors - number of error messages detected
Success Rate - percentage of code blocks that appear to have worked

The Patterns tab shows:
- Repeated Errors - errors that appear many times, with solution status
- Common Commands - commands used frequently, with success indicators
- Working Code - code blocks that were successful
- Error to Solutions - specific errors paired with their fixes

===============================================================================
HOW TO INTERPRET THE RESULTS
===============================================================================

Each search result shows:
- Filename where the match was found
- A relevance score (higher is more relevant)
- Badges indicating if the entry contains code, errors, or success indicators
- The actual text content

Patterns show aggregation across all logs, so you can identify trends.

===============================================================================
THE EVIDENCE MODEL (NEXT PHASE)
===============================================================================

We are moving from simple metadata to a full provenance model:

  source -> observation -> evidence -> claim -> entity

Each extracted item has:
- A content hash (immutable, for reproducibility)
- A source span (character offsets, page numbers, or bounding boxes)
- A timestamp (observed_at, created_at, effective_from, effective_until)
- A verification state (PROPOSED, EXECUTED, VERIFIED, CORROBORATED, REJECTED)

The Evidence State Machine allows the system to distinguish:

  PROPOSED FIX
  EXECUTED FIX
  VERIFIED FIX
  FIX THAT APPEARED TO WORK

===============================================================================
TECHNICAL DETAILS
===============================================================================

Backend: Python FastAPI with sentence-transformers for semantic search
Frontend: Static HTML/CSS served by nginx (Vite build)
Storage: SQLite for metadata, in-memory vector store (migrating to PostgreSQL + pgvector)
Extraction: Regex patterns for code blocks, errors, commands, and success
Ports: Backend on 5001, Frontend on 3000
Docker: Full containerized build (docker-compose)

===============================================================================
FILE STRUCTURE
===============================================================================

receipts-ocr-rag/
├── backend/
│   └── app.py          Main application with extraction and search logic
├── frontend/
│   └── index.html      User interface (Vite build)
├── data/               SQLite database and uploaded data (persistent)
├── models/             Cached embedding models
├── Dockerfile          Container build definition
└── docker-compose.yml  Service orchestration

===============================================================================
COMMANDS
===============================================================================

Start the system:
docker compose up -d

Stop the system:
docker compose down

View logs:
docker compose logs -f

Check backend status:
curl http://localhost:5001/

Get patterns via API:
curl http://localhost:5001/rag/patterns

===============================================================================
FUTURE ARCHITECTURE (ROADMAP)
===============================================================================

The project is evolving into an Agentic Knowledge CRM:

   CRM Entities  +  Knowledge Graph  +  Evidence Ledger
                         |
                   Unified Retrieval
                         |
              Hybrid: FTS + Vector + Metadata
                         |
                       Reranker
                         |
                   Agent Orchestrator
                         |
                       MCP Tools
                         |
                   LiteLLM Gateway
                         |
        Cloud (OpenAI/Anthropic) vs Local (Ollama/vLLM)

Key principles:
- LLM is replaceable; the evidence model is not.
- Never trust "confidence" from a model; require deterministic evidence.
- Sandbox has no database credentials and deny-all egress.
- Model routing is policy-driven (task, data sensitivity, cost, latency).

===============================================================================
LIVE DEMO
===============================================================================

The system is deployed at:
https://swipswaps.github.io/receipts-ocr-rag

It connects to your local backend running on port 5001.
NOTE: The live GitHub Pages site only works locally (PNA bypass).
For public use, deploy the Docker backend to a cloud host.

===============================================================================
END OF README
===============================================================================

This document is maintained as plain ASCII text. Last updated: September 2, 2026.

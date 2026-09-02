===============================================================================
DEV LOG RAG - FIND WORKING CODE AND FIX PATTERNS IN CHAT/TERMINAL LOGS
===============================================================================

This system helps developers extract useful information from conversation
transcripts and terminal logs. It finds working code blocks, repeated errors,
commands that succeeded, and patterns that show how problems were fixed.

===============================================================================
HOW IT WORKS
===============================================================================

1. Upload logs (chat transcripts, terminal sessions, any .txt .log .json)

2. The system automatically extracts:
   - Code blocks (from markdown code fences or shell commands)
   - Error messages (Python tracebacks, shell errors, generic errors)
   - Commands (lines starting with $, #, > or common command names)
   - Success indicators (whether a command or code block worked)

3. You can then:
   - Search for working code that fixed specific errors
   - Find commands that succeeded
   - See repeated errors and how they were solved
   - Browse common patterns across all logs

===============================================================================
QUICK START
===============================================================================

Start the system:
cd /home/owner/Documents/a882dd73-3df0-4da3-9c2e-292bde88873a/repo/receipts-ocr-rag
docker compose up -d

Open the interface:
http://localhost:3000

Upload your logs using the drop zone or file picker.

===============================================================================
USEFUL SEARCHES
===============================================================================

Search for:
"working code that fixed error" - finds code blocks that appear after errors
"command that succeeded" - finds commands that exited cleanly
"failed and then succeeded" - finds fix patterns
"error repeated multiple times" - finds recurring problems
"code block with bash" - finds bash code specifically

===============================================================================
WHAT THE STATS TELL YOU
===============================================================================

Entries - number of log files processed
Code Blocks - number of code snippets extracted
Errors - number of error messages detected
Success Rate - percentage of code blocks that appear to have worked

The Patterns tab shows:
Repeated Errors - errors that appear many times, with solution status
Common Commands - commands used frequently, with success indicators
Working Code - code blocks that were successful
Error to Solutions - specific errors paired with their fixes

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
WHY THIS IS USEFUL FOR DEVELOPERS
===============================================================================

1. Stop re-learning the same lessons - find the fix you already discovered
2. Identify recurring problems that need better documentation or tooling
3. Share knowledge by pointing to code snippets that actually worked
4. Retrospectively understand what went wrong in a long debugging session
5. Extract working commands from messy terminal histories

===============================================================================
TECHNICAL DETAILS
===============================================================================

Backend: Python FastAPI with sentence-transformers for semantic search
Frontend: Static HTML/CSS served by nginx
Storage: SQLite for metadata, in-memory vector store for search
Extraction: Regex patterns for code blocks, errors, commands, and success
Ports: Backend on 5001, Frontend on 3000

===============================================================================
FILE STRUCTURE
===============================================================================

receipts-ocr-rag/
├── backend/
│   └── app.py          Main application with extraction and search logic
├── frontend/
│   └── index.html      User interface
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
EXAMPLE USE CASE
===============================================================================

You have a terminal history from a 4-hour debugging session. You remember
that you eventually fixed the problem with a specific command or code change,
but you don't remember exactly what it was.

Upload the log. Search for "worked" or "success" or "fixed". The system will
find the relevant sections and show you the exact code or command that worked.

Alternatively, look at the Patterns tab to see all commands sorted by frequency
and success rate. The command you used most often is likely the one that
eventually worked.

===============================================================================
LICENSE
===============================================================================

This project is provided as-is for internal use. Feel free to modify and
extend for your own needs.

===============================================================================
CONTACT
===============================================================================

For questions or improvements, refer to the chat logs that generated this
system. The entire development process is documented in the conversation
that led to this system.

===============================================================================
END OF README
===============================================================================

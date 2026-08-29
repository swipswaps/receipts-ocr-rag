=============================================================================
                    RECEIPTS OCR + RAG + AGENT
                    Complete Deployment Guide
=============================================================================

A unified document processing system combining OCR, Retrieval-Augmented
Generation (RAG), and Agentic workflows. Built with FastAPI, React/Vite,
OpenRAG, and DeepSeek Harness.

=============================================================================
QUICK START
=============================================================================

Clone the repository:
git clone https://github.com/swipswaps/receipts-ocr-rag.git
cd receipts-ocr-rag

Run the one-shot builder:
./build_repo.sh

=============================================================================
ARCHITECTURE
=============================================================================

GitHub Pages (Static Frontend)
React + Vite + Material UI
         |
         | http://localhost:5001
         v
FastAPI Backend (Docker) - Port 5001
+------------------+------------------+------------------+
|     OpenRAG      |      Agent       |     SQLite       |
|    (RAG/QA)      |    (Tasks)       |  (scans.db)      |
+------------------+------------------+------------------+

=============================================================================
FEATURES
=============================================================================

OCR Integration: PaddleOCR backend with column-first layout analysis
RAG Queries: Natural language search over processed documents
Agent Workflows: Task execution with database and web plugins
Persistent Storage: SQLite database for scans and action logs
Modern Frontend: React 18 + Vite + Material UI
Mobile Ready: Responsive design works on all devices
Backend Detection: Automatic online/offline status detection
Idempotent Deployment: Terraform + Ansible for reproducible infrastructure

=============================================================================
DEPLOYMENT OPTIONS
=============================================================================

Option                               URL                                     Backend
----------------------------------------------------------------------------------------
GitHub Pages + Local Docker          swipswaps.github.io/receipts-ocr-rag    Local Docker
Local Development                    http://localhost:5173                   Docker container
Docker Only                          http://localhost:5001                   Docker container

=============================================================================
PREREQUISITES
=============================================================================

Node.js 20+          https://nodejs.org
Docker Desktop       https://docker.com/get-started
GitHub CLI (gh)      https://cli.github.com
Python 3.12+         (for local backend development only)

Install GitHub CLI:
macOS:   brew install gh
Ubuntu:  sudo apt install gh
Fedora:  sudo dnf install gh
Windows: winget install --id GitHub.cli

Authenticate GitHub CLI:
gh auth login
Select: GitHub.com > HTTPS > Login with a web browser

=============================================================================
ONE-SHOT BUILDER SCRIPT
=============================================================================

The build_repo.sh script handles everything:
1. Clones the repository (if needed)
2. Builds the frontend
3. Deploys to gh-pages branch
4. Enables GitHub Pages
5. Validates the deployment

Run it:
./build_repo.sh

What the script does:

Step 1: Detects or clones the repository
Step 2: Installs npm dependencies
Step 3: Builds the React frontend
Step 4: Switches to gh-pages branch
Step 5: Copies built files to root
Step 6: Force-pushes to GitHub
Step 7: Enables GitHub Pages via API
Step 8: Validates HTTP 200 response

=============================================================================
MANUAL DEPLOYMENT
=============================================================================

If the script encounters issues, deploy manually:

Build the frontend:
cd frontend
npm install
npm run build
cd ..

Switch to gh-pages branch:
git checkout gh-pages

Clean the branch (keep only .git):
find . -maxdepth 1 ! -name '.git' ! -name '.' -exec rm -rf {} + 2>/dev/null || true

Copy built files to root:
cp -r frontend/dist/* .
touch .nojekyll

Commit and push:
git add -f .
git commit --no-verify -m "Deploy to GitHub Pages"
git push -f origin gh-pages

Enable Pages (if not already enabled):
gh api -X POST "/repos/swipswaps/receipts-ocr-rag/pages" -f source=gh-pages

Wait 2-3 minutes for deployment:
curl -I https://swipswaps.github.io/receipts-ocr-rag

=============================================================================
API ENDPOINTS
=============================================================================

Endpoint                 Method  Description
----------------------------------------------------------------------------------------
/health                  GET     Health check (RAG/Agent status)
/rag/query               POST    Natural language query
/agent/execute           POST    Execute agent task
/scans                   GET     List all scans
/scans/{id}              GET     Get scan details
/rag/stream              POST    Streaming RAG results

Example API calls:

Health check:
curl http://localhost:5001/health

RAG query:
curl -X POST http://localhost:5001/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What documents are available?", "top_k": 5}'

Agent execution:
curl -X POST http://localhost:5001/agent/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "summarize", "params": {"text": "Sample text"}}'

=============================================================================
TROUBLESHOOTING
=============================================================================

GitHub Pages Returns 404

Problem: https://swipswaps.github.io/receipts-ocr-rag returns 404.

Solutions:
1. Wait 2-3 minutes - GitHub Pages takes time to build
2. Check Pages settings:
   Visit https://github.com/swipswaps/receipts-ocr-rag/settings/pages
   Verify source is gh-pages branch, / folder
3. Force re-deploy:
   git checkout gh-pages
   git commit --allow-empty -m "Trigger rebuild"
   git push origin gh-pages

Terminal Closes After Running Script

Problem: The script closes your terminal window.

Solution: Source the script instead of executing it:
source build_repo.sh
or
. build_repo.sh

gh CLI Not Authenticated

Problem: gh auth status fails.

Solution:
gh auth login
Follow the prompts to authenticate

Frontend Build Fails

Problem: npm run build fails.

Solutions:
1. Clear node_modules and reinstall:
   rm -rf node_modules package-lock.json
   npm install
2. Check Node.js version: node -v (should be 20+)
3. Check for TypeScript errors: npx tsc --noEmit

Docker Backend Not Available

Problem: Backend status shows "offline".

Solutions:
1. Start Docker: docker compose up -d
2. Check container status: docker compose ps
3. View logs: docker compose logs backend
4. Verify port 5001 is free: sudo lsof -i :5001

Port Already in Use

Problem: "Address already in use" error.

Solution:
Find and kill the process:
sudo lsof -i :5001
sudo kill -9 [PID]

Or use a different port:
export BACKEND_PORT=5002
docker compose up -d

Git Push Fails

Problem: git push origin gh-pages fails.

Solutions:
1. Check authentication: gh auth status
2. Force push: git push -f origin gh-pages
3. Check repository permissions

=============================================================================
USAGE GUIDE
=============================================================================

Access the Application

1. Start the backend:
   docker compose up -d

2. Open the frontend:
   GitHub Pages: https://swipswaps.github.io/receipts-ocr-rag
   Local: http://localhost:5173

3. The frontend auto-detects backend status (Online/Offline)

Using RAG Queries

1. Enter a question in the "RAG Query" field
2. Click "Search"
3. Results appear below showing relevant documents

Using the Agent

1. Enter a task (e.g., "summarize", "categorize")
2. Click "Execute"
3. Results appear showing the agent's output

Viewing Scans

1. Click on any scan in the list
2. Details appear showing OCR text and structured data

=============================================================================
FILE STRUCTURE
=============================================================================

receipts-ocr-rag/
├── backend/
│   ├── app.py              FastAPI application
│   ├── Dockerfile          Backend container
│   └── requirements.txt    Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.tsx         Main React component
│   │   └── main.tsx        Entry point
│   ├── package.json        npm dependencies
│   └── vite.config.ts      Vite configuration
├── infra/
│   └── main.tf             Terraform configuration
├── ansible/
│   └── playbook.yml        Ansible playbook
├── docker-compose.yml      Docker orchestration
├── build_repo.sh           One-shot builder script
└── .gitignore              Git ignore rules

=============================================================================
DOCKER COMMANDS
=============================================================================

Start the stack:
docker compose up -d

Stop the stack:
docker compose down

View logs:
docker compose logs backend
docker compose logs frontend

Rebuild images:
docker compose build

Access backend shell:
docker compose exec backend bash

=============================================================================
LICENSE
=============================================================================

MIT License

=============================================================================
CONTRIBUTING
=============================================================================

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run pre-commit hooks: pre-commit run --all-files
5. Submit a pull request

=============================================================================
SUPPORT
=============================================================================

GitHub Issues: https://github.com/swipswaps/receipts-ocr-rag/issues
Documentation: https://swipswaps.github.io/receipts-ocr-rag

=============================================================================
ACKNOWLEDGMENTS
=============================================================================

OpenRAG: https://github.com/langflow-ai/openrag
DeepSeek Harness: https://github.com/deepseek-ai/deepseek-harness
FastAPI: https://fastapi.tiangolo.com
Vite: https://vitejs.dev
React: https://react.dev
Material UI: https://mui.com
Terraform: https://terraform.io
Ansible: https://ansible.com

=============================================================================
END OF README
=============================================================================

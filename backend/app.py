import os
import json
import re
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import sqlite3
from collections import defaultdict, Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dev Log RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "/app/data"
MODEL_DIR = "/app/models"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "dev.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)

# Create tables with AUTOINCREMENT for id
conn.execute("""
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        content TEXT,
        entry_type TEXT,
        timestamp TEXT
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS code_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER,
        language TEXT,
        code TEXT,
        worked INTEGER DEFAULT 0,
        FOREIGN KEY(entry_id) REFERENCES entries(id)
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        error_text TEXT,
        error_type TEXT,
        count INTEGER DEFAULT 1,
        first_seen TEXT,
        last_seen TEXT,
        solved INTEGER DEFAULT 0,
        solution TEXT
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command TEXT,
        exit_code INTEGER,
        worked INTEGER DEFAULT 0,
        count INTEGER DEFAULT 1,
        last_used TEXT
    )
""")
conn.commit()

MODEL_NAME = "all-MiniLM-L6-v2"
logger.info(f"Loading model: {MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME, cache_folder=MODEL_DIR)

documents = []  # Vector store

# --- Models ---
class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 10
    threshold: Optional[float] = 0.15
    search_type: Optional[str] = "all"

class PatternRequest(BaseModel):
    pattern_type: str
    limit: Optional[int] = 20

# --- Helpers ---
def get_embedding(text: str) -> np.ndarray:
    if not text or len(text.strip()) == 0:
        return np.zeros(384)
    return model.encode(text, normalize_embeddings=True)

def extract_code_blocks(text: str) -> List[Dict]:
    blocks = []
    pattern = r'```(\w+)\n(.*?)```'
    for match in re.finditer(pattern, text, re.DOTALL):
        blocks.append({
            "language": match.group(1),
            "code": match.group(2).strip()
        })
    cmd_pattern = r'^(?:\$|#|>)\s*(.+)$'
    for line in text.split('\n'):
        m = re.match(cmd_pattern, line.strip())
        if m:
            blocks.append({
                "language": "bash",
                "code": m.group(1).strip()
            })
    return blocks

def extract_errors(text: str) -> List[Dict]:
    errors = []
    error_patterns = [
        (r'(error|Error|ERROR):\s*(.+?)(?:\n|$)', 'generic'),
        (r'(Traceback|Exception|SyntaxError|NameError|TypeError|KeyError|ValueError|ImportError|ModuleNotFoundError).*?(?:\n|$)', 'python'),
        (r'(command not found|permission denied|no such file|cannot find|failed to|unable to)', 'shell'),
    ]
    for pattern, etype in error_patterns:
        for match in re.finditer(pattern, text, re.DOTALL | re.MULTILINE):
            errors.append({
                "text": match.group(0).strip(),
                "type": etype
            })
    return errors

def extract_commands(text: str) -> List[str]:
    commands = []
    patterns = [
        r'(?:^|\n)(?:>|\$|#)\s*([a-zA-Z0-9_\-\./]+[^\n]*)',
        r'(?:^|\n)(?:sudo|npm|docker|git|python|pip|curl|wget|cat|grep|awk|sed|find|ls|cd|chmod|chown)\s+[^\n]+',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            cmd = match.group(0).strip()
            if len(cmd) > 3:
                commands.append(cmd)
    return commands

def detect_success(text: str) -> bool:
    success_patterns = [
        r'(success|successfully|completed|done|finished|✅|✓|ok|OK)',
        r'exited with code 0',
        r'(installed|built|deployed|connected|started|running)',
    ]
    failure_patterns = [
        r'(failed|error|exception|traceback|fatal|cancelled|aborted|❌|✗)',
        r'exited with code [1-9]',
    ]
    has_success = any(re.search(p, text, re.I) for p in success_patterns)
    has_failure = any(re.search(p, text, re.I) for p in failure_patterns)
    return has_success and not has_failure

# --- API Endpoints ---
@app.get("/")
async def root():
    return {"status": "online", "service": "Dev Log RAG", "documents": len(documents)}

@app.post("/scan")
async def scan_log(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename
    text = content.decode('utf-8', errors='ignore')

    timestamp = datetime.now().isoformat()

    # Extract features
    code_blocks = extract_code_blocks(text)
    errors = extract_errors(text)
    commands = extract_commands(text)
    success = detect_success(text)

    # Insert entry (AUTOINCREMENT handles id)
    cursor = conn.execute(
        "INSERT INTO entries (filename, content, entry_type, timestamp) VALUES (?, ?, ?, ?)",
        (filename, text, "log", timestamp)
    )
    entry_id = cursor.lastrowid

    # Store code blocks
    for block in code_blocks:
        conn.execute(
            "INSERT INTO code_blocks (entry_id, language, code, worked) VALUES (?, ?, ?, ?)",
            (entry_id, block["language"], block["code"], 1 if success else 0)
        )

    # Store errors
    for error in errors:
        conn.execute(
            "INSERT INTO errors (error_text, error_type, first_seen, last_seen) VALUES (?, ?, ?, ?)",
            (error["text"], error["type"], timestamp, timestamp)
        )

    # Store commands
    for cmd in commands:
        conn.execute(
            "INSERT INTO commands (command, last_used) VALUES (?, ?)",
            (cmd, timestamp)
        )

    conn.commit()

    # Store in vector index
    chunks = [text[i:i+500] for i in range(0, len(text), 300)]
    for chunk in chunks:
        if len(chunk.strip()) > 20:
            embedding = get_embedding(chunk)
            documents.append({
                "id": entry_id,
                "filename": filename,
                "text": chunk,
                "embedding": embedding,
                "metadata": {
                    "has_code": len(code_blocks) > 0,
                    "has_errors": len(errors) > 0,
                    "success": success,
                    "commands": len(commands)
                }
            })

    return {
        "id": entry_id,
        "filename": filename,
        "status": "success",
        "chunks": len(chunks),
        "code_blocks": len(code_blocks),
        "errors": len(errors),
        "commands": len(commands),
        "has_success": success
    }

@app.post("/rag/query")
async def rag_query(request: QueryRequest):
    if not documents:
        return {"results": [], "total": 0}

    query_embedding = get_embedding(request.query)
    results = []
    for doc in documents:
        if np.any(doc["embedding"]):
            score = cosine_similarity([query_embedding], [doc["embedding"]])[0][0]
            if score > request.threshold:
                results.append({
                    "id": doc["id"],
                    "filename": doc["filename"],
                    "text": doc["text"],
                    "score": float(score),
                    "metadata": doc.get("metadata", {})
                })
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:request.top_k], "total": len(results)}

@app.get("/rag/patterns")
async def get_patterns(pattern_type: str = "all", limit: int = 20):
    patterns = {}

    errors = conn.execute(
        "SELECT error_type, error_text, count, solved FROM errors ORDER BY count DESC LIMIT ?",
        (limit,)
    ).fetchall()
    patterns["top_errors"] = [
        {"type": e[0], "text": e[1][:200], "count": e[2], "solved": bool(e[3])}
        for e in errors
    ]

    commands = conn.execute(
        "SELECT command, count, worked FROM commands ORDER BY count DESC LIMIT ?",
        (limit,)
    ).fetchall()
    patterns["top_commands"] = [
        {"command": c[0][:100], "count": c[1], "worked": bool(c[2])}
        for c in commands
    ]

    code = conn.execute(
        "SELECT language, code FROM code_blocks WHERE worked = 1 ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    patterns["working_code"] = [
        {"language": c[0], "code": c[1][:500]}
        for c in code
    ]

    error_solutions = []
    for err in conn.execute("SELECT error_text, error_type FROM errors LIMIT 20").fetchall():
        solution = conn.execute(
            "SELECT e.content FROM entries e JOIN code_blocks c ON c.entry_id = e.id WHERE e.content LIKE ? AND c.worked = 1 LIMIT 1",
            ('%' + err[0][:50] + '%',)
        ).fetchone()
        if solution:
            error_solutions.append({
                "error": err[0][:200],
                "solution": solution[0][:500]
            })
    patterns["error_solutions"] = error_solutions[:10]

    return patterns

@app.get("/rag/stats")
async def get_stats():
    total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    code_count = conn.execute("SELECT COUNT(*) FROM code_blocks").fetchone()[0]
    error_count = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
    cmd_count = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    success_count = conn.execute("SELECT COUNT(*) FROM code_blocks WHERE worked = 1").fetchone()[0]

    return {
        "total_entries": total,
        "code_blocks": code_count,
        "errors": error_count,
        "commands": cmd_count,
        "working_code": success_count,
        "success_rate": round(success_count / code_count * 100, 1) if code_count > 0 else 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)

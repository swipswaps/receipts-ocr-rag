import os, json, re, logging
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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DATA_DIR = "/app/data"; MODEL_DIR = "/app/models"
os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(MODEL_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "dev.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)

# Create tables
conn.execute("""CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, content TEXT, entry_type TEXT, timestamp TEXT)""")
conn.execute("""CREATE TABLE IF NOT EXISTS code_blocks (id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id INTEGER, language TEXT, code TEXT, worked INTEGER DEFAULT 0, FOREIGN KEY(entry_id) REFERENCES entries(id))""")
conn.execute("""CREATE TABLE IF NOT EXISTS errors (id INTEGER PRIMARY KEY AUTOINCREMENT, error_text TEXT, error_type TEXT, count INTEGER DEFAULT 1, first_seen TEXT, last_seen TEXT, solved INTEGER DEFAULT 0, solution TEXT)""")
conn.execute("""CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY AUTOINCREMENT, command TEXT, exit_code INTEGER, worked INTEGER DEFAULT 0, count INTEGER DEFAULT 1, last_used TEXT)""")
conn.commit()

MODEL_NAME = "all-MiniLM-L6-v2"
model = SentenceTransformer(MODEL_NAME, cache_folder=MODEL_DIR)

# Global vector store
documents = []

# Helper functions
def get_embedding(text: str) -> np.ndarray:
    if not text or len(text.strip()) == 0: return np.zeros(384)
    return model.encode(text, normalize_embeddings=True)

def extract_code_blocks(text: str) -> List[Dict]:
    blocks = []
    for match in re.finditer(r'```(\w+)\n(.*?)```', text, re.DOTALL):
        blocks.append({"language": match.group(1), "code": match.group(2).strip()})
    for line in text.split('\n'):
        m = re.match(r'^(?:\$|#|>)\s*(.+)$', line.strip())
        if m: blocks.append({"language": "bash", "code": m.group(1).strip()})
    return blocks

def extract_errors(text: str) -> List[Dict]:
    errors = []
    patterns = [
        (r'(error|Error|ERROR):\s*(.+?)(?:\n|$)', 'generic'),
        (r'(Traceback|Exception|SyntaxError|NameError|TypeError|KeyError|ValueError|ImportError|ModuleNotFoundError).*?(?:\n|$)', 'python'),
        (r'(command not found|permission denied|no such file|cannot find|failed to|unable to)', 'shell'),
    ]
    for pattern, etype in patterns:
        for match in re.finditer(pattern, text, re.DOTALL | re.MULTILINE):
            errors.append({"text": match.group(0).strip(), "type": etype})
    return errors

# Load existing DB entries into vector store on startup
def load_existing_entries():
    global documents
    documents = []  # Reset
    rows = conn.execute("SELECT id, filename, content FROM entries").fetchall()
    for entry_id, filename, text in rows:
        chunks = [text[i:i+500] for i in range(0, len(text), 300)]
        for chunk in chunks:
            if len(chunk.strip()) > 20:
                documents.append({
                    "id": entry_id,
                    "filename": filename,
                    "text": chunk,
                    "embedding": get_embedding(chunk),
                    "metadata": {
                        "has_code": len(extract_code_blocks(chunk)) > 0,
                        "has_errors": len(extract_errors(chunk)) > 0,
                        "success": "success" in text.lower(),
                        "commands": len(extract_code_blocks(chunk))
                    }
                })
    logger.info(f"Loaded {len(documents)} chunks from DB into vector store.")

# Call the loader right after the model is ready
load_existing_entries()

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 10
    threshold: Optional[float] = 0.15
    search_type: Optional[str] = "all"

@app.get("/")
async def root():
    return {"status": "online", "service": "Dev Log RAG", "documents": len(documents)}

@app.post("/scan")
async def scan_log(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename
    text = content.decode('utf-8', errors='ignore')
    timestamp = datetime.now().isoformat()
    cursor = conn.execute("INSERT INTO entries (filename, content, entry_type, timestamp) VALUES (?, ?, ?, ?)", (filename, text, "log", timestamp))
    entry_id = cursor.lastrowid
    conn.commit()

    code_blocks = extract_code_blocks(text)
    errors = extract_errors(text)
    for block in code_blocks:
        conn.execute("INSERT INTO code_blocks (entry_id, language, code, worked) VALUES (?, ?, ?, ?)", (entry_id, block["language"], block["code"], 1 if "success" in text.lower() else 0))
    for error in errors:
        conn.execute("INSERT INTO errors (error_text, error_type, first_seen, last_seen) VALUES (?, ?, ?, ?)", (error["text"], error["type"], timestamp, timestamp))
    conn.commit()

    chunks = [text[i:i+500] for i in range(0, len(text), 300)]
    for chunk in chunks:
        if len(chunk.strip()) > 20:
            documents.append({
                "id": entry_id, "filename": filename, "text": chunk,
                "embedding": get_embedding(chunk),
                "metadata": {"has_code": len(code_blocks) > 0, "has_errors": len(errors) > 0, "success": "success" in text.lower(), "commands": len(code_blocks)}
            })
    return {"status": "success", "id": entry_id, "filename": filename}

@app.post("/rag/query")
async def rag_query(request: QueryRequest):
    """Returns structured insights, not raw text dumps."""
    if not documents:
        return {"results": [], "total": 0}

    query_embedding = get_embedding(request.query)
    results = []
    for doc in documents:
        if np.any(doc["embedding"]):
            score = cosine_similarity([query_embedding], [doc["embedding"]])[0][0]
            if score > request.threshold:
                # Extract the *specific* code or error from the text block
                code_blocks = extract_code_blocks(doc["text"])
                errors = extract_errors(doc["text"])
                
                # Format the result as a clean object
                formatted_result = {
                    "id": doc["id"],
                    "filename": doc["filename"],
                    "score": float(score),
                    "type": "solution" if code_blocks else ("error" if errors else "context"),
                    "worked": 1 if "success" in doc["text"].lower() else 0,
                    "content": code_blocks[0]["code"] if code_blocks else (errors[0]["text"] if errors else doc["text"][:300]),
                    "language": code_blocks[0]["language"] if code_blocks else None,
                    "metadata": doc.get("metadata", {})
                }
                results.append(formatted_result)
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:request.top_k], "total": len(results)}

@app.get("/rag/patterns")
async def get_patterns(pattern_type: str = "all", limit: int = 20):
    patterns = {}
    errors = conn.execute("SELECT error_type, error_text, count, solved FROM errors ORDER BY count DESC LIMIT ?", (limit,)).fetchall()
    patterns["top_errors"] = [{"type": e[0], "text": e[1][:200], "count": e[2], "solved": bool(e[3])} for e in errors]
    commands = conn.execute("SELECT command, count, worked FROM commands ORDER BY count DESC LIMIT ?", (limit,)).fetchall()
    patterns["top_commands"] = [{"command": c[0][:100], "count": c[1], "worked": bool(c[2])} for c in commands]
    code = conn.execute("SELECT language, code FROM code_blocks WHERE worked = 1 ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    patterns["working_code"] = [{"language": c[0], "code": c[1][:500]} for c in code]
    error_solutions = []
    for err in conn.execute("SELECT error_text, error_type FROM errors LIMIT 20").fetchall():
        err_embedding = get_embedding(err[0])
        best_score = 0; best_code = None
        for cb in conn.execute("SELECT code, worked FROM code_blocks").fetchall():
            if not cb[1]: continue
            cb_embedding = get_embedding(cb[0][:500])
            score = cosine_similarity([err_embedding], [cb_embedding])[0][0]
            if score > best_score: best_score = score; best_code = cb[0]
        if best_code and best_score > 0.5:
            error_solutions.append({"error": err[0][:200], "solution": best_code[:500], "score": round(float(best_score), 3)})
    patterns["error_solutions"] = error_solutions[:10]
    return patterns

@app.get("/rag/graph")
async def get_graph_data(limit: int = 50):
    nodes = []; edges = []
    for e in conn.execute("SELECT id, error_text, count FROM errors ORDER BY count DESC LIMIT ?", (limit,)).fetchall():
        nodes.append({"id": f"err_{e[0]}", "type": "error", "label": e[1][:50], "size": e[2]})
        edges.append({"source": "root", "target": f"err_{e[0]}"})
    for c in conn.execute("SELECT id, command, count FROM commands ORDER BY count DESC LIMIT ?", (limit,)).fetchall():
        nodes.append({"id": f"cmd_{c[0]}", "type": "command", "label": c[1][:50], "size": c[2]})
        edges.append({"source": "root", "target": f"cmd_{c[0]}"})
    for f in conn.execute("SELECT DISTINCT filename FROM entries LIMIT 10").fetchall():
        nodes.append({"id": f, "type": "file", "label": f, "size": 10})
    return {"nodes": nodes, "edges": edges}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)

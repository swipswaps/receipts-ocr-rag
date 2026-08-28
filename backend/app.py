import os
import json
import sqlite3
import datetime
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from datetime import timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/app/data/scans.db")
MODEL_PATH = os.environ.get("OPENRAG_MODEL_PATH", "/app/models")
PLUGINS = os.environ.get("DEEPSEEK_HARNESS_PLUGINS", "database,web").split(",")

class RAGQuery(BaseModel):
    query: str = Field(..., description="Natural language query")
    top_k: int = Field(5, description="Number of results to return")

class RAGResponse(BaseModel):
    results: List[Dict[str, Any]]

class AgentTask(BaseModel):
    task: str = Field(..., description="Task to execute")
    params: Dict[str, Any] = Field(default_factory=dict)

class AgentResponse(BaseModel):
    result: Dict[str, Any]

class HealthResponse(BaseModel):
    status: str
    rag_engine: str
    agent_engine: str
    scan_count: int
    timestamp: str

class ScanSummary(BaseModel):
    id: int
    filename: str
    timestamp: str

class ScanDetail(BaseModel):
    id: int
    filename: str
    text: str
    structured: Dict[str, Any]
    timestamp: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing backend components...")
    init_db()
    app.state.rag = None
    app.state.harness = None

    try:
        from openrag import OpenRAG
        app.state.rag = OpenRAG(
            model_path=MODEL_PATH,
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            db_path=DB_PATH
        )
        logger.info("OpenRAG initialized")
    except ImportError as e:
        logger.warning("OpenRAG import failed: %s", e)

    try:
        from deepseek_harness import DeepSeekHarness
        app.state.harness = DeepSeekHarness(
            plugins=PLUGINS,
            memory_path="/app/data/memory.db"
        )
        logger.info("DeepSeek Harness initialized with plugins: %s", PLUGINS)
    except ImportError as e:
        logger.warning("DeepSeek Harness import failed: %s", e)

    yield
    logger.info("Shutting down...")

app = FastAPI(
    title="Receipts OCR + RAG + Agent API",
    description="Unified backend for retrieval-augmented generation and agentic workflows",
    version="0.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            text TEXT,
            structured JSON,
            embedding BLOB,
            timestamp TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            params JSON,
            result TEXT,
            timestamp TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS embeddings_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            embedding BLOB,
            metadata JSON,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", DB_PATH)

def get_scan_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM scans")
    count = cur.fetchone()[0]
    conn.close()
    return count

@app.get("/health", response_model=HealthResponse)
async def health():
    return {
        "status": "ok",
        "rag_engine": "OpenRAG" if app.state.rag is not None else "disabled",
        "agent_engine": "DeepSeek Harness" if app.state.harness is not None else "disabled",
        "scan_count": get_scan_count(),
        "timestamp": datetime.datetime.now(timezone.utc).isoformat()
    }

@app.post("/rag/query", response_model=RAGResponse)
async def rag_query(request: RAGQuery):
    if app.state.rag is None:
        raise HTTPException(status_code=503, detail="OpenRAG not available")
    try:
        results = app.state.rag.search(request.query, top_k=request.top_k)
        return {"results": results}
    except Exception as e:
        logger.error("RAG query failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/execute", response_model=AgentResponse)
async def agent_execute(request: AgentTask):
    if app.state.harness is None:
        raise HTTPException(status_code=503, detail="DeepSeek Harness not available")
    try:
        result = app.state.harness.run(task=request.task, params=request.params)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO actions (action, params, result, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            request.task,
            json.dumps(request.params),
            json.dumps(result),
            datetime.datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()
        return {"result": result}
    except Exception as e:
        logger.error("Agent execution failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scans", response_model=List[ScanSummary])
async def get_scans(limit: int = 50, offset: int = 0):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, filename, timestamp FROM scans
        ORDER BY timestamp DESC LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "filename": r[1], "timestamp": r[2]} for r in rows]

@app.get("/scans/{scan_id}", response_model=ScanDetail)
async def get_scan(scan_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, filename, text, structured, timestamp FROM scans WHERE id=?", (scan_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {
        "id": row[0],
        "filename": row[1],
        "text": row[2],
        "structured": json.loads(row[3]),
        "timestamp": row[4]
    }

@app.post("/rag/stream")
async def rag_stream(request: RAGQuery):
    if app.state.rag is None:
        raise HTTPException(status_code=503, detail="OpenRAG not available")
    async def generate():
        yield f"data: {json.dumps({'status': 'starting', 'query': request.query})}\n\n"
        try:
            results = app.state.rag.search(request.query, top_k=request.top_k)
            for i, result in enumerate(results):
                yield f"data: {json.dumps({'index': i, 'result': result})}\n\n"
            yield f"data: {json.dumps({'status': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")


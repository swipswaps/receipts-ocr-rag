import os
import json
import re
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import aiofiles
import sqlite3
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Receipts OCR + RAG + Agent")

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

# SQLite for metadata + chat history
DB_PATH = os.path.join(DATA_DIR, "rag.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY,
        filename TEXT,
        text TEXT,
        vendor TEXT,
        date TEXT,
        amount REAL,
        category TEXT,
        created_at TEXT
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        query TEXT,
        response TEXT,
        timestamp TEXT
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS image_references (
        id INTEGER PRIMARY KEY,
        filename TEXT,
        doc_id INTEGER,
        image_path TEXT,
        uploaded_at TEXT
    )
""")
conn.commit()

MODEL_NAME = "all-MiniLM-L6-v2"
logger.info(f"Loading model: {MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME, cache_folder=MODEL_DIR)

documents = []  # In-memory vector store

# --- Models ---
class RAGQuery(BaseModel):
    query: str
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.2
    session_id: Optional[str] = None
    filter_vendor: Optional[str] = None
    filter_date_from: Optional[str] = None
    filter_date_to: Optional[str] = None
    filter_category: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    session_id: str
    top_k: Optional[int] = 5

# --- Helper functions ---
def get_embedding(text: str) -> np.ndarray:
    if not text or len(text.strip()) == 0:
        return np.zeros(model.get_sentence_embedding_dimension())
    return model.encode(text, normalize_embeddings=True)

def extract_metadata(text: str) -> Dict[str, Any]:
    """Extract vendor, date, amount, category from text."""
    metadata = {"vendor": None, "date": None, "amount": None, "category": None}
    # Vendor detection (common patterns)
    vendor_patterns = [
        r'(?i)(?:from|at|vendor|store|merchant):\s*([A-Za-z0-9\s&,.]+)',
        r'(?i)([A-Za-z0-9\s&,.]+)(?:\s+receipt|\s+invoice)',
    ]
    for pattern in vendor_patterns:
        m = re.search(pattern, text[:500])
        if m:
            metadata["vendor"] = m.group(1).strip()
            break
    # Date extraction
    date_patterns = [
        r'(\d{4}[-/]\d{2}[-/]\d{2})',
        r'(\d{2}[-/]\d{2}[-/]\d{4})',
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})',
    ]
    for pattern in date_patterns:
        m = re.search(pattern, text[:1000])
        if m:
            metadata["date"] = m.group(1)
            break
    # Amount extraction
    amount_patterns = [
        r'(?:total|sum|amount|grand total)[:\s]*\$?(\d+\.\d{2})',
        r'(\d+\.\d{2})\s*(?:USD|EUR|GBP|total)',
    ]
    for pattern in amount_patterns:
        m = re.search(pattern, text[:1000])
        if m:
            metadata["amount"] = float(m.group(1))
            break
    return metadata

def detect_query_intent(query: str) -> Dict[str, Any]:
    """Detect if query is aggregation, filter, or semantic."""
    intent = {"type": "semantic", "filters": {}, "aggregation": None}
    
    # Aggregation keywords
    agg_keywords = ["sum", "total", "average", "avg", "count", "how many", "how much", "breakdown"]
    for kw in agg_keywords:
        if kw in query.lower():
            intent["type"] = "aggregation"
            if "sum" in query.lower() or "total" in query.lower():
                intent["aggregation"] = "sum"
            elif "average" in query.lower() or "avg" in query.lower():
                intent["aggregation"] = "avg"
            elif "count" in query.lower():
                intent["aggregation"] = "count"
            break
    
    # Date filters
    date_patterns = [
        (r'(?:last|past)\s+(\d+)\s+(day|week|month|year)', 'period'),
        (r'(?:in|during)\s+(\d{4})', 'year'),
        (r'(\d{4}[-/]\d{2}[-/]\d{2})\s+to\s+(\d{4}[-/]\d{2}[-/]\d{2})', 'range'),
    ]
    for pattern, typ in date_patterns:
        m = re.search(pattern, query.lower())
        if m:
            if typ == 'period':
                num = int(m.group(1))
                unit = m.group(2)
                intent["filters"]["period"] = {"num": num, "unit": unit}
            elif typ == 'year':
                intent["filters"]["year"] = m.group(1)
            elif typ == 'range':
                intent["filters"]["date_from"] = m.group(1)
                intent["filters"]["date_to"] = m.group(2)
            break
    
    # Vendor filters
    vendor_match = re.search(r'(?:from|at|vendor|merchant)[:\s]+([A-Za-z0-9\s]+)', query, re.I)
    if vendor_match:
        intent["filters"]["vendor"] = vendor_match.group(1).strip()
    
    # Category filters
    categories = ["food", "transport", "groceries", "utility", "shopping", "dining"]
    for cat in categories:
        if cat in query.lower():
            intent["filters"]["category"] = cat
            break
    
    return intent

# --- API Endpoints ---

@app.get("/")
async def root():
    return {"status": "online", "service": "Receipts OCR + RAG + Agent", "documents": len(documents)}

@app.post("/scan")
async def scan_document(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename
    
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "text" in data:
            text = data["text"]
        else:
            text = str(data)
    except:
        text = content.decode('utf-8', errors='ignore')
    
    metadata = extract_metadata(text)
    doc_id = len(documents) + 1
    timestamp = datetime.now().isoformat()
    
    # Store in SQLite for metadata
    conn.execute(
        "INSERT INTO documents (id, filename, text, vendor, date, amount, category, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (doc_id, filename, text, metadata.get("vendor"), metadata.get("date"), metadata.get("amount"), metadata.get("category"), timestamp)
    )
    conn.commit()
    
    # Store in vector index
    chunks = [text[i:i+500] for i in range(0, len(text), 300)]
    for i, chunk in enumerate(chunks):
        if chunk and len(chunk.strip()) > 10:
            embedding = get_embedding(chunk)
            documents.append({
                "id": doc_id,
                "filename": filename,
                "text": chunk,
                "embedding": embedding,
                "metadata": {"chunk": i, "total_chunks": len(chunks), **metadata}
            })
    
    logger.info(f"Processed {filename}: {len(chunks)} chunks")
    return {
        "id": doc_id,
        "filename": filename,
        "status": "success",
        "chunks": len(chunks),
        "metadata": metadata,
        "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
        "created_at": timestamp
    }

@app.post("/rag/chat")
async def chat_query(request: ChatRequest):
    """Chat with conversation history."""
    # Get previous chat history
    history = conn.execute(
        "SELECT query, response FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT 5",
        (request.session_id,)
    ).fetchall()
    
    # Build context from history
    context = ""
    for q, r in reversed(history):
        context += f"Q: {q}\nA: {r}\n"
    
    # Run RAG with context
    intent = detect_query_intent(request.message)
    results = await rag_query_internal(request.message, request.top_k, 0.2, request.session_id)
    
    # Store in history
    conn.execute(
        "INSERT INTO chat_history (session_id, query, response, timestamp) VALUES (?, ?, ?, ?)",
        (request.session_id, request.message, json.dumps(results[:3]), datetime.now().isoformat())
    )
    conn.commit()
    
    return {
        "response": results,
        "context": context,
        "session_id": request.session_id,
        "intent": intent
    }

async def rag_query_internal(query: str, top_k: int = 5, threshold: float = 0.2, session_id: str = None):
    if not documents:
        return []
    
    intent = detect_query_intent(query)
    
    # Aggregation path
    if intent["type"] == "aggregation":
        cursor = conn.cursor()
        if intent["aggregation"] == "sum":
            cursor.execute("SELECT SUM(amount) FROM documents WHERE amount IS NOT NULL")
            result = cursor.fetchone()
            return [{"type": "aggregation", "value": result[0] if result and result[0] else 0, "unit": "dollars"}]
        elif intent["aggregation"] == "count":
            cursor.execute("SELECT COUNT(*) FROM documents")
            result = cursor.fetchone()
            return [{"type": "aggregation", "value": result[0] if result else 0, "unit": "documents"}]
        elif intent["aggregation"] == "avg":
            cursor.execute("SELECT AVG(amount) FROM documents WHERE amount IS NOT NULL")
            result = cursor.fetchone()
            return [{"type": "aggregation", "value": result[0] if result and result[0] else 0, "unit": "dollars"}]
    
    # Filtered query
    filters = intent["filters"]
    cursor = conn.cursor()
    sql = "SELECT id, filename, text, vendor, date, amount, category FROM documents"
    conditions = []
    if filters.get("vendor"):
        conditions.append(f"vendor LIKE '%{filters['vendor']}%'")
    if filters.get("category"):
        conditions.append(f"category = '{filters['category']}'")
    if filters.get("date_from"):
        conditions.append(f"date >= '{filters['date_from']}'")
    if filters.get("date_to"):
        conditions.append(f"date <= '{filters['date_to']}'")
    if filters.get("year"):
        conditions.append(f"date LIKE '{filters['year']}%'")
    if filters.get("period"):
        days = filters["period"]["num"] * {"day": 1, "week": 7, "month": 30, "year": 365}.get(filters["period"]["unit"], 1)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conditions.append(f"created_at >= '{cutoff}'")
    
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
        cursor.execute(sql)
        filtered_docs = cursor.fetchall()
        if filtered_docs:
            return [{"type": "filtered", "documents": filtered_docs[:top_k]}]
    
    # Semantic search (default)
    query_embedding = get_embedding(query)
    results = []
    for doc in documents:
        if np.any(doc["embedding"]):
            score = cosine_similarity([query_embedding], [doc["embedding"]])[0][0]
            if score > threshold:
                results.append({
                    "id": doc["id"],
                    "filename": doc["filename"],
                    "text": doc["text"],
                    "score": float(score),
                    "metadata": doc.get("metadata", {})
                })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

@app.post("/rag/query")
async def rag_query(request: RAGQuery):
    results = await rag_query_internal(request.query, request.top_k, request.threshold, request.session_id)
    return {
        "results": results,
        "query": request.query,
        "total": len(results),
        "session_id": request.session_id
    }

@app.get("/rag/scans")
async def list_scans():
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, vendor, date, amount, category, created_at FROM documents")
    rows = cursor.fetchall()
    return [{"id": r[0], "filename": r[1], "vendor": r[2], "date": r[3], "amount": r[4], "category": r[5], "created_at": r[6]} for r in rows]

@app.get("/rag/stats")
async def get_stats():
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT vendor) FROM documents WHERE vendor IS NOT NULL")
    vendors = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(amount) FROM documents WHERE amount IS NOT NULL")
    total_spend = cursor.fetchone()[0] or 0
    cursor.execute("SELECT category, COUNT(*) FROM documents GROUP BY category")
    categories = {r[0]: r[1] for r in cursor.fetchall()}
    return {
        "total_documents": total,
        "total_vendors": vendors,
        "total_spend": total_spend,
        "categories": categories
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)

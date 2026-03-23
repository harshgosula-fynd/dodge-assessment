"""FastAPI application entry point."""

import sys
from pathlib import Path

# Ensure backend directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import graph, lineage, status, chat

app = FastAPI(
    title="O2C Context Graph",
    description="SAP Order-to-Cash context graph with LLM-powered query interface",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph.router)
app.include_router(lineage.router)
app.include_router(status.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    """Health check."""
    return {"status": "ok"}

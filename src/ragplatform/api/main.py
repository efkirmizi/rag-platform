"""Retrieval Service API (Faz 0).

Faz 1 notları:
- user_id gövdeden değil OIDC token'ından gelecek (Platform API katmanı).
- Bu servis LLM çağrısı YAPMAZ; generation LiteLLM gateway arkasındadır.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from ragplatform.acl.access import AccessResolver
from ragplatform.acl.fga import FgaClient
from ragplatform.config import get_settings
from ragplatform.db import create_pool
from ragplatform.embeddings import create_embeddings
from ragplatform.retrieval.rerank import create_reranker
from ragplatform.retrieval.service import RetrievalService


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    user_id: str = Field(min_length=1, max_length=200)
    top_k: int = Field(default=8, ge=1, le=50)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    pool = await create_pool(settings.database_url)
    fga = FgaClient.from_settings(settings)
    embedder = create_embeddings(settings)
    app.state.service = RetrievalService(
        pool=pool,
        embedder=embedder,
        resolver=AccessResolver(fga, ttl_seconds=settings.acl_cache_ttl_seconds),
        reranker=create_reranker(settings),
    )
    yield
    await fga.close()
    await embedder.close()
    await pool.close()


app = FastAPI(title="RAG Platform — Retrieval Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.post("/v1/retrieve")
async def retrieve(req: RetrieveRequest) -> dict:
    return await app.state.service.retrieve(req.user_id, req.query, req.top_k)

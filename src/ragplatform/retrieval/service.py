import asyncio
import time

import asyncpg

from ragplatform.acl.access import AccessResolver
from ragplatform.embeddings.base import EmbeddingProvider
from ragplatform.retrieval.hybrid import hybrid_search
from ragplatform.retrieval.rerank import Reranker


class RetrievalService:
    def __init__(
        self,
        pool: asyncpg.Pool,
        embedder: EmbeddingProvider,
        resolver: AccessResolver,
        reranker: Reranker,
        candidate_k: int = 50,
        fused_k: int = 24,
    ):
        self._pool = pool
        self._embedder = embedder
        self._resolver = resolver
        self._reranker = reranker
        self._candidate_k = candidate_k
        self._fused_k = fused_k

    async def retrieve(self, user_id: str, query: str, top_k: int = 8) -> dict:
        t0 = time.perf_counter()

        allowed_spaces, allowed_restricted = await asyncio.gather(
            self._resolver.allowed_spaces(user_id),
            self._resolver.allowed_restricted_pages(user_id),
        )

        results: list[dict] = []
        if allowed_spaces:
            [query_embedding] = await self._embedder.embed_query([query])
            rows = await hybrid_search(
                self._pool,
                query_embedding,
                query,
                allowed_spaces,
                allowed_restricted,
                candidate_k=self._candidate_k,
                fused_k=max(self._fused_k, top_k),
            )
            rows = await self._reranker.rerank(query, rows, top_k)
            results = [self._shape(r) for r in rows]

        return {
            "query": query,
            "user_id": user_id,
            "took_ms": round((time.perf_counter() - t0) * 1000, 1),
            "allowed_spaces": allowed_spaces,
            "results": results,
        }

    @staticmethod
    def _shape(row: dict) -> dict:
        return {
            "content": row["content"],
            "score": float(row["rrf_score"]),
            "citation": {
                "title": row["title"],
                "heading_path": row["heading_path"],
                "space_key": row["space_key"],
                "page_key": row["page_key"],
                "url": row["url"],
                "updated_at": row["updated_at"].isoformat(),
            },
            "debug": {
                "vec_rank": row["vec_rank"],
                "fts_rank": row["fts_rank"],
                "is_restricted": row["is_restricted"],
                "rerank_score": row.get("rerank_score"),  # noop'ta None
            },
        }

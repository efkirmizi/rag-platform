from abc import ABC, abstractmethod


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, results: list[dict], top_k: int) -> list[dict]: ...


class NoopReranker(Reranker):
    """Faz 0: RRF sırasını korur. Faz 1'de bge-reranker-v2-m3 servisi bağlanacak
    (cross-encoder; top-50 aday → top-8). Arayüz o geçiş için sabit tutuldu."""

    async def rerank(self, query: str, results: list[dict], top_k: int) -> list[dict]:
        return results[:top_k]

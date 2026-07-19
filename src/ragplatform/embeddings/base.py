from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    name: str
    dim: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Simetrik kodlama. Asimetrik olmayan sağlayıcılar için tek giriş noktası."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Doküman (index) tarafı. Simetrik sağlayıcıda `embed`'e eşittir."""
        return await self.embed(texts)

    async def embed_query(self, texts: list[str]) -> list[list[float]]:
        """Sorgu tarafı. Asimetrik modeller (ör. Qwen3-Embedding) burada
        instruction öneki uygular; simetrik sağlayıcıda `embed`'e eşittir."""
        return await self.embed(texts)

    async def close(self) -> None:
        pass

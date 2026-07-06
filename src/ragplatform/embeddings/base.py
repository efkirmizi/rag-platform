from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    name: str
    dim: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def close(self) -> None:
        pass

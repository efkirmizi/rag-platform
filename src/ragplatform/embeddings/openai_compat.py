import httpx

from ragplatform.embeddings.base import EmbeddingProvider


class OpenAICompatEmbeddings(EmbeddingProvider):
    """vLLM / OpenAI-uyumlu /v1/embeddings endpoint istemcisi.

    Hedef mimaride embedding'ler on-prem vLLM havuzundan servis edilir;
    bu istemci Faz 0'da G-2 model karşılaştırması için de kullanılır.
    """

    def __init__(self, endpoint: str, model: str, dim: int, api_key: str = ""):
        self._base = endpoint.rstrip("/")
        self.name = model
        self.dim = dim
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(timeout=60.0, headers=headers)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        r = await self._http.post(
            f"{self._base}/embeddings",
            json={"model": self.name, "input": texts},
        )
        r.raise_for_status()
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        vectors = [d["embedding"] for d in data]
        for v in vectors:
            if len(v) != self.dim:
                raise ValueError(
                    f"Beklenen boyut {self.dim}, gelen {len(v)} — "
                    "EMBEDDINGS_DIM ile model uyumsuz (şema vector(1024) sabit, ADR-3 notu)"
                )
        return vectors

    async def close(self) -> None:
        await self._http.aclose()

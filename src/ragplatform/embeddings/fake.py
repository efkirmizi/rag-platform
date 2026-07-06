import hashlib
import math
import random

from ragplatform.embeddings.base import EmbeddingProvider


class FakeEmbeddings(EmbeddingProvider):
    """Deterministik sahte embedding — SADECE ACL doğruluğu ve latency testi için (G-1).

    Anlamsal benzerlik ÜRETMEZ: vektör tarafı gürültü döner, hybrid aramada
    isabet FTS (lexical) tarafından gelir. Kalite ölçümü (G-2) gerçek model ister
    (EMBEDDINGS_PROVIDER=openai ile vLLM endpoint'i).
    """

    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.name = f"fake-{dim}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        v = [rng.gauss(0.0, 1.0) for _ in range(self.dim)]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

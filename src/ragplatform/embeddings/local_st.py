import asyncio

from ragplatform.embeddings.base import EmbeddingProvider


class LocalSTEmbeddings(EmbeddingProvider):
    """sentence-transformers ile yerel embedding (G-2 model denemeleri için).

    CPU'da çalışır; üretim hedefi değildir (üretim: vLLM havuzu, openai_compat).
    bge-m3 dense kullanımında instruction prefix gerekmez; normalize edilmiş
    vektörler cosine mesafeyle uyumludur (şemadaki vector_cosine_ops).
    """

    def __init__(self, model_name: str = "BAAI/bge-m3", dim: int = 1024):
        # Ağır import bilinçli olarak burada: paket, sentence-transformers
        # kurulu olmadan da (fake/openai sağlayıcılarla) çalışabilmeli.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, device="cpu")
        self.name = model_name
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Encode CPU-yoğun ve bloklayıcı — event loop'u tıkamamak için thread'e al
        return await asyncio.to_thread(self._encode, texts)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, batch_size=8)
        if vectors.shape[1] != self.dim:
            raise ValueError(
                f"Model boyutu {vectors.shape[1]} != beklenen {self.dim} "
                "(şema vector(1024) sabit — ADR-3 notu)"
            )
        return [v.tolist() for v in vectors]

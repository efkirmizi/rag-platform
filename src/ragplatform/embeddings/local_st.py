import asyncio

from ragplatform.embeddings.base import EmbeddingProvider


class LocalSTEmbeddings(EmbeddingProvider):
    """sentence-transformers ile yerel embedding (G-2 model karşılaştırması için).

    GPU varsa cuda+float16, yoksa cpu'da çalışır (bkz. ragplatform.hardware).
    Üretim hedefi vLLM havuzudur (openai_compat); bu sağlayıcı Faz 0 ölçümü içindir.

    Query/document asimetrisi model'in kendi `prompts` sözlüğünden gelir:
    - Qwen3-Embedding {query: "Instruct…", document: ""} taşır → query'e prefix eklenir.
    - bge-m3'te prompts yok → düz encode (simetrik). Model başına sabit kodlama yok.
    normalize edilmiş vektörler cosine mesafeyle uyumludur (şemadaki vector_cosine_ops).
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        dim: int = 1024,
        device: str = "auto",
        dtype: str = "auto",
    ):
        # Ağır import bilinçli olarak burada: paket, sentence-transformers
        # kurulu olmadan da (fake/openai sağlayıcılarla) çalışabilmeli.
        from sentence_transformers import SentenceTransformer

        from ragplatform.hardware import log_device, resolve_device_dtype

        dev, torch_dtype = resolve_device_dtype(device, dtype)
        model_kwargs = {"model_kwargs": {"torch_dtype": torch_dtype}} if torch_dtype is not None else {}
        self._model = SentenceTransformer(model_name, device=dev, **model_kwargs)
        log_device("embeddings", model_name, dev, torch_dtype)
        self.name = model_name
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self.embed_documents(texts)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._encode, texts, "document")

    async def embed_query(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._encode, texts, "query")

    def _encode(self, texts: list[str], prompt_name: str) -> list[list[float]]:
        # Encode CPU/GPU-yoğun ve bloklayıcı — event loop'u tıkamamak için thread'e alınır.
        prompts = getattr(self._model, "prompts", None) or {}
        use = prompt_name if prompt_name in prompts else None
        vectors = self._model.encode(
            texts, normalize_embeddings=True, batch_size=8, prompt_name=use
        )
        if vectors.shape[1] != self.dim:
            raise ValueError(
                f"Model boyutu {vectors.shape[1]} != beklenen {self.dim} "
                "(şema vector(1024) sabit — ADR-3 notu)"
            )
        return [v.tolist() for v in vectors]

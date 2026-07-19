from ragplatform.config import Settings
from ragplatform.embeddings.base import EmbeddingProvider
from ragplatform.embeddings.fake import FakeEmbeddings
from ragplatform.embeddings.openai_compat import OpenAICompatEmbeddings


def create_embeddings(settings: Settings) -> EmbeddingProvider:
    if settings.embeddings_provider == "fake":
        return FakeEmbeddings(dim=settings.embeddings_dim)
    if settings.embeddings_provider == "local":
        from ragplatform.embeddings.local_st import LocalSTEmbeddings

        return LocalSTEmbeddings(
            model_name=settings.embeddings_model or "BAAI/bge-m3",
            dim=settings.embeddings_dim,
            device=settings.embeddings_device,
            dtype=settings.embeddings_dtype,
        )
    if settings.embeddings_provider == "openai":
        if not settings.embeddings_endpoint or not settings.embeddings_model:
            raise ValueError("openai provider için EMBEDDINGS_ENDPOINT ve EMBEDDINGS_MODEL zorunlu")
        return OpenAICompatEmbeddings(
            endpoint=settings.embeddings_endpoint,
            model=settings.embeddings_model,
            dim=settings.embeddings_dim,
            api_key=settings.embeddings_api_key,
        )
    raise ValueError(f"Bilinmeyen embeddings_provider: {settings.embeddings_provider}")

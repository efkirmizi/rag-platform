from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Varsayılanlar docker-compose ile birebir uyumlu; .env opsiyoneldir."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://rag:ragpass@localhost:5432/rag"

    fga_api_url: str = "http://localhost:8080"
    # Boşsa fga_state_file'dan okunur (seed script yazar)
    fga_store_id: str = ""
    fga_model_id: str = ""
    fga_state_file: str = "infra/openfga/store.state.json"

    # fake: deterministik, yalnız ACL/latency testi için. openai: vLLM uyumlu endpoint.
    embeddings_provider: str = "fake"
    embeddings_dim: int = 1024
    embeddings_endpoint: str = ""
    embeddings_model: str = ""
    embeddings_api_key: str = ""
    # local sağlayıcı (sentence-transformers) donanımı. auto: cuda varsa cuda+float16,
    # yoksa cpu+float32. Açık değer verilince (cuda/cpu, float16/float32/bfloat16) o kullanılır.
    embeddings_device: str = "auto"
    embeddings_dtype: str = "auto"

    # noop: RRF sırasını korur (Faz 0). local: bge-reranker-v2-m3 cross-encoder (G-2).
    reranker_provider: str = "noop"
    reranker_model: str = ""

    acl_cache_ttl_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()

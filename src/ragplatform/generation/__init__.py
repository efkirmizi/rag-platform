from ragplatform.config import Settings
from ragplatform.generation.base import LLMProvider
from ragplatform.generation.echo import EchoLLM


class GenerationDisabled(RuntimeError):
    """generation_provider=none iken cevap uçları çağrılırsa."""


def create_llm(settings: Settings) -> LLMProvider:
    provider = settings.generation_provider
    if provider == "none":
        raise GenerationDisabled(
            "Üretim kapalı. GENERATION_PROVIDER=echo|local|openai ayarlayın "
            "(echo: model gerektirmez, local: yerel GPU, openai: vLLM endpoint)."
        )
    if provider == "echo":
        return EchoLLM()
    if provider == "local":
        from ragplatform.generation.local_hf import LocalHFLLM

        return LocalHFLLM(
            model_name=settings.generation_model or "Qwen/Qwen2.5-1.5B-Instruct",
            device=settings.embeddings_device,
            dtype=settings.embeddings_dtype,
            max_new_tokens=settings.generation_max_tokens,
        )
    if provider == "openai":
        from ragplatform.generation.openai_compat import OpenAICompatLLM

        if not settings.generation_endpoint or not settings.generation_model:
            raise ValueError(
                "openai üretim sağlayıcısı için GENERATION_ENDPOINT ve GENERATION_MODEL zorunlu"
            )
        return OpenAICompatLLM(
            endpoint=settings.generation_endpoint,
            model=settings.generation_model,
            api_key=settings.generation_api_key,
        )
    raise ValueError(f"Bilinmeyen generation_provider: {provider}")

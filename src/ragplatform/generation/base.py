from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Üretim (generation) sağlayıcısı.

    Hedef mimaride LLM çağrıları LiteLLM gateway'i arkasındaki vLLM'e gider
    (ADR-5 metadata standardı orada zorunlu kılınır). Bu arayüz dar tutuldu ki
    gateway devreye girdiğinde yalnız sağlayıcı değişsin.
    """

    name: str

    @abstractmethod
    async def complete(self, system: str, user: str, *, max_tokens: int = 512) -> str:
        """Sistem + kullanıcı mesajından düz metin cevap üretir."""

    async def close(self) -> None:
        pass

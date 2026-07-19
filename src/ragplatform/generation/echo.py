from ragplatform.generation.base import LLMProvider


class EchoLLM(LLMProvider):
    """Model gerektirmeyen deterministik sağlayıcı — testler ve CI için.

    Gerçek bir cevap üretmez; ilk kaynağa atıf yapan sabit bir metin döner.
    Böylece cevap hattı (prompt → üretim → citation ayrıştırma → ACL) GPU ve
    model indirmesi olmadan uçtan uca test edilebilir.
    """

    name = "echo"

    def __init__(self, canned: str | None = None):
        self._canned = canned

    async def complete(self, system: str, user: str, *, max_tokens: int = 512) -> str:
        if self._canned is not None:
            return self._canned
        if "(kaynak bulunamadı)" in user:
            return "Bu konuda elimdeki kaynaklarda bilgi yok."
        return "Kaynaklara göre özet cevap [1]."

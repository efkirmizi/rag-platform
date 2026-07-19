import httpx

from ragplatform.generation.base import LLMProvider


class OpenAICompatLLM(LLMProvider):
    """vLLM / OpenAI-uyumlu /v1/chat/completions istemcisi — ÜRETİM yolu.

    Hedef mimaride bu istemci doğrudan vLLM'e değil, LiteLLM gateway'ine bakar;
    ADR-5 gereği her çağrıda agent_id/user_id/trace_id gibi metadata zorunlu
    olacak (gateway middleware'de enforce edilir). Şimdilik düz sohbet çağrısı.
    """

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str = "",
        temperature: float = 0.0,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._base = endpoint.rstrip("/")
        self.name = model
        self._temperature = temperature
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(timeout=120.0, headers=headers, transport=transport)

    async def complete(self, system: str, user: str, *, max_tokens: int = 512) -> str:
        r = await self._http.post(
            f"{self._base}/chat/completions",
            json={
                "model": self.name,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": self._temperature,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    async def close(self) -> None:
        await self._http.aclose()

"""Cevap servisi: ACL'li retrieval → prompt → üretim → citation.

Kritik nokta: bu servis retrieval'ı ATLAYAMAZ. Cevap yalnız kullanıcının
görmeye yetkili olduğu chunk'lardan üretilir; yetki filtresi RetrievalService
içinde SQL seviyesinde uygulanır. Yani generation katmanı ACL'i gevşetmez —
yalnız zaten izinli olan içeriği özetler.
"""

import time

from ragplatform.generation.base import LLMProvider
from ragplatform.generation.prompt import build_prompt, extract_citations
from ragplatform.retrieval.service import RetrievalService

NO_CONTEXT_ANSWER = "Bu konuda elimdeki kaynaklarda bilgi yok."


class AnswerService:
    def __init__(
        self,
        retrieval: RetrievalService,
        llm: LLMProvider,
        *,
        max_tokens: int = 512,
    ):
        self._retrieval = retrieval
        self._llm = llm
        self._max_tokens = max_tokens

    async def answer(self, user_id: str, query: str, top_k: int = 5) -> dict:
        t0 = time.perf_counter()
        retrieved = await self._retrieval.retrieve(user_id, query, top_k)
        results = retrieved["results"]

        # Yetkili içerik yoksa modeli hiç çağırma: hem gereksiz maliyet hem de
        # modelin boşlukta halüsinasyon üretme riski.
        if not results:
            return {
                "query": query,
                "user_id": user_id,
                "answer": NO_CONTEXT_ANSWER,
                "citations": [],
                "unsupported_citations": [],
                "retrieval_took_ms": retrieved["took_ms"],
                "took_ms": round((time.perf_counter() - t0) * 1000, 1),
                "llm": self._llm.name,
            }

        bundle = build_prompt(query, results)
        text = await self._llm.complete(
            bundle.system, bundle.user, max_tokens=self._max_tokens
        )
        used, bogus = extract_citations(text, bundle.source_count)

        return {
            "query": query,
            "user_id": user_id,
            "answer": text,
            # Yalnız modelin gerçekten atıf yaptığı kaynaklar döner; sıralama
            # atıf numarasına göre (kullanıcı [1] gördüğünde ilkine bakabilsin).
            "citations": [
                {"n": n, **results[n - 1]["citation"]} for n in used
            ],
            "unsupported_citations": bogus,  # uydurulmuş atıf numaraları
            "retrieval_took_ms": retrieved["took_ms"],
            "took_ms": round((time.perf_counter() - t0) * 1000, 1),
            "llm": self._llm.name,
        }

"""Erişim seti çözümü (ADR-4).

Desen: sorgu anında chunk başına FGA check DEĞİL; kullanıcının erişebildiği
space/page setini ListObjects ile çekip SQL'de metadata pre-filter olarak uygula.
Faz 0'da set kısa TTL'li in-process cache'te tutulur; Faz 1'de kalıcı
materializasyona (tablo + değişiklik senkronu) taşınacak.
"""

import time

from ragplatform.acl.fga import FgaClient


class AccessResolver:
    def __init__(self, fga: FgaClient, ttl_seconds: int = 60):
        self._fga = fga
        self._ttl = ttl_seconds
        self._cache: dict[tuple[str, str], tuple[float, list[str]]] = {}

    async def allowed_spaces(self, user_id: str) -> list[str]:
        return await self._get(user_id, "space", "viewer")

    async def allowed_restricted_pages(self, user_id: str) -> list[str]:
        """Kısıtlı sayfalardan kullanıcının açıkça görebildikleri.

        Not (Confluence semantiği): kısıt erişimi DARALTIR, genişletmez —
        sayfayı görmek için space erişimi de gerekir; SQL filtresi bunu uygular.
        """
        return await self._get(user_id, "page", "restricted_viewer")

    async def _get(self, user_id: str, type_: str, relation: str) -> list[str]:
        key = (user_id, type_)
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
        objects = await self._fga.list_objects(f"user:{user_id}", relation, type_)
        self._cache[key] = (now + self._ttl, objects)
        return objects

    def invalidate(self, user_id: str | None = None) -> None:
        if user_id is None:
            self._cache.clear()
        else:
            for key in [k for k in self._cache if k[0] == user_id]:
                del self._cache[key]

"""OpenFGA HTTP API üzerine ince istemci.

Faz 0'da resmi SDK yerine dar bir HTTP istemcisi tutuyoruz: bağımlılık az,
davranış şeffaf. Faz 1'de gerekirse openfga-sdk'ye geçilir — arayüz dar
tutulduğu için değişim maliyeti düşük.
"""

import json
from pathlib import Path

import httpx

from ragplatform.config import Settings


def resolve_store(settings: Settings) -> tuple[str, str]:
    """Store/model id çözümü: env öncelikli, yoksa seed script'in yazdığı state dosyası."""
    if settings.fga_store_id:
        return settings.fga_store_id, settings.fga_model_id
    state_path = Path(settings.fga_state_file)
    if not state_path.exists():
        raise FileNotFoundError(
            f"{state_path} yok. Önce `python scripts/seed_synthetic.py` çalıştırın "
            "veya FGA_STORE_ID env değişkenini verin."
        )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    return state["store_id"], state["model_id"]


class FgaClient:
    def __init__(self, api_url: str, store_id: str, model_id: str = ""):
        self._base = api_url.rstrip("/")
        self.store_id = store_id
        self.model_id = model_id
        self._http = httpx.AsyncClient(timeout=10.0)

    @classmethod
    def from_settings(cls, settings: Settings) -> "FgaClient":
        store_id, model_id = resolve_store(settings)
        return cls(settings.fga_api_url, store_id, model_id)

    async def list_objects(self, user: str, relation: str, type_: str) -> list[str]:
        """ListObjects: kullanıcının `relation` ilişkisiyle erişebildiği tüm `type_` nesneleri.

        Dönen liste tip öneki olmadan verilir: ["IK", "ENG"] gibi.
        """
        body: dict = {"user": user, "relation": relation, "type": type_}
        if self.model_id:
            body["authorization_model_id"] = self.model_id
        r = await self._http.post(f"{self._base}/stores/{self.store_id}/list-objects", json=body)
        r.raise_for_status()
        return [obj.split(":", 1)[1] for obj in r.json()["objects"]]

    async def close(self) -> None:
        await self._http.aclose()


class FgaAdmin:
    """Bootstrap işlemleri: store + model + tuple yazımı (seed script kullanır)."""

    def __init__(self, api_url: str):
        self._base = api_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=30.0)

    async def create_store(self, name: str) -> str:
        r = await self._http.post(f"{self._base}/stores", json={"name": name})
        r.raise_for_status()
        return r.json()["id"]

    async def write_model(self, store_id: str, model: dict) -> str:
        r = await self._http.post(
            f"{self._base}/stores/{store_id}/authorization-models", json=model
        )
        r.raise_for_status()
        return r.json()["authorization_model_id"]

    async def write_tuples(
        self, store_id: str, model_id: str, tuples: list[tuple[str, str, str]], batch: int = 50
    ) -> int:
        """tuples: (user, relation, object) üçlüleri. Örn: ("group:eng#member", "viewer", "space:ENG")"""
        written = 0
        for i in range(0, len(tuples), batch):
            keys = [
                {"user": u, "relation": rel, "object": obj}
                for u, rel, obj in tuples[i : i + batch]
            ]
            r = await self._http.post(
                f"{self._base}/stores/{store_id}/write",
                json={"writes": {"tuple_keys": keys}, "authorization_model_id": model_id},
            )
            r.raise_for_status()
            written += len(keys)
        return written

    async def close(self) -> None:
        await self._http.aclose()

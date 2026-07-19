# -*- coding: utf-8 -*-
"""Çalışan bir retrieval API'sini uçtan uca doğrular (sentetik korpus gerekir).

Üç şeyi kanıtlar:
  1) /healthz ayakta,
  2) yetkili kullanıcı sonuç alıyor,
  3) KISITLI sayfa yalnız yetkilisine dönüyor — aynı space'i gören yetkisiz
     kullanıcı aynı soruyu sorduğunda o sayfayı ALMIYOR (asıl iddia bu).

CI'da `docker compose --profile demo up` sonrası koşar; yerelde de kendi
kurulumunuzu doğrulamak için kullanılabilir. Payload'lar httpx ile JSON olarak
gönderilir — kabuk/locale kaynaklı UTF-8 bozulması olmaz.

Çalıştırma: python scripts/smoke_api.py [--base-url http://localhost:8000]
"""

import argparse
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SALARY_Q = "maaş bantları seviye matrisi"
RESTRICTED_PAGE = "ik-maas-bantlari"


def _pages(client: httpx.Client, base: str, user: str, query: str, top_k: int = 8) -> list[str]:
    r = client.post(
        f"{base}/v1/retrieve",
        json={"query": query, "user_id": user, "top_k": top_k},
    )
    r.raise_for_status()
    return [item["citation"]["page_key"] for item in r.json()["results"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    failures: list[str] = []

    with httpx.Client(timeout=30.0) as client:
        health = client.get(f"{base}/healthz")
        health.raise_for_status()
        print(f"[ok] /healthz -> {health.json()}")

        # 1) Yetkili kullanıcı sonuç almalı
        ayse = _pages(client, base, "ayse", "yıllık izin kaç gün", top_k=3)
        print(f"[..] ayse            -> {ayse}")
        if not ayse:
            failures.append("ayse için sonuç dönmedi (izinli içerik bulunamadı)")

        # 2) Kısıtlı sayfanın yetkilisi görmeli
        zeynep = _pages(client, base, "zeynep", SALARY_Q)
        print(f"[..] zeynep (yetkili) -> {zeynep}")
        if RESTRICTED_PAGE not in zeynep:
            failures.append(f"yetkili kullanıcı '{RESTRICTED_PAGE}' sayfasını GÖREMEDİ")

        # 3) Aynı space'i gören ama yetkisiz kullanıcı GÖRMEMELİ  ← asıl kapı
        mehmet = _pages(client, base, "mehmet", SALARY_Q)
        print(f"[..] mehmet (yetkisiz)-> {mehmet}")
        if RESTRICTED_PAGE in mehmet:
            failures.append(f"SIZINTI: yetkisiz kullanıcıya '{RESTRICTED_PAGE}' döndü")

    print()
    if failures:
        for f in failures:
            print(f"❌ {f}")
        return 1
    print("✅ API smoke testi geçti — ACL uçtan uca uygulanıyor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

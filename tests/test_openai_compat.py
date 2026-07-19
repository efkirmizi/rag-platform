# -*- coding: utf-8 -*-
"""vLLM / OpenAI-uyumlu embedding istemcisi — sözleşme testleri.

Bu sağlayıcı ÜRETİM hedefidir (embedding'ler vLLM havuzundan servis edilir) ama
yerel ölçümler `local` sağlayıcıyla yapıldığı için gerçek bir endpoint'e karşı
hiç koşmadı. Burada httpx.MockTransport ile sözleşme sabitlenir: istek gövdesi,
kimlik başlığı, sıra garantisi, boyut doğrulaması ve hata yayılımı.
"""

import httpx
import pytest

from ragplatform.embeddings.openai_compat import OpenAICompatEmbeddings

DIM = 4


def _vec(seed: float) -> list[float]:
    return [seed + i for i in range(DIM)]


def _provider(handler, *, api_key: str = "", dim: int = DIM) -> OpenAICompatEmbeddings:
    return OpenAICompatEmbeddings(
        endpoint="http://vllm.local/v1",
        model="bge-m3",
        dim=dim,
        api_key=api_key,
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_request_shape_and_endpoint():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": _vec(0)}]})

    p = _provider(handler)
    await p.embed(["merhaba"])
    await p.close()

    assert seen["url"] == "http://vllm.local/v1/embeddings"
    assert seen["body"] == {"model": "bge-m3", "input": ["merhaba"]}
    assert seen["auth"] is None  # api_key verilmedi -> başlık yok


@pytest.mark.asyncio
async def test_authorization_header_when_api_key_given():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": _vec(0)}]})

    p = _provider(handler, api_key="s3cret")
    await p.embed(["x"])
    await p.close()
    assert seen["auth"] == "Bearer s3cret"


@pytest.mark.asyncio
async def test_results_are_reordered_by_index():
    """Sunucu sırayı bozarsa bile çıktı girdi sırasını korumalı —
    aksi hâlde yanlış vektör yanlış chunk'a yazılır (sessiz bozulma)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [  # bilinçli olarak karışık sırada
                    {"index": 2, "embedding": _vec(200)},
                    {"index": 0, "embedding": _vec(0)},
                    {"index": 1, "embedding": _vec(100)},
                ]
            },
        )

    p = _provider(handler)
    out = await p.embed(["a", "b", "c"])
    await p.close()
    assert out == [_vec(0), _vec(100), _vec(200)]


@pytest.mark.asyncio
async def test_dimension_mismatch_raises():
    """Şema vector(1024) sabit — yanlış model erken yakalanmalı."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 2.0]}]})

    p = _provider(handler)  # dim=4 bekleniyor, 2 geliyor
    with pytest.raises(ValueError, match="Beklenen boyut"):
        await p.embed(["x"])
    await p.close()


@pytest.mark.asyncio
async def test_http_error_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "model yükleniyor"})

    p = _provider(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await p.embed(["x"])
    await p.close()


@pytest.mark.asyncio
async def test_query_and_document_default_to_symmetric():
    """Bu sağlayıcı simetrik: embed_query == embed_documents == embed."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        calls.append(json.loads(request.content)["input"])
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": _vec(1)}]})

    p = _provider(handler)
    a = await p.embed(["soru"])
    b = await p.embed_query(["soru"])
    c = await p.embed_documents(["soru"])
    await p.close()

    assert a == b == c
    assert calls == [["soru"], ["soru"], ["soru"]]  # hiçbirine prefix eklenmedi

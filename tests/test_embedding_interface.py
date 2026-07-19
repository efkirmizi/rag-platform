# -*- coding: utf-8 -*-
"""Asimetrik embedding arayüzü (embed_query / embed_documents).

Simetrik sağlayıcılarda (fake, openai) üçü de aynı sonucu vermeli — base
sınıfının varsayılanları `embed`'e düşer. Asimetrik sağlayıcı (Qwen3, local_st)
query'e prompt öneki uygular; o davranış model indirmesi gerektirdiği için
burada değil, entegrasyon koşusunda doğrulanır.
"""

import pytest

from ragplatform.embeddings.fake import FakeEmbeddings


@pytest.mark.asyncio
async def test_symmetric_provider_query_equals_document_equals_embed():
    emb = FakeEmbeddings(dim=32)
    [q] = await emb.embed_query(["yıllık izin politikası"])
    [d] = await emb.embed_documents(["yıllık izin politikası"])
    [e] = await emb.embed(["yıllık izin politikası"])
    assert q == e
    assert d == e


@pytest.mark.asyncio
async def test_document_and_query_are_batch_shaped():
    emb = FakeEmbeddings(dim=16)
    docs = await emb.embed_documents(["a", "b", "c"])
    assert len(docs) == 3
    assert all(len(v) == 16 for v in docs)

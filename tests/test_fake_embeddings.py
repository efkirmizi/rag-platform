# -*- coding: utf-8 -*-
import math

import pytest

from ragplatform.embeddings.fake import FakeEmbeddings


@pytest.mark.asyncio
async def test_deterministic():
    emb = FakeEmbeddings(dim=64)
    [a] = await emb.embed(["yıllık izin politikası"])
    [b] = await emb.embed(["yıllık izin politikası"])
    assert a == b


@pytest.mark.asyncio
async def test_different_texts_differ():
    emb = FakeEmbeddings(dim=64)
    [a], [b] = await emb.embed(["metin bir"]), await emb.embed(["metin iki"])
    assert a != b


@pytest.mark.asyncio
async def test_dim_and_unit_norm():
    emb = FakeEmbeddings(dim=128)
    [v] = await emb.embed(["deneme"])
    assert len(v) == 128
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9)

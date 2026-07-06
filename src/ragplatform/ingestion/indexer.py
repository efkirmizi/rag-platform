"""Sayfa upsert + chunk index'leme.

Idempotent: aynı page_key tekrar geldiğinde sayfa güncellenir, eski chunk'lar
silinip yenileri yazılır. content_hash ile değişmemiş sayfayı atlama
(incremental sync) Faz 1'de connector tarafına eklenecek.
"""

import hashlib

import asyncpg

from ragplatform.embeddings.base import EmbeddingProvider
from ragplatform.ingestion.chunking import chunk_markdown
from ragplatform.retrieval.hybrid import _to_pgvector


async def upsert_space(pool: asyncpg.Pool, key: str, name: str) -> None:
    await pool.execute(
        "INSERT INTO spaces(key, name) VALUES($1, $2) "
        "ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name",
        key,
        name,
    )


async def index_page(
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    *,
    page_key: str,
    space_key: str,
    title: str,
    content_md: str,
    url: str | None = None,
    is_restricted: bool = False,
) -> int:
    """Sayfayı chunk'layıp embed'leyerek indexler; chunk sayısını döner."""
    chunks = chunk_markdown(content_md)
    if not chunks:
        return 0
    # Bağlam başlığı: sayfa başlığı + heading yolu chunk metnine gömülür.
    # Hem FTS hem embedding isabetini artırır (örn. başlıkta geçen "maaş bantları"
    # gövdede "maaş bandı" olarak çekimlenmişse stemmer t/d yumuşamasını eşleyemez;
    # başlık satırı bu boşluğu kapatır). Contextual retrieval'ın hafif hali.
    contents = [
        f"[{title if not c.heading_path else f'{title} > {c.heading_path}'}]\n{c.content}"
        for c in chunks
    ]
    embeddings = await embedder.embed(contents)
    content_hash = hashlib.sha256(content_md.encode("utf-8")).hexdigest()

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO pages(page_key, space_key, title, url, is_restricted, content_hash)
                VALUES($1, $2, $3, $4, $5, $6)
                ON CONFLICT (page_key) DO UPDATE
                    SET space_key = EXCLUDED.space_key,
                        title = EXCLUDED.title,
                        url = EXCLUDED.url,
                        is_restricted = EXCLUDED.is_restricted,
                        content_hash = EXCLUDED.content_hash,
                        updated_at = now()
                RETURNING id
                """,
                page_key,
                space_key,
                title,
                url,
                is_restricted,
                content_hash,
            )
            page_id = row["id"]
            await conn.execute("DELETE FROM chunks WHERE page_id = $1", page_id)
            await conn.executemany(
                """
                INSERT INTO chunks(page_id, chunk_index, heading_path, content,
                                   embedding, embedding_model)
                VALUES($1, $2, $3, $4, $5::vector, $6)
                """,
                [
                    (page_id, i, c.heading_path, text, _to_pgvector(e), embedder.name)
                    for i, (c, text, e) in enumerate(zip(chunks, contents, embeddings))
                ],
            )
    return len(chunks)

"""Hybrid arama: pgvector HNSW (dense) + Postgres FTS turkish_unaccent (lexical), RRF füzyonu.

ACL pre-filter her iki kolda da SQL seviyesinde uygulanır (fail-closed):
- space_key kullanıcının erişim setinde olmalı
- kısıtlı sayfalar yalnız açıkça izinli page_key setindeyse görünür
Post-filter YOK: izinsiz içerik aday listesine bile giremez (ADR-4).
"""

import asyncpg

RRF_K = 60

_HYBRID_SQL = """
WITH vec AS (
    SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> $1::vector) AS rnk
    FROM chunks c
    JOIN pages p ON p.id = c.page_id
    WHERE p.space_key = ANY($2::text[])
      AND (NOT p.is_restricted OR p.page_key = ANY($3::text[]))
    ORDER BY c.embedding <=> $1::vector
    LIMIT $4
),
fts AS (
    SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.content_tsv, q.tsq) DESC) AS rnk
    FROM chunks c
    JOIN pages p ON p.id = c.page_id
    CROSS JOIN (SELECT websearch_to_tsquery('turkish_unaccent', $5) AS tsq) q
    WHERE c.content_tsv @@ q.tsq
      AND p.space_key = ANY($2::text[])
      AND (NOT p.is_restricted OR p.page_key = ANY($3::text[]))
    LIMIT $4
),
fused AS (
    SELECT COALESCE(vec.id, fts.id) AS id,
           COALESCE(1.0 / ($6 + vec.rnk), 0) + COALESCE(1.0 / ($6 + fts.rnk), 0) AS rrf_score,
           vec.rnk AS vec_rank,
           fts.rnk AS fts_rank
    FROM vec
    FULL OUTER JOIN fts USING (id)
)
SELECT f.rrf_score, f.vec_rank, f.fts_rank,
       c.content, c.heading_path, c.chunk_index,
       p.page_key, p.title, p.url, p.space_key, p.is_restricted, p.updated_at
FROM fused f
JOIN chunks c ON c.id = f.id
JOIN pages p ON p.id = c.page_id
ORDER BY f.rrf_score DESC
LIMIT $7
"""


def _to_pgvector(embedding: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"


async def hybrid_search(
    pool: asyncpg.Pool,
    query_embedding: list[float],
    query_text: str,
    allowed_spaces: list[str],
    allowed_restricted_pages: list[str],
    candidate_k: int = 50,
    fused_k: int = 24,
) -> list[dict]:
    """Her iki koldan candidate_k aday çeker, RRF ile birleştirip fused_k döner.

    allowed_spaces boşsa SQL sıfır satır döner (fail-closed) — çağıran taraf
    yine de boş listeyle kısa devre yapabilir.
    """
    rows = await pool.fetch(
        _HYBRID_SQL,
        _to_pgvector(query_embedding),
        allowed_spaces,
        allowed_restricted_pages,
        candidate_k,
        query_text,
        RRF_K,
        fused_k,
    )
    return [dict(r) for r in rows]

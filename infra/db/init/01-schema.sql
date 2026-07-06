-- Kurumsal RAG platformu — Faz 0 şeması
-- Not: embedding boyutu 1024 (bge-m3 / Qwen3-Embedding-0.6B ile uyumlu).
-- Model değişirse ADR-3 gereği embedding_model kolonu + re-embed runbook kullanılır.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Türkçe FTS: snowball turkish_stem + unaccent (İ/ı, ğ, ş vb. aksan normalizasyonu)
CREATE TEXT SEARCH CONFIGURATION turkish_unaccent (COPY = turkish);
ALTER TEXT SEARCH CONFIGURATION turkish_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, turkish_stem;

CREATE TABLE spaces (
    key  text PRIMARY KEY,
    name text NOT NULL
);

CREATE TABLE pages (
    id            bigserial PRIMARY KEY,
    page_key      text NOT NULL UNIQUE,
    space_key     text NOT NULL REFERENCES spaces(key) ON DELETE CASCADE,
    title         text NOT NULL,
    url           text,
    -- Confluence semantiği: kısıtlı sayfayı yalnız restricted_viewer görür;
    -- kısıt, space erişimini GENİŞLETMEZ, daraltır.
    is_restricted boolean NOT NULL DEFAULT false,
    content_hash  text,
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX pages_space_idx ON pages (space_key);

CREATE TABLE chunks (
    id              bigserial PRIMARY KEY,
    page_id         bigint NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    chunk_index     int NOT NULL,
    heading_path    text NOT NULL DEFAULT '',
    content         text NOT NULL,
    content_tsv     tsvector GENERATED ALWAYS AS (to_tsvector('turkish_unaccent', content)) STORED,
    embedding       vector(1024),
    embedding_model text NOT NULL,
    UNIQUE (page_id, chunk_index)
);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (content_tsv);
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);

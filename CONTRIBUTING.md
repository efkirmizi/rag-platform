# Contributing

Thanks for your interest. This is a Phase 0 research project — the roadmap and
architectural decisions live in [PROJE-PLANI.md](PROJE-PLANI.md) (Turkish).

## The one rule that matters

**Retrieval must never return content a user is not permitted to see.**

Any change touching `retrieval/`, `acl/`, the SQL in `hybrid.py`, or the OpenFGA
model must keep the leak test at **0 violations**:

```bash
python scripts/acl_leak_test.py     # must print "ACL sızıntısı: 0"
```

If you add a filter, add it *inside* the SQL (pre-filter). Do not filter results
after the query returns — a post-filter that is forgotten in one code path is
exactly the bug class this project exists to prevent.

## Setup

```bash
docker compose up -d              # Postgres + pgvector, OpenFGA
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python scripts/seed_synthetic.py  # synthetic corpus + permissions
```

Optional, for local embedding/reranker models (GPU auto-detected):

```bash
pip install -e ".[local]"
```

## Before opening a pull request

```bash
ruff check src scripts tests      # lint
pytest                            # unit tests (no services or GPU needed)
python scripts/acl_leak_test.py   # ACL gate — must be 0
python scripts/run_eval.py --golden eval/golden/golden_v2.jsonl   # eval gate
```

CI runs exactly these on every PR, so a green local run should mean a green CI.

## Project conventions

- **Golden set is append-only.** Adding questions is fine; changing or deleting
  existing ones breaks score comparability. If you must change the set's
  semantics, create a new version file (`golden_v3.jsonl`) — see
  [eval/golden/README.md](eval/golden/README.md).
- **Eval results are committed.** `eval/results/` tracks baselines over time.
- **Quality claims need measurements.** "This improves retrieval" should come
  with an eval run showing it. Overlap, chunking, and query-rewrite changes in
  particular have to be demonstrated, not asserted.
- **Comments explain *why*, not *what*.** Existing code comments are in Turkish;
  match the surrounding file. New user-facing docs should be English +
  Turkish where practical.
- **Keep dependencies few.** This is deliberately a small dependency set.
  Heavy/optional things (torch, sentence-transformers) belong in the `local`
  extra with lazy imports so the core package works without them.

## Architecture orientation

```
src/ragplatform/
  acl/          OpenFGA client + access-set resolution (ADR-4)
  embeddings/   fake (tests) · local (GPU) · openai-compatible (vLLM)
  ingestion/    chunking, indexing, corpus model, folder connector
  retrieval/    hybrid search + RRF + reranker + service
  api/          FastAPI retrieval service
```

The most important file is `src/ragplatform/retrieval/hybrid.py` — it contains
the ACL pre-filter, and its correctness is the project's core claim.

## Reporting security issues

Do **not** open a public issue for a permission-bypass bug. See
[SECURITY.md](SECURITY.md).

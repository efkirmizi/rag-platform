## What and why

<!-- What does this change, and what problem does it solve? -->

## Checks

- [ ] `ruff check src scripts tests` passes
- [ ] `pytest` passes
- [ ] `python scripts/acl_leak_test.py` → **0 leaks** (required if this touches
      retrieval, ACL, the hybrid SQL, or the OpenFGA model)
- [ ] `python scripts/run_eval.py --golden eval/golden/golden_v2.jsonl` → no ACL violations

## Retrieval quality

<!-- If this could change ranking (chunking, embeddings, reranker, query handling,
     RRF, FTS), paste the before/after eval numbers. "Should be better" is not
     enough — the golden set exists to settle this. Delete this section if N/A. -->

| | MRR | hit@1 | hit@5 | parafraz@5 |
|---|---|---|---|---|
| before | | | | |
| after | | | | |

## Notes

<!-- Trade-offs, follow-ups, anything a reviewer should know. -->

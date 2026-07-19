# Security Policy

## ⚠️ Do not deploy this as-is

This project is at **Phase 0 (proof of concept)**. It is a research/reference
implementation, **not a production system**. Specifically:

| Gap | Detail |
|---|---|
| **No authentication** | `POST /v1/retrieve` takes `user_id` **in the request body**. Anyone who can reach the API can impersonate any user and read everything that user may read. Real identity (OIDC) arrives in Phase 1. |
| **No authorization on the API itself** | There is no API key, token, rate limit, or tenant isolation at the HTTP layer. |
| **Default credentials** | `docker-compose.yml` ships well-known dev credentials (`rag` / `ragpass`) and an unauthenticated OpenFGA. These are for local development only. |
| **No audit log** | Immutable audit logging is a Phase 2 deliverable. |
| **Synthetic permissions** | The shipped permission model is a synthetic scenario, not a real org's. |

**If you expose this to a network you do not fully control, you have an
unauthenticated read API in front of your documents.** Run it locally, or put
real authentication in front of it first.

## What *is* security-tested

The core claim of this project — that retrieval respects document-level
permissions — is continuously verified:

- **ACL pre-filter is fail-closed.** The user's permitted space/page set is
  applied *inside the SQL query* (`src/ragplatform/retrieval/hybrid.py`).
  Unauthorized content never enters the candidate list; there is no post-filter
  to forget. Empty access set ⇒ zero rows.
- **Leak test on every change.** `scripts/acl_leak_test.py` runs every user ×
  query combination and asserts that every returned chunk is one the user is
  independently expected to see. Current: **0 leaks / 480 results**.
- **Boundary questions in the eval set.** `golden_v2.jsonl` contains
  `yetki-siniri` cases where a user who *can* see the space must **not** see a
  restricted page in it. Any violation fails the eval with a non-zero exit code.
- **Both run in CI** on every push and pull request.

### Known design decisions relevant to security

- **Retrieved content is untrusted (ADR-8).** Indexed document text must never be
  able to trigger tool calls or be treated as instructions. Prompt-injection
  defenses are a Phase 2 deliverable; today this service performs no generation
  and calls no tools, so the surface is limited to what it returns.
- **Permission freshness (ADR-9).** The access set is cached in-process with a
  short TTL (`ACL_CACHE_TTL_SECONDS`, default 60s). A permission revoked at the
  source is therefore visible to retrieval for up to that TTL. The target SLA
  (≤15 min end-to-end, including source-system sync) is a Phase 2 deliverable.

## Reporting a vulnerability

If you find a way to make retrieval return content a user should not see, that
is the bug this project most wants to hear about.

Please report privately rather than opening a public issue:

- Open a [GitHub security advisory](https://github.com/efkirmizi/rag-platform/security/advisories/new), or
- Email **enisfurkankirmizi2003@gmail.com**

Please include a reproduction (a corpus + permission setup + query is ideal).
Given this is a pre-production research project maintained by one person, expect
a first response within about a week. There is no bug bounty.

## Supported versions

Only `main` is supported. There are no released versions and no backports yet.

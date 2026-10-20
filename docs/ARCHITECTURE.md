# Architecture and browser contracts

## Integration

`frontend/src/app` owns routing, shared shell, session/server state and selected policy. Feature directories contain auth, policies/upload/overview, questions/sources, claims, comparison, guide and settings. UI controls and local design tokens are shared. TanStack Query manages server state; React Hook Form/Zod handles forms; local state holds interaction state. Source Sans 3 is served locally.

`src/api/contracts.ts` validates every structured response using Zod. `real.ts` always calls the API and returns actionable errors. `demo.ts` is a separate development-only fixture adapter. There is no real-to-demo fallback. Vite rejects demo builds; production eliminates the dynamic demo import. Never treat demo authentication as a security boundary.

`api/app.py` is the FastAPI factory. `api/auth.py` supplies session dependencies used by every resource router. `api/db.py` adds owned resource tables to the existing `PolicyStore` database. Uploads use existing `process_pdf` + `chunk_policy` and persist chunks using `PolicyStore`. New public policy IDs are random, and same-content deduplication is scoped to the owner. Retrieval uses `PersistentPolicyService(use_semantic=False)` so no embedding model needs to download or retain derived caches. Existing CLI/semantic services remain available independently.

`api/questions.py` wraps the existing `answer_policy_question`, `make_verification_request`, `make_verifier_search`, and `verify_answer`. It captures both initial and independent-search sources. It returns only claim text covered by verification; the draft's separate answer prose is not returned as verified. Generation/citation/verifier failure cannot produce a verified answer. Prior user questions from the same owned conversation are explicitly untrusted context. Conditional output remains unconfirmed; no probabilistic scores are shown. User facts are not automatically extracted into the verifier's structured user_facts dictionary, so some follow-ups can still need human review.

`api/comparison.py` reuses `compare_policies` and strips `financial_difference` and `comparable` from browser responses because context equivalence is not established. The original CLI output is unchanged. `api/claims.py` provides a real manual organizer; it does not infer insurer obligations.

## Routes

Public frontend: `/login`, `/signup`, `/forgot-password`, `/reset-password`.
Authenticated frontend: `/policies`, `/policies/:id`, `/ask?policy=:id&conversation=:id`, `/claims?policy=:id`, `/compare`, `/guide`, `/settings`.

API:
- `GET /api/config`, `GET /api/health` — public, non-secret capabilities/configuration.
- `POST /api/auth/signup` `{name,email,password}`; `POST /api/auth/login` `{email,password}`; `GET /api/auth/session` — return `{user:{id,name,email},csrf}` and an opaque HttpOnly session cookie.
- `POST /api/auth/logout`, `POST /api/auth/password` `{current,password}`, `PATCH /api/auth/profile` `{name}`.
- `POST /api/auth/forgot` `{email}` — honest development instructions / production 503. `POST /api/auth/reset` `{token,password}` — single-use reset, invalidates all sessions.
- `GET /api/policies`; `POST /api/policies` — raw PDF body with percent-encoded `X-Filename`, bounded actual bytes. Raw upload enables measurable XHR transfer progress; processing remains indeterminate.
- `GET /api/policies/:id`; `POST .../opened`; `PATCH ...` `{archived}`; `DELETE ...` — owned metadata and lifecycle.
- `GET .../original` — owned attachment; `GET .../pages/:page` — extracted page text and page count; `GET .../pages/:page/image` — bounded raster preview. No PDF actions, remote embeds or scripting run in the viewer.
- `GET .../conversations`; `POST .../questions` `{question,conversation_id?}` — owned conversation with messages. A message includes `question`, timestamp and `{status,text,claims,missing_information,sources,warnings}`. Status is `verified` or `insufficient_evidence`. Claims contain exact verified text and source objects; source objects contain owned policy/passage ID, exact page range/text and optional exact quote/section.
- `GET /api/claims`; `POST /api/claims`; `PUT /api/claims/:id` — `{policy_id,description,incident_date,gathered}`; `DELETE /api/claims/:id`; `GET /api/claims/:id/export` — authorized UTF-8 plain-text attachment.
- `POST /api/comparison` `{a,b}` — nine evidence categories and limitations. Findings use `supported` (rendered as “Relevant text found”), `uncertain`, or `not_found`. No savings/ranking or numeric difference is exposed.

All unsafe API requests require `X-PolicyIQ: 1`; authenticated unsafe requests also require `X-CSRF-Token` from the in-memory session response. Origin, when present, must exactly match `POLICYIQ_ORIGIN`. There is no credentialed cross-origin CORS. Missing/expired sessions return 401; ownership mismatch returns 404; validation 422; body size 413; throttling 429; unavailable provider/delivery 503. Errors exclude stack traces and filesystem paths.

## Remaining integration work

Add a configured production email delivery mechanism and address verification, preferably migrate to a mature identity platform for internet-scale deployment. Add structured extraction with financial contexts and claim requirements/deadlines/citations before displaying them as policy-derived. Add independently owned scanned-document OCR and claim attachments only with explicit storage/processing rules. Expand country guidance through reviewed content and maintenance dates. Process-isolate PDF parsing and introduce production quotas/observability/retention controls.

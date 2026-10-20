# PolicyIQ development checkpoints

## 0 — Repository assessment (2026-10-20)
- Clean tracked working tree; no applicable AGENTS.md. Python-only repository, no frontend/API/design exports.
- Existing: PyMuPDF ingestion with stable error codes; keyword/hybrid passage retrieval; structured generation/citation checking; independent OpenRouter verification; SQLite PolicyStore/PersistentPolicyService; evidence comparison. Existing services will remain the integration points.
- Missing: ownership/session boundary, browser contracts, originals, conversations, claims, summaries and country content.
- Risks identified: separately generated prose is not covered by claim verification; comparison computes amounts without equivalent context. Browser contract will expose only fully checked claim text and suppress numerical differences.
- Runtime: Python 3.12.8 (no project packages installed), Node 22.16.0, npm 10.9.2 via npm.cmd (PowerShell script policy blocks npm.ps1).
- Official Vite, React Router, Tailwind and FastAPI docs checked. Node meets Vite's 22.12+ requirement.
- Order: shell/adapters; auth; owned uploads; verified claim answers/sources; claims/comparison; guide/hints; browser polish; regression/security verification.
- Deployment: same-origin FastAPI + built SPA; Vite /api proxy during local development. No external deployment.

## 1 — Foundation
In progress.

## 1 — Foundation verified
- React/TypeScript/Vite 8, Router, Query, RHF/Zod, Tailwind tokens, local Source Sans 3, shared responsive shell, error boundary, validated adapters and explicit development-only demo.
- npm run build and npm run lint passed. Latest resolver 6 had an upstream optional-peer conflict; resolver 5 installed cleanly without force flags. npm audit at installation: zero findings.
- Vite starts on 127.0.0.1:5173. Playwright foundation check passed across five direct routes at 1440/1024/390 px, shared navigation and no horizontal overflow.
- Browser connector has no available browser surfaces; installed Playwright Chromium is used for the requested browser inspection.

## 2 — Authentication boundary verified
- Real Argon2id passwords, hashed opaque server sessions, HttpOnly/SameSite cookies, Secure + HSTS in production, session rotation/expiry/logout, CSRF token and origin/custom-header protection, persistent rate limits.
- Login, signup, forgot/reset forms with visibility, autocomplete, validation and safe recoverable values. Password reset delivery fails explicitly; local operator-only one-time link command is available outside production.
- python -m pytest tests/test_web.py -q: 5 passed (lifecycle, invalid input, CSRF/origin, rate limiting, reset single-use, production guard). Frontend typecheck passed.
- Existing backend baseline: 49 passed, 1 failed because the fallback-provider unit test constructs credential-dependent providers before replacing them with mocks. Will fix the test isolation at final regression checkpoint.
- Cross-user resource cases follow in policy checkpoint. No email delivery or email-address verification configured. TestClient dependency emits a new httpx2 migration warning; will resolve before final checks.

## 3 — Policies and uploads verified
- Owned SQLite policies/original PDF bytes with random public IDs; reuse existing ingestion, chunking and PolicyStore. Safe display filenames, 20 MB / 300-page caps, file signature/parsing validation, duplicate handling per user, persisted archive/last-opened state, cascading deletion.
- Original downloads require ownership. Viewer pages are rasterized server-side; embedded PDF scripts/links do not execute in the browser.
- Frontend empty/list/search, upload selection/replace/remove, measured transfer progress, indeterminate processing, cancellation, recovery and delete confirmation implemented.
- python -m pytest tests/test_web.py tests/test_ingest.py tests/test_storage.py -q: 30 passed. Covered duplicate upload, actual original bytes, restart recovery, A/B ownership (including same PDF), traversal filename, invalid/corrupt/unreadable PDFs, page bounds, size rejection and deletion isolation.
- Fixed a real Windows corrupt-PDF handle leak in ingestion: bounded PDF bytes now open in memory; temporary file cleanup no longer masks the actionable error.
- Limits: no OCR, antivirus or process-isolated PDF parser; logical deletion cannot guarantee erasure from filesystem backups/WAL. Full browser upload journey follows with overview.

## 4 — Overview, questions and sources verified
- Policy overview favors questions and document metadata; real policies never receive sample financial facts. Demo financial term is labelled fictional with context and source.
- Existing retrieval/generation/independent verification wrapped by browser contract. Only verified claim text is displayed as verified; unrelated draft prose is omitted. Failed verification returns no confirmed claims. Source references include exact excerpts/pages/quotes and independently found supporting evidence.
- Conversations persist under policy ownership. Follow-ups include previous user questions as untrusted context. Policy-keyed query state and separately keyed conversation components isolate switching.
- Native modal source panel and original-page raster viewer preserve underlying page state, provide text transcripts and authorized original downloads. React renders all content as text.
- Question/verification regression subset: 11 passed. Explicitly checked extra unverified prose exclusion, matching citations, follow-up persistence, cross-user conversations and provider/verification failure. Typecheck/lint passed.
- OpenRouter and Ollama now have 20-second request timeouts; verifier extra queries capped at five. Provider calls remain disabled by default. No live-provider smoke test (credentials unavailable).

## 5 — Claims and comparison verified
- Three-step claim organizer with validated details, saved drafts, recommended gathered-document checklist, recalculated preparation completeness, editable back navigation and actual UTF-8 text download.
- Real manual organization works without model claim extraction. Required obligations/deadlines explicitly remain unestablished. No file attachment storage or insurer submission is implied. Demo drafts use the separate in-memory adapter.
- Existing evidence-comparison service reused behind ownership checks. Browser response removes financial_difference/comparable fields because matching contexts are unproven. All nine categories preserve not-found/uncertain/evidence states.
- python -m pytest tests/test_web.py tests/test_comparison.py -q: 17 passed, including export contents/HTML-as-text, invalid dates, cross-user draft/export denial, deletion cascade, comparison ownership and suppressed differences.
- Typecheck passed; replaced RHF watch with useWatch after lint identified compiler-incompatible usage.

## 6 — Country guide and first-use assistance
- Optional country/coverage questionnaire; reviewed US starting links from official HealthCare.gov quick guide, job-based coverage guide, and state directory (reviewed 2026-10-20). No eligibility determinations or hardcoded enrollment deadlines. Other countries show a safe unsupported state.
- Country changes reset dependent answers. Guide remains usable before adding a policy. Links open safely with noopener/noreferrer.
- Four contextual keyboard-accessible hints with individual dismissal, skip-all and replay. Only these non-sensitive preferences use localStorage.
- Account profile/password/signout screens and configured-processing privacy disclosure completed. Guide/hint browser assertions are included in final journeys.

## 7 — Browser polish and end-to-end journeys verified
- Playwright E2E suite (`npx.cmd playwright test`) passing across 5 test specs with dual workers against real and demo server instances.
- Comprehensive user journeys verified: account lifecycle (signup, login, session expiry, logout), policy PDF upload and invalid/corrupt file recovery, server-side raster page viewer with text transcripts and focus restoration, verifier question retry and source panel modal with quote highlighting, contextual follow-up message isolation, 3-step claim organizer with checklist completeness and UTF-8 plain text export, multi-policy evidence comparison across 9 categories, guided US/unsupported country flows, and dismissible/replayable contextual hints.
- Responsive layout verified across desktop (1440px), tablet (1024px), and mobile (390px) with zero horizontal overflow (`scrollWidth <= innerWidth`).
- Accessibility: automated axe-core accessibility analysis across all primary views returned zero violations. Fixed landmark uniqueness requirements by attaching distinct ARIA labels (`Sidebar navigation`, `Helpful tip`, `First-use assistance`, `Claim preparation progress`, `PolicyIQ overview`) to all `<aside>` complementary landmarks.

## 8 — Regression and security verification
- Backend regression: 61 passed in pytest suite (`.\.venv\Scripts\python.exe -m pytest -q`). Verified fallback provider unit test isolation via monkeypatch.
- Frontend regression: 5 passed in Vitest unit suite, TypeScript check (`tsc -b`) passed with zero errors, ESLint (`eslint .`) clean with zero warnings/errors, production Vite build generated clean bundle.
- Security dependency audit:
  - `npm.cmd audit`: 0 vulnerabilities.
  - `.\.venv\Scripts\python.exe -m pip_audit`: 0 known vulnerabilities.
- Residual security risks and operational deployment controls documented in `docs/SECURITY.md` and `docs/ARCHITECTURE.md`.


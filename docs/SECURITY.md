# Security controls and residual risks

Implemented and tested controls:
- Argon2id hashing through argon2-cffi; opaque random server sessions stored as SHA-256 digests; HttpOnly/SameSite cookies, Secure in production; rotation on login; logout, reset and password-change invalidation; eight-hour session expiry.
- Exact-origin/custom-header checks plus session CSRF tokens for unsafe requests. Persistent account/IP auth rate limits and operation limits; no wildcard CORS.
- Server-side ownership on policies, originals, pages, conversations, both comparison operands, claims and exports. Same document uploaded by two users has independent resources. Tests explicitly use two users.
- Server-enforced actual-body limits including streamed bodies; bounded pages and render dimensions; PDF signature and parser validation; random temporary paths outside public directories; safe display filenames. Original bytes are stored as non-executable SQLite BLOBs. The browser receives raster pages and a transcript, with the original only as an authorized attachment.
- Parameterized SQL, foreign-key cascade removal, no shared global browser policy list. Failed upload cleanup and per-user duplicate handling. No semantic embedding cache in the browser API.
- React text escaping; no raw HTML/Markdown execution; static reviewed HTTPS external links only; text/plain exports cannot interpret user HTML.
- Independent claim verification with quote/page integrity and verified-only claim prose; no draft-prose promotion or fallback after failed verification. Browser comparisons omit unmatched financial differences.
- Restrictive CSP, frame denial, nosniff, no-referrer, no-store for sensitive responses, feature restrictions and production HSTS. Same-origin deployment and dev proxy. Provider requests remain server-side with explicit timeouts.
- No passwords, session tokens or document contents in localStorage/IndexedDB. Browser memory/query cache holds current task data; only non-sensitive hint preferences use persistent browser storage. Cache/selection clears on logout/expiry. Deleted resource caches are removed.
- Production rejects demo configuration/builds; API has no demo authentication switch. External model questions are off until explicitly enabled. Provider configuration is disclosed in the privacy UI.

Limits that passing checks do not remove:
- This is a single-worker prototype. Concurrency controls are in-process, and upload buffering/auth hashing can still consume resources under load. Deploy behind authenticated infrastructure or a properly configured proxy with global rate/body/connection quotas. Storage is capped at 50 policies per account, not an organization-wide disk budget. There is no MFA, email verification or production reset delivery yet.
- PDF parsing runs in-process using PyMuPDF. There is no antivirus or container/process sandbox for hostile parser inputs. Keep the parser patched, restrict deployment exposure, and isolate parsing before accepting untrusted internet-scale workloads. OCR is not provided.
- The application does not encrypt or redact stored records. Use OS volume encryption and filesystem ACLs, restricted service accounts and documented backup retention. Logical deletion cascades through the active database; journals, snapshots and backups can retain bytes. SQLite secure_delete helps but is not a secure-erasure guarantee.
- Upload ingestion metadata and ownership mapping span two SQLite transactions; a process crash between them can leave an inaccessible orphan metadata row (no original). Maintenance can reconcile such rows. No browser route can list or retrieve them without ownership.
- Model verification reduces some errors but is not an insurer decision or a correctness guarantee. Retrieval can miss material text; flattening tables can lose meaning; both models can make mistakes. Prompt injection is treated as untrusted data, not authority, but no absolute model immunity is claimed. No actions are authorized by model text.
- Questions enabled with Ollama still send relevant text to OpenRouter for independent verification. Gemini/auto additionally sends text to Google. Operator must assess provider retention, privacy and consent before enabling external processing; there is no local-only or compliance certification claim.
- Contextual follow-ups do not yet populate the verifier's structured user-facts map, and complex conditional questions can remain unresolved. The UI preserves uncertainty.
- Claim checklist suggestions are generic preparation aids. Required documents and deadlines are not extracted; no claim attachments or insurer submission exist.
- The reviewed US country guide is intentionally narrow and needs ongoing review. Other countries are unsupported.
- CSP is applied to the production FastAPI-served build. Vite development intentionally uses development tooling and is bound to loopback. No internet deployment, HTTPS termination test or live provider smoke test was performed.

Dependency audit results, secret scan scope, browser coverage and known limitations are recorded in CHECKPOINTS.md. An empty advisory report is not a claim of zero vulnerabilities.

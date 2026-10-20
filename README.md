# PolicyIQ

A focused health-insurance document workspace, with a React frontend and a thin FastAPI boundary around the existing Python services.

## Run locally (PowerShell)

From the repository root, one-time setup:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-web.lock.txt
cd frontend
npm.cmd ci
cd ..
```

Terminal 1, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Terminal 2:

```powershell
cd frontend
npm.cmd run dev
```

Open **http://127.0.0.1:5173** and create a local account (password: at least 12 characters). Use the same hostname consistently. `npm.cmd` avoids Windows PowerShell execution-policy restrictions. Node 22.12+ and Python 3.12 are supported by the checked environment.

For an explicit fictional demonstration instead of the real API:

```powershell
cd frontend
npm.cmd run dev:demo
```

Choose **Explore sample policies**. Demo data lives only in memory, uploads are unavailable, authentication is simulated, and no model is called. Production builds refuse demo mode and exclude its adapter/fixtures.

## Real behavior and current limits

Real: signup/login/expiry/logout/password change; owned policy PDFs and extracted passages; duplicate handling; search/list/open/archive/restore/delete; original download and page viewer; persisted conversations when providers are enabled; manual claim drafts and text exports; evidence comparison; hint preferences; account settings.

Questions reuse the existing answer generator and independent verifier. They are **disabled by default**. Set `POLICYIQ_ENABLE_QUESTIONS=true` and configure both the chosen generator and `OPENROUTER_API_KEY` server-side. Ollama generates locally but verification still sends relevant passages to OpenRouter. Gemini/auto also sends relevant passages and questions to Google. Enabling a provider is an explicit operator decision; the privacy screen reflects configuration. No live-provider test was performed without credentials.

Not implemented: OCR, automatic financial summaries, policy-derived claim obligations/deadlines, claim-document attachments, insurer submission, email verification, production password-reset email delivery, automatic redaction, application-level encryption at rest. Real claim preparation is an honest manual organizer, with recommended items explicitly distinguished from policy requirements. These gaps never silently use demo data.

Country guidance is a small curated US starting guide, with official links and review metadata. Bangladesh, UK and other countries have an unsupported state. Guidance does not determine eligibility or savings.

## Configuration and data

See [.env.example](.env.example). Copy values into server environment variables, or copy the example to `.env` in the root. Never put provider credentials in `VITE_*` variables.

The default data location is `~/.policyiq/policyiq.db`, outside public/frontend source. Set `POLICYIQ_DATA_DIR` to change it. Original PDF bytes, metadata, passages, sessions, conversations and claim drafts persist in SQLite. Browser tests use their own database. No browser document storage or session localStorage is used.

Development password reset (local operator only):

```powershell
.\.venv\Scripts\python.exe -m api.reset_link account@example.test
```

This prints a one-time link valid for 15 minutes. It does not send email and is disabled in production. The public forgot-password endpoint never exposes a token. Reset tokens use the URL fragment, and the UI removes the fragment after success. Do not share or log generated links.

## Same-origin production build

```powershell
cd frontend
npm.cmd run build
cd ..
$env:POLICYIQ_ENV='production'
$env:POLICYIQ_ORIGIN='https://your-policyiq-domain.example'
.\.venv\Scripts\python.exe -m uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Place a trusted HTTPS reverse proxy in front of the API. FastAPI serves the built SPA and handles direct frontend routes; `/api` remains the backend. Enforce body-size, connection and request limits at the proxy too. Use **one worker** for this prototype's in-process concurrency limits. Set filesystem ACLs, backups, retention and patching for the deployment. Production requires an explicit HTTPS origin; reset delivery remains unavailable until integrated. No deployment has been performed.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip_audit
cd frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
npm.cmd audit
```

Install the browser once with `npm.cmd exec playwright install chromium`. See [checkpoint results](docs/CHECKPOINTS.md), [API and architecture](docs/ARCHITECTURE.md), and [security controls and remaining risks](docs/SECURITY.md). Automated answer tests use controlled mocks, not live providers. Playwright screenshots are written under `frontend/test-results/`.

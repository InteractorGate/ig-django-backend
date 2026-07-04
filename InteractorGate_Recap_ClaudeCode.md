# InteractorGate — Recap for Claude Code

> Django REST backend for a desktop **AAC (Augmentative and Alternative Communication)** application for people with motor disabilities.
> Eye tracking via CNN + contextual text prediction via RNN.
> This document is the full project context and the protocol to **validate real progress by evidence**, not by summary.

---

## How to use this document

1. Read the context and the stack.
2. Run the **Validation protocol** (below) to determine which phase we are actually in.
3. For each phase, **do not mark it complete until you demonstrate it with the real output of a command or endpoint**. If something fails or is missing, say so explicitly.
4. Once the state is validated, continue from the first incomplete phase.

---

## Status summary (as of 2026-06-21)

| Phase | Title | Status |
|---|---|---|
| 1 | Environment & scaffold | ✅ Complete |
| 2 | Core API (Identity & Auth) | ✅ Complete |
| 3 | Prediction pipeline | ✅ Complete |
| 4 | Interaction logs (Cosmos DB) | ✅ Complete |
| 5 | Real AI model integration | ⚠️ In progress — RNN text prediction real (PyTorch LSTM); CNN eye-tracking still stubbed (OE3-I2) |
| 6 | Security hardening & Azure integration | ✅ Complete |
| 7 | CI/CD & deployment | ✅ Complete — live on Azure |
| 8 | Testing & QA | ⚠️ Pending — test scaffolding only, no real test cases |

**Backend (OE3-I1) is functional and deployed end-to-end:** auth + predictions on Azure SQL, logs on Cosmos DB, secrets in Key Vault, CI/CD to App Service. Remaining work is replacing the AI stubs with trained CNN/RNN models (OE3-I2) and the QA suite (OE4).

Live URL: `https://ig-backend-tesis.azurewebsites.net`

---

## Project context

Thesis application (timeline April–June 2026). The backend orchestrates the core logic and exposes endpoints over HTTPS/TLS 1.3 to a Flutter frontend (separate repo). Two AI models: CNN for eye tracking (OpenCV + TensorFlow) and RNN for contextual text/phrase prediction (PyTorch + TensorFlow). Scrum methodology.

Repo: \`https://github.com/InteractorGate/ig-django-backend\`
Working branch: \`develop\` → merge to \`main\` via PR when closing each phase.

---

## Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.1 + Django REST Framework 3.15.2 |
| Auth | djangorestframework-simplejwt (JWT) |
| Relational DB | Azure SQL Database (via \`mssql-django\` + \`pyodbc\`, ODBC Driver 18) |
| Document DB | Azure Cosmos DB (MongoDB API) via PyMongo |
| AI — Eye tracking | OpenCV + TensorFlow (CNN) |
| AI — Text prediction | PyTorch + TensorFlow (RNN) |
| Secrets | Azure Key Vault |
| AI training | Azure AI Studio |
| Frontend (separate repo) | Flutter desktop |
| Dev environment | Windows + PowerShell + venv |

Settings module: \`config.settings.local\` (dev) / \`config.settings.base\` (prod base).
\`DJANGO_SETTINGS_MODULE=config.settings.local\`

Expected structure:
\`\`\`
ig-django-backend/
├── config/
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py        → Azure SQL (mssql engine) + Cosmos DB
│   │   └── local.py       → dev overrides + logging
│   ├── mongo.py           → PyMongo singleton client (Cosmos DB)
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── users/                 → custom User model + JWT auth
├── predictions/           → CNN/RNN orchestration (Azure SQL, ORM)
├── interaction_logs/      → log writes (Cosmos DB, no ORM)
├── ai_modules/            → CNN/RNN stubs + orchestrator
├── .env                   → credentials (gitignored)
├── requirements.txt
└── manage.py
\`\`\`

---

## Validation protocol (run first)

Before continuing with any phase, determine the real state with evidence. Activate the \`venv\` and run:

\`\`\`powershell
# A. Migration integrity and Azure SQL connection
python manage.py makemigrations --check --dry-run
python manage.py migrate

# B. Server starts with no import/URL errors
python manage.py runserver
\`\`\`

With the server up, test the real endpoints for each phase (next section). **A phase is only complete if its endpoints respond as expected**, not just if the files exist.

Cosmos DB rule: confirm the document was actually written (Azure portal, \`mongosh\`, or Compass) and that \`interaction_logs\` has **no** Django models or migrations.

---

## Phase 1 — Environment & scaffold ✅

**Status:** Complete. `config/settings/{base,local,production}.py` split in place, `config/mongo.py` PyMongo singleton, custom `users.User`, all apps registered, `.env`/`.env.example`/`.gitignore` present, `mssql` engine on ODBC Driver 18 (container) / 17 (local). `migrate` applies cleanly against Azure SQL and `runserver` starts without errors.

**Objective:** A runnable Django project connected to Azure SQL and Cosmos DB, with secrets externalized.

### Requirements
- \`venv\` with dependencies pinned in \`requirements.txt\`
- Split settings: \`config/settings/base.py\` + \`local.py\`
- \`config/mongo.py\` — PyMongo singleton exposing \`interaction_logs\` and \`training_history\` collections
- Custom user model (\`users.User\` extending \`AbstractUser\`) declared via \`AUTH_USER_MODEL\`
- Apps created: \`users\`, \`predictions\`, \`interaction_logs\`
- \`.env\` (gitignored) with Azure SQL + Cosmos DB credentials and JWT lifetimes
- \`.env.example\` committed as a template
- \`.gitignore\` excluding \`.env\`, \`venv/\`, \`__pycache__/\`
- DB engine = \`mssql\` with ODBC Driver 18 for SQL Server
- \`python manage.py migrate\` runs successfully against Azure SQL

### Dependencies
\`\`\`
Django==5.1
djangorestframework==3.15.2
djangorestframework-simplejwt
django-environ
django-cors-headers
mssql-django
pyodbc
pymongo
gunicorn
\`\`\`

### Closing evidence
\`migrate\` applies with no errors against Azure SQL and \`runserver\` starts clean.

---

## Phase 2 — Core API (Identity & Auth) ✅

**Status:** Complete. `users` app implements register/login/logout/me with JWT (simplejwt), token blacklist enabled, admin registration, and routes wired in `config/urls.py`. Verified end-to-end against Azure SQL (live deployment returns 2xx for auth flow; `/me/` returns 401 without a token).

**Objective:** Working JWT authentication and user management.

### Requirements
- \`users/serializers.py\`
  - \`UserRegisterSerializer\` — username, email, password, confirmation, validation
  - \`UserProfileSerializer\` — username, email, first_name, last_name
- \`users/views.py\`
  - \`RegisterView\` — \`POST /api/users/register/\` (public)
  - \`LoginView\` — token pair issuance (extends \`TokenObtainPairView\`)
  - \`LogoutView\` — \`POST /api/users/logout/\` (blacklists refresh token)
  - \`UserProfileView\` — \`GET\` + \`PUT /api/users/me/\` (authenticated)
- \`users/urls.py\` — route endpoints
- \`users/admin.py\` — register \`User\` in the admin
- \`config/urls.py\` — include routers + simplejwt refresh endpoint
- Token blacklist app enabled
- Superuser created via \`createsuperuser\`

### Endpoints
| Method | Path | Auth |
|---|---|---|
| POST | \`/api/users/register/\` | Public |
| POST | \`/api/users/login/\` | Public |
| POST | \`/api/token/refresh/\` | Public |
| POST | \`/api/users/logout/\` | JWT |
| GET/PUT | \`/api/users/me/\` | JWT |

### Closing evidence
Register creates a user in Azure SQL; login returns \`access\` + \`refresh\`; \`/me/\` responds with the token and returns **401** without it; logout invalidates the refresh token.

\`\`\`powershell
curl -X POST http://localhost:8000/api/users/register/ -H "Content-Type: application/json" -d "{\"username\":\"test\",\"email\":\"t@t.com\",\"password\":\"Testpass123\",\"password2\":\"Testpass123\"}"
curl -X POST http://localhost:8000/api/users/login/ -H "Content-Type: application/json" -d "{\"username\":\"test\",\"password\":\"Testpass123\"}"
\`\`\`

---

## Phase 3 — Prediction pipeline ✅

**Status:** Complete. `PredictionRequest` + `PredictionResult` models migrated to Azure SQL (migration 0001), serializers and views in place, `POST /api/predictions/` routes through `ai_modules/orchestrator.py` and `GET /api/predictions/history/` lists results. AI logic is intentionally stubbed at this phase (see Phase 5).

**Objective:** Endpoint that receives gaze/text input, routes it to the correct model, and returns a prediction. AI logic stays stubbed.

### Requirements
- \`predictions/models.py\`
  - \`PredictionRequest\` — user FK, \`input_type\` (gaze/text), \`raw_input\` (JSON), \`session_id\` (UUID), \`created_at\`
  - \`PredictionResult\` — FK to \`PredictionRequest\`, \`model_used\` (CNN/RNN), \`output_text\`, \`confidence_score\` (float), \`response_time_ms\` (int), \`created_at\`
- \`predictions/serializers.py\` — \`PredictionRequestSerializer\`, \`PredictionResultSerializer\`
- \`predictions/views.py\`
  - \`PredictionView\` — \`POST /api/predictions/\` (routes via orchestrator, returns text)
  - \`PredictionHistoryView\` — \`GET /api/predictions/history/\`
- \`predictions/urls.py\` — route endpoints
- \`ai_modules/\`
  - \`cnn_module.py\` — stub \`EyeTracker.predict(frame)\` → gaze coordinates
  - \`rnn_module.py\` — stub \`TextPredictor.predict(context)\` → suggested phrases
  - \`orchestrator.py\` — routes to CNN or RNN and returns a unified result
- Migrations generated and applied for \`predictions\` (Azure SQL)

### Endpoints
| Method | Path | Auth |
|---|---|---|
| POST | \`/api/predictions/\` | JWT |
| GET | \`/api/predictions/history/\` | JWT |

### Closing evidence
\`migrate\` created the \`PredictionRequest\` and \`PredictionResult\` tables; the POST returns text from the orchestrator (even if stubbed); history lists what was created.

---

## Phase 4 — Interaction logs (Cosmos DB) ✅

**Status:** Complete. `interaction_logs` is Cosmos-only via PyMongo (no Django model, no migrations). `POST /api/logs/` writes a document and `GET /api/logs/session/<id>/` retrieves it; verified writing to Cosmos DB (MongoDB API) on the live deployment.

**Objective:** Capture interaction telemetry to Cosmos DB for analysis and future retraining. No Django ORM.

### Requirements
- \`interaction_logs/serializers.py\` — validates the incoming JSON only (no Django model)
- \`interaction_logs/views.py\`
  - \`LogInteractionView\` — \`POST /api/logs/\` (writes to Cosmos DB via \`config/mongo.py\`)
    - Fields: \`user_id\`, \`session_id\`, \`event_type\`, \`gaze_x\`, \`gaze_y\`, \`selected_word\`, \`timestamp\`
  - \`SessionLogsView\` — \`GET /api/logs/session/<session_id>/\`
- \`interaction_logs/urls.py\` — route endpoints
- **Constraint:** no Django models, no migrations — Cosmos DB only via PyMongo

### Endpoints
| Method | Path | Auth |
|---|---|---|
| POST | \`/api/logs/\` | JWT |
| GET | \`/api/logs/session/<session_id>/\` | JWT |

### Closing evidence
The POST writes a real document to the \`interaction_logs\` collection in Cosmos DB (verifiable in portal/Compass); the GET by \`session_id\` retrieves it; the app has **no** migrations or Django models.

---

## Phase 5 — Real AI model integration ⚠️

**Status:** In progress (OE3-I2).

- **RNN text prediction — done (real).** `ai_modules/rnn/` holds a real PyTorch word-level **LSTM** language model trained on a curated Spanish AAC corpus. `TextPredictor` (re-exported by `ai_modules/rnn_module.py`) loads the trained artifact `ai_modules/rnn/artifacts/phrase_lstm.pt` **once** and returns ranked phrase suggestions with a real softmax `confidence_score`; torch is imported lazily so startup and the gaze path pay no cost. Training via `python -m ai_modules.rnn.train` writes the artifact + `metrics.json` and records a document to the Cosmos DB `training_history` collection. Initial benchmark: train perplexity 2.72 / top-3 79.9%, val top-3 41.8% on a 103-sentence corpus (see `ai_modules/rnn/README.md`).
- **CNN eye-tracking — still stubbed.** `ai_modules/cnn_module.EyeTracker` returns random gaze data; no trained `.h5`/`.keras` artifact yet. This is the remaining Phase 5 work (see recommended architecture below).

**Objective:** Replace stubs with trained CNN and RNN models.

### Requirements
- CNN: OpenCV frame capture → gaze detection → coordinates, integrated with TensorFlow
- RNN: contextual phrase prediction via PyTorch → ranked suggestions
- Model artifacts loaded once and reused across requests
- Inference kept out of the blocking path where feasible
- \`confidence_score\` and \`response_time_ms\` recorded in \`PredictionResult\`
- Training history written to the \`training_history\` collection in Cosmos DB
- Initial accuracy benchmarks documented (suggestion accuracy target and gaze error margin)

---

## Phase 6 — Security hardening & Azure integration ✅

**Status:** Complete (branch `feat/phase6-hardening`). Throttling on auth endpoints, environment-driven CORS for the Flutter origin, and security headers added (commit `1a4bf55`). Azure Key Vault holds 7 secrets (JWT signing key, SQL + Mongo credentials) consumed via App Service Key Vault references + system-assigned managed identity; HTTPS enforced by App Service; refresh-token rotation + blacklist active.

**Objective:** Production-grade security, aligned with the C4 "Identity & Secrets Management" component.

### Requirements
- Azure Key Vault for secrets (JWT signing material, DB credentials, AES-256 keys)
- HTTPS/TLS 1.3 enforced for all traffic
- Security headers and strict CORS for the Flutter frontend origin
- Sensitive-data handling policy applied to interaction logs
- Refresh-token rotation + blacklist confirmed in production
- Throttling on auth endpoints

---

## Phase 7 — CI/CD & deployment ✅

**Status:** Complete. GitHub Actions `deploy.yml` builds the image, pushes to ACR (`igtesisacr.azurecr.io`), and deploys to Azure App Service for Containers (`ig-backend-tesis`, plan `ig-asp-tesis` B1) on push to `main`; `codeql.yml` runs security scanning. `config/settings/production.py` with `DEBUG=False` and hardened hosts is in place. App is live at `https://ig-backend-tesis.azurewebsites.net`. Note: CI/CD auth is credentials-based (publish profile + ACR creds), not OIDC, because the `upc.edu.pe` tenant blocks app registrations for the student account.

**Objective:** Automated, repeatable deployment to Azure.

### Requirements
- GitHub Actions pipeline: lint → test → build → deploy
- Django deployed to Azure App Service (or container)
- \`production.py\` module with \`DEBUG=False\` and hardened hosts
- Static files collected and served
- Environment variables / Key Vault references injected into the host
- Post-deploy smoke tests
- **(Optional) IaC:** if required by advisor, scope Terraform to the compute + Key Vault layer; reference Azure SQL and Cosmos DB by connection string rather than managing them in state

---

## Phase 8 — Testing & QA ⚠️

**Status:** Pending (OE4). Only Django's default empty `tests.py` scaffolding exists in `users`, `predictions`, and `interaction_logs` — no real unit/integration test cases yet. Usability testing with target users, accessibility validation, performance/latency tests, and the QA report against the success indicators all remain to be done.

**Objective:** Validate functionality, accessibility, and performance (charter OE4).

### Requirements
- Unit tests for serializers and model logic
- Integration tests per endpoint (auth, predictions, logs)
- Usability testing with target users (people with motor disabilities)
- Accessibility validation of the end-to-end flow
- Performance tests on the prediction path (latency, throughput)
- QA report against the success indicators

---

## Cross-cutting conventions

- Branch on \`develop\`; merge to \`main\` via PR when closing each phase
- Incremental commits — never lose more than one session of work
- Secrets only in \`.env\` (gitignored) and Azure Key Vault — never committed
- All endpoints except \`register\`, \`login\`, and \`token/refresh\` require a JWT Bearer token
- \`interaction_logs\` is Cosmos-only; \`users\` and \`predictions\` use the ORM on Azure SQL

---

## Final instruction for Claude Code

\`\`\`
Validate the real project state with the Validation protocol before 
claiming any phase is complete. For each phase:
1. Run makemigrations --check --dry-run and migrate.
2. Start the server and test each endpoint of the phase with curl.
3. For Phase 4, confirm the document reached Cosmos DB and that 
   interaction_logs has NO migrations or Django models.
Show me the command and its real output in each case. If something fails 
or is missing, say so explicitly instead of marking it done. Then continue 
from the first incomplete phase and commit when closing each one.
\`\`\`

# SPEC — Job Application Assistant ("hirable")

A self-hosted, multi-user web app that helps people **write, tailor, and track** job applications:
upload a resume → parse it into a rich master profile → save job postings → chat with an agent that
enriches the profile and generates a **tailored, LaTeX-quality CV + cover letter** per job → edit the
source → export a professional PDF → track applications with automation and analytics.

This document is the implementation contract. It is paired with [`docs/good_resume.md`](docs/good_resume.md),
the rulebook the agent uses to write and critique resumes/cover letters.

---

## 1. Goals & non-goals

**Goals**
- Multi-tenant from day one; strict per-user data isolation.
- One-command self-host: `docker compose up`.
- Provider-agnostic LLM (OpenAI / Anthropic / Gemini / Ollama / vLLM / any OpenAI-compatible) via a
  single config block — **no hard-coded model or provider anywhere**.
- Professional, LaTeX-quality PDF output with a user-editable source.
- Agentic chat for profile enrichment and document generation, built on the
  [`agent_kit`](https://github.com/sharma-n/agent_kit) sidecar (which builds on
  [`llm_kit`](https://github.com/sharma-n/llm_kit)).

**Non-goals (initially)**
- Public cloud SaaS hardening / horizontal scale (local-first deployment is the target).
- Mobile apps.
- Cross-conversation fuzzy memory (episodic recall) — see §6.3 for the rationale.

---

## 2. Architecture overview

Three services + SQLite + a render toolchain, orchestrated by `docker compose`.

```
                 REST / SSE (session cookie)
[ Next.js frontend ] ───────────────────────────▶ [ FastAPI backend ]
   TS, editor UI                                    system of record
        ▲                                             │   ▲   │
        │  streamed AgentEvents                       │   │   │ HTTP/WS  (X-Internal-Secret)
        └─────────────────────────────────────────────┘   │   ▼
                                                           │  [ agent_kit sidecar ]
                          tool callbacks (X-Internal-Secret)   chat brain (uvicorn)
                                  ◀────────────────────────┘   internal network only
        │
        ├── SQLite (app DB)  +  file store (uploads, generated PDFs/sources)
        ├── llm_kit client (provider-agnostic; structured outputs)
        └── RenderCV + TinyTeX  +  LaTeX letter template  → PDF
```

- **Frontend (Next.js / React / TypeScript)** — the only host-published UI. Talks to the backend's
  **public** API over an authenticated session cookie. Streams agent events for chat.
- **Backend (FastAPI / Python)** — the **system of record** and the only component with DB access. It
  owns auth, the public API, an **internal** (shared-secret) API used by the sidecar's tools, the chat
  **proxy** to the sidecar, document rendering, the tracking scheduler, and analytics.
- **agent_kit sidecar (Python / uvicorn)** — the chat brain: streaming agent loop, working memory +
  session store, per-user `PermissionStore`, and our injected custom tools. **Bound to the internal
  docker network only — never published to the host.**

Bottom-up layering mirrors agent_kit's own philosophy: `config → db → services → api → frontend`, with
the sidecar as a peer reached only through the backend.

---

## 3. Repository layout

```
hirable/
├─ docker-compose.yml          # frontend + backend + agent; only frontend/backend published
├─ .env.example                # AGENT_INTERNAL_SECRET, ANTHROPIC_API_KEY (secrets only)
├─ config.yaml                 # single source of truth for LLM + agent + app config
├─ README.md                   # quickstart
├─ SPEC.md                     # this file
├─ CLAUDE.md                   # AI assistant context (architecture, gotchas, decisions)
├─ docs/
│  └─ good_resume.md           # resume/cover-letter rulebook (injected into agent prompts)
├─ frontend/                   # Next.js 16 (TypeScript)
│  └─ app/  (auth, admin, profile, jobs, chat, editor, tracker, analytics) + components/ + lib/api
├─ backend/                    # FastAPI (uv-managed, Python 3.13)
│  ├─ pyproject.toml
│  └─ app/
│     ├─ main.py               # app factory, router mounting, scheduler startup
│     ├─ config.py             # loads config.yaml (${VAR:-default} expansion) + env
│     ├─ db/                   # engine, models, migrations, session
│     ├─ auth/                 # password hashing, sessions, dependencies, admin guard
│     ├─ api/                  # PUBLIC routers (session-scoped): profile, jobs, documents,
│     │                        #   applications, analytics, chat proxy, admin
│     ├─ internal/             # INTERNAL routers (shared-secret): the agent tool callbacks
│     ├─ llm/                  # llm_kit client factory + Pydantic schemas (Profile, Job, RenderCV)
│     ├─ parsing/              # docling extraction + structured profile/job extraction
│     ├─ rendercv/             # RenderCV YAML build + compile
│     ├─ letters/              # cover-letter LaTeX template + compile
│     ├─ tracking/             # APScheduler jobs (stale/rejected), stage transitions
│     └─ analytics/            # metric computations
└─ agent/                      # agent_kit bootstrap (Python 3.13, uv-managed)
   ├─ bootstrap.py             # builds AgentService, enforces X-Internal-Secret, /health
   └─ tools/                   # custom Tool definitions (call backend internal API)
   # config.yaml resolved at runtime: Docker mount (/app/config.yaml) or repo root
```

---

## 4. Configuration

A **single `config.yaml`** is mounted into both backend and agent so the LLM is configured once.

```yaml
# ---- LLM (consumed by agent_kit sidecar AND backend parsing/generation) ----
llm_kit:
  llm:
    base_url: https://api.anthropic.com   # change for other providers
    model: claude-haiku-4-5-20251001
    api_key_env: ANTHROPIC_API_KEY        # name of the env var holding the key
    message_format: anthropic             # openai | anthropic | gemini
    chat_completions_path: /v1/messages   # required for anthropic; omit for openai
    max_tokens: 4096

# ---- agent_kit (exact schema — do not add unknown top-level keys here) ----
agent:
  max_iterations: 6
  per_tool_timeout_s: 30.0               # field name is per_tool_timeout_s, not per_turn_budget_s
  system_prompt: |
    You are a job application assistant called hirable.
    # good_resume.md rulebook appended here at bootstrap time (M4)
memory:
  working:                               # buffer config is nested under working:
    buffer_turns: 12
    buffer_token_budget: 4000
    idle_finalize_s: 900
    ttl_s: 3600
    sweep_interval_s: 60
  episodic:
    enabled: false                       # OFF — see §6.3
  factual:
    extraction_enabled: false            # OFF — enrichments via record_clarification tool
context:
  max_input_tokens: 128000
  output_reserve_tokens: 4096
  safety_margin: 1024
stores:
  session_backend: memory
  profile_backend: memory
  vector_backend: memory
  permission_backend: memory
tools:
  default_allowed: []                    # populated in M4 with custom tool names
mcp:
  servers: []
telemetry:
  enabled: false

# ---- app (consumed by backend only — agent_kit strips this block) ----
app:
  agent_base_url: ${AGENT_BASE_URL:-http://agent:8000}  # override locally
  internal_base_url: http://backend:8000
  selectable_models:
    - { display_name: "Haiku",  model_id: "claude-haiku-4-5-20251001" }
    - { display_name: "Sonnet", model_id: "claude-sonnet-4-6" }
    - { display_name: "Opus",   model_id: "claude-opus-4-8" }
  auth:
    session_ttl_days: 14                 # httpOnly cookie TTL
    cookie_secure: false                 # set to true behind HTTPS in prod (${COOKIE_SECURE:-false})
  tracking:
    stale_after_days: 15                 # idle → Stale
    auto_reject_after_days: 30           # idle → Rejected (ghosted)
```

`.env.example` — **secrets only; all LLM/agent config lives in `config.yaml`**:
```
AGENT_INTERNAL_SECRET=change-me-to-a-long-random-string
ANTHROPIC_API_KEY=sk-ant-...
```

**Provider portability** (from llm_kit) — switch the whole app by editing the `llm:` block:
- *OpenAI-compatible (OpenAI, vLLM, Ollama, LM Studio, Together):* `message_format: openai`,
  `base_url` to the endpoint (e.g. `http://host.docker.internal:11434` for local Ollama).
- *Anthropic:* `message_format: anthropic`, `chat_completions_path: /v1/messages`.
- *Gemini:* `message_format: gemini`, model lives in `chat_completions_path`.

---

## 5. Security model (multi-tenant isolation)

Three trust boundaries, two credentials:

1. **Frontend ↔ backend public API** — authenticated **session** via httpOnly, SameSite cookie. Every
   public query is scoped to the session's `user_id`; cross-user access returns 404/403.
2. **Backend ↔ sidecar (chat proxy)** and **sidecar tools ↔ backend internal API** — a **shared
   secret** (`AGENT_INTERNAL_SECRET`) sent as `X-Internal-Secret`. Internal endpoints reject any
   request without it.
3. **Network** — only `frontend` and `backend` publish ports. The **sidecar is on the docker internal
   network only**, so neither it nor the internal API is reachable from the host.

**Trusted `user_id` flow:** the backend derives `user_id` from the authenticated session and injects
it when starting/continuing a conversation with the sidecar. agent_kit passes that `user_id` to each
tool handler. Tool handlers call the backend internal API with `X-Internal-Secret` **and** that
`user_id`; the internal endpoints scope strictly to it. Consequence: **a plain HTTP request cannot read
another user's data** — there is no host-reachable, unauthenticated path to user data, and the
`user_id` is never client-supplied to a privileged endpoint.

Passwords hashed with **argon2**. Sessions are opaque random tokens with expiry, revocable (admin
delete / password reset invalidates them).

---

## 6. Agent integration (agent_kit)

### 6.1 Bootstrap (native tools, no MCP)
`agent/bootstrap.py` builds the agent_kit app by loading the shared `config.yaml`, stripping the
`app:` block (agent_kit rejects unknown top-level keys), and calling:

```python
from agent_kit.config.loader import load_dict
from agent_kit.config.schema import AgentKitConfig
from agent_kit.service import AgentService
from agent_kit.serving.app import create_app

service = AgentService.build(load_dict(AgentKitConfig, agent_raw))
app = create_app(service)
# then register custom tools on service (M4)
```

Each custom tool is a native agent_kit `Tool` (exact API to be confirmed in M4):
```python
Tool(
    definition=ToolDefinition(name=..., description=..., parameters={...JSON schema...}),
    handler=async (user_id: str, args: dict) -> str,   # calls backend internal API w/ shared secret
)
```

Tools are permission-gated via `service.stores.permissions.grant(user_id, tool_names)`.
`tools.default_allowed` in `config.yaml` is the global fallback. Tool errors become observations,
never exceptions — consistent with agent_kit. The agent's **system prompt embeds
`docs/good_resume.md`** so all drafting follows the rulebook.

### 6.2 Tool catalogue (all `user_id`-scoped via the internal API)
| Tool | Purpose |
|---|---|
| `get_profile` | Read the user's canonical master profile |
| `update_profile_section` / `add_profile_item` | Edit/append profile sections |
| `record_clarification(key, value)` | Persist a clarifying-question answer into the profile (enrichment) |
| `list_jobs` / `get_job(job_id)` | Read the user's saved jobs |
| `draft_cv(job_id)` | Produce RenderCV YAML for a job (LLM structured output, §8.3) |
| `draft_cover_letter(job_id)` | Produce cover-letter source for a job |
| `compile_document(document_id)` | Compile a stored document to PDF, return its URL |
| `save_document(...)` | Persist a CV/cover-letter draft (source + new version) |
| `list_application_status` | (optional) Let the agent answer tracking questions |

### 6.3 Memory configuration — and why episodic is OFF
- **Working memory + session store: ON** — needed for multi-turn coherence within a chat.
- **Episodic (vector) recall: OFF.** The source of truth (profile, jobs, documents) lives in the app
  DB and is fetched **deterministically via tools**, so the agent never needs fuzzy vector recall to
  "remember" facts. Episodic only adds marginal cross-conversation fuzzy recall while **forcing an
  embedding model into the install** (hurting the one-command setup goal). It is a config flag
  (`memory.episodic.enabled`) we can flip on later if we want "you mentioned X on another job" recall.
- **agent_kit factual auto-extraction: OFF.** Enrichments are persisted **explicitly** via
  `record_clarification` into the canonical profile, keeping a single source of truth (no duplicate
  fact store to reconcile).

### 6.4 Model selection & mid-conversation switching
- The provider/model is set once in `config.yaml` (`llm_kit.llm`).
- `app.selectable_models` is surfaced to the chat UI as a picker. Choosing a model calls the backend,
  which calls the sidecar's `AgentService.set_conversation_model(model_id)` for that conversation.
- Models sharing the configured endpoint switch natively. For **true cross-provider** switching, the
  admin can point `llm_kit.llm` at an **OpenAI-compatible gateway (e.g. LiteLLM)** that fronts multiple
  providers — documented as optional, not required.

### 6.5 Chat transport
Frontend opens an SSE/WebSocket to the backend chat proxy → backend attaches `user_id` + secret and
relays to the sidecar's WS/SSE → streams typed `AgentEvent` frames
(`TextDelta` / `ToolCallStarted` / `ToolResult` / `TurnComplete`) back to the frontend. The frontend
never contacts the sidecar directly. Conversation end (disconnect/idle) is signalled to the sidecar to
finalize working memory.

---

## 7. Data model (SQLite, owned by backend)

| Table | Key columns |
|---|---|
| `users` | id, email (unique), password_hash, role (`admin`/`user`), is_active, created_at |
| `sessions` | token_hash (pk — SHA-256 of the opaque cookie token), user_id → users, expires_at |
| `resumes` | id, user_id, filename, format (`pdf`/`docx`/`tex`), raw_text, uploaded_at |
| `profiles` | id, user_id, version, data (JSON master profile), updated_at |
| `jobs` | id, user_id, source_url, raw_text, parsed (JSON), shortlist_status, created_at |
| `documents` | id, user_id, job_id → jobs, type (`cv`/`cover_letter`), source_format, source_text, pdf_path, version, is_finalized, created_at |
| `applications` | id, user_id, job_id → jobs, stage, submitted_at, last_activity_at, next_action, auto_stale_at, notes |
| `application_documents` | application_id → applications, document_id → documents (snapshot of finalized CV + cover letter used) |
| `application_events` | id, application_id, from_stage, to_stage, at, note |

**Master profile JSON shape** (`profiles.data`): `contact`, `summary`, `skills[]`,
`experience[]{company,title,start,end,location,bullets[],tech[]}`, `projects[]{name,link,bullets[],tech[]}`,
`education[]`, `extras[]` (patents/talks/OSS/interests), `enrichment[]` (clarification key/values).

All user-owned tables carry `user_id`; **deleting a user cascades** to all of the above. Generated PDFs
and uploads live in a per-user directory in the file store; deletion removes them too.

---

## 8. Pipelines

### 8.1 Resume parsing (`POST /api/resumes`)
1. Accept `.pdf` / `.docx` / `.tex`. Extract text with **docling** (pdf/docx → structured
   text/markdown); `.tex` → stripped to plain text.
2. `llm.invoke(messages, response_model=ProfileModel)` → validated structured profile.
3. Store as `profiles` version 1. The user edits any field in the profile editor (re-save bumps
   version). This profile is the **verbose "master"** referenced by `good_resume.md` §8.

### 8.2 Job ingest (`POST /api/jobs`)
1. If a URL is given: fetch and extract main content with **trafilatura** (readability fallback). If
   blocked/empty (many job boards block bots), return a `needs_paste` signal so the UI prompts the
   user to paste the text.
2. `llm.invoke(messages, response_model=JobModel)` → `{company, title, location, must_have[],
   nice_to_have[], keywords[], why_opened_guess, seniority, company_type}`.
3. Store in `jobs`; fields are editable.

### 8.3 CV generation (`draft_cv` tool / `POST /api/documents/cv`)
- Build **RenderCV YAML** via `llm.invoke(..., response_model=RenderCVModel)` — a Pydantic mirror of
  RenderCV's schema so output is guaranteed parsable — from the master profile + job + `good_resume.md`
  rules (level-appropriate ordering, impact bullets, JD keyword mirroring, no self-ratings, ≤2 pages).
- `rendercv render <yaml>` → PDF (+ `.tex`). Store source + `pdf_path` as a `documents` row.
- User edits the YAML in-app → re-compile → live PDF preview. Each save is a new version.

### 8.4 Cover letter (`draft_cover_letter` tool / `POST /api/documents/cover_letter`)
- Draft source (company-first, JD-tied, concise per `good_resume.md` §12), then compile with a minimal
  **LaTeX letter template** via the same bundled TinyTeX for visual consistency with the CV. Editable
  source + preview + versioning.

### 8.5 Clarifying-question loop
The agent compares the profile against `good_resume.md` to find gaps (missing numbers/impact, thin
projects, unclear target role/level, JD-relevant skills not evidenced) and asks targeted questions;
answers persist via `record_clarification`, enriching the master profile for all future documents.

---

## 9. Application tracking & automation

- **Stages:** `Draft → Applied → Recruiter Screen → Technical → Onsite → Offer → Accepted / Declined`,
  plus terminal `Rejected` and automatic `Stale`.
- **On submission:** snapshot the **finalized CV + cover letter** (source + compiled PDF) into
  `application_documents` so the exact materials used are preserved for future reference, even if the
  user later regenerates documents.
- **Scheduler (APScheduler in the backend):**
  - Mark `Stale` after `tracking.stale_after_days` of no `last_activity_at` change in an active stage.
  - Optionally mark `Rejected` (ghosted) after `tracking.auto_reject_after_days`.
  - Surface `next_action` reminders.
- Every stage change writes an `application_events` row (for the funnel).
- **Triage views:** kanban by stage; sortable/filterable table (by staleness, last activity, company);
  per-application detail listing the exact submitted PDFs.

---

## 10. Analytics dashboard

Computed from `applications` + `application_events`:
- **Funnel** conversion per stage.
- **Response rate** — % of `Applied` that reached any later stage.
- **Median time-to-first-response.**
- **Applications over time.**
- **Status counts** — active / stale / rejected / offers.
- **Offer rate.**
- **Per-CV-version response rate** — which tailored CV performs best (joins `application_documents`).
- **Breakdowns** by company type / location.

---

## 11. API surface (representative)

**Public (`/api/*`, session-scoped)**
- `POST /api/auth/signup`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- `GET/PUT /api/profile`
- `POST /api/resumes` (upload+parse)
- `GET/POST /api/jobs`, `GET/PUT/DELETE /api/jobs/{id}`
- `GET/POST /api/documents`, `GET/PUT /api/documents/{id}`, `POST /api/documents/{id}/compile`,
  `GET /api/documents/{id}/pdf`
- `GET/POST /api/applications`, `PATCH /api/applications/{id}` (stage transition), `POST
  /api/applications/{id}/submit`
- `GET /api/analytics`
- `GET /api/chat/models`, chat stream endpoint (SSE/WS), `POST /api/chat/model` (switch)
- **Admin** (`role=admin`): `GET /api/admin/users`, `DELETE /api/admin/users/{id}`,
  `POST /api/admin/users/{id}/reset-password`, `POST /api/admin/users/{id}/disable`

**Internal (`/internal/*`, requires `X-Internal-Secret`, `user_id` in body/params)** — the tool
callbacks backing §6.2.

---

## 12. Roles & admin

- The **first registered account becomes `admin`**.
- Admin console: list users; **delete a user and cascade all their data + files**; reset a user's
  password; disable/enable an account. Deleting/disabling invalidates that user's sessions.

---

## 13. Milestones (each = deliverables + acceptance)

**M0 — Project skeleton & one-command setup** ✅
- Monorepo; `docker-compose.yml` (frontend, backend, agent on an internal network; only
  frontend+backend published); `.env.example`; single mounted `config.yaml`.
- `uv` backend (Python 3.13); agent_kit installed from git URL. SQLite engine + `create_all()`
  migration runner. Health endpoints on all three services.
- Agent bootstrap strips `app:` from config, builds `AgentService`, enforces `X-Internal-Secret`
  middleware; backend chat proxy relays WS messages to the sidecar with injected `user_id`.
- **Acceptance:** ✅ chat round-trip verified locally — message streams back through
  proxy → sidecar (real LLM) → frontend placeholder chat page.

**M1 — Auth, sessions, admin** ✅
- argon2 password hashing; httpOnly-cookie sessions (`hirable_session`, SameSite=Lax, SHA-256 hash
  stored in DB); signup/login/logout/me. First account auto-promoted to admin.
- Admin console (list/delete-cascade/reset-password/disable); all public routes scoped to the session
  user; unauthenticated WS connections rejected with close code 4401.
- Full UI rebuild: Tailwind v4 + shadcn base-nova, dark/light mode, app shell, redesigned chat.
- **Acceptance:** ✅ two users isolated; admin delete cascades + invalidates sessions; 17/17 tests
  green; TypeScript clean; middleware-free route protection via server-component `cookies()`.

**M2 — Resume upload → master profile**
- Upload pdf/docx/tex → docling/text extraction → `response_model=ProfileModel` → `profiles` v1;
  full profile editor UI (every section editable; save bumps version).
- **Acceptance:** sample pdf, docx, and tex each parse into a coherent, editable profile; edits persist.

**M3 — Jobs shortlist**
- Add job by URL (trafilatura) with **paste fallback**; `response_model=JobModel`; shortlist list +
  detail UI; editable parsed fields.
- **Acceptance:** a normal URL parses; a blocked URL cleanly falls back to paste; fields editable.

**M4 — Agent tools + clarifying-question loop**
- Implement the §6.2 custom tools calling the internal API (shared secret, user_id-scoped); grant
  defaults via `PermissionStore`; embed `good_resume.md` in the system prompt; chat UI streams
  `TextDelta/ToolCallStarted/ToolResult/TurnComplete`; model picker wired to `set_conversation_model`.
- Agent reads profile + jobs, asks gap-filling questions, writes enrichments via `record_clarification`.
- **Acceptance:** in chat, the agent enriches the profile (new items appear in DB/UI); switching model
  mid-chat works; user A's tools cannot touch user B's data; the sidecar/internal API reject calls
  without the secret.

**M5 — CV generation + source editor + PDF preview**
- `RenderCVModel` schema; `draft_cv` yields valid YAML; `rendercv render` → PDF + `.tex`; persist as
  `documents`; in-app YAML editor with live re-compile + PDF preview; versioning.
- **Acceptance:** generate a tailored CV for a job, edit the YAML, re-compile, preview updates; output
  passes a `good_resume.md` lint spot-check (single column, quantified bullets, ≤2 pages, no
  self-ratings).

**M6 — Cover letter generation + editor**
- `draft_cover_letter` (company-first, JD-tied); LaTeX letter template compile; editor + preview;
  versioning.
- **Acceptance:** generate/edit/compile a cover letter; PDF is professional and visually consistent
  with the CV.

**M7 — Application tracking + automation + finalized-doc history**
- `applications` + stage-transition UI (kanban + table); on submit, **snapshot** finalized CV + cover
  letter into `application_documents`; APScheduler stale/rejected automation; `next_action` reminders;
  per-application view lists exact submitted PDFs.
- **Acceptance:** create → advance → submit an application; finalized docs are snapshotted and viewable
  later; a time-travel unit test marks an idle application `Stale`.

**M8 — Analytics dashboard**
- Compute & render funnel, response rate, time-to-response, over-time, status counts, per-CV-version
  performance, and company-type/location breakdowns.
- **Acceptance:** dashboard reflects seeded data; metric math verified by unit tests.

**M9 — Polish, hardening, docs**
- Error/empty/loading states; pytest suites (parsing fixtures, internal-API auth, tool isolation,
  scheduler time-travel, analytics math); README quickstart; optional Langfuse tracing toggle; optional
  LiteLLM-gateway docs for cross-provider switching.
- **Acceptance:** `pytest` green; a fresh clone → `docker compose up` → the full §14 happy path works.

---

## 14. End-to-end verification

`docker compose up` brings up all three services; the agent passes health checks. Manual happy path:

1. Sign up (first user → **admin**).
2. Upload a resume → confirm the parsed **master profile**.
3. Add a job by URL; confirm the **paste fallback** path for a blocked URL.
4. Chat: run the clarifying-question loop; **switch models** mid-conversation.
5. Generate a **CV** → edit the YAML → compile → preview the PDF.
6. Generate a **cover letter** → edit → compile.
7. Create and **submit** an application → finalized CV + cover letter are **snapshotted**.
8. Advance stages → **analytics** update.
9. **Isolation checks:** a second user sees none of the first user's data; calls to the sidecar /
   internal API without `X-Internal-Secret` fail; the sidecar has no host-published port.
10. **Quality check:** spot-check a generated CV against the `docs/good_resume.md` lint rules.

---

## 15. Key dependencies

- **Backend:** FastAPI, uvicorn, SQLAlchemy (or SQLModel) + SQLite, argon2-cffi, `agent_kit`
  (brings `llm_kit`), docling, trafilatura, rendercv (+ bundled TinyTeX), APScheduler, pydantic.
- **Agent sidecar:** `agent_kit` (configured per §4/§6), our custom tools.
- **Frontend:** Next.js, React, TypeScript; a code editor component (e.g. Monaco/CodeMirror) for the
  YAML/letter source; a PDF viewer; charts for analytics.
- **LLM:** any provider/model via the `llm_kit.llm` block — no hard-coded model anywhere.

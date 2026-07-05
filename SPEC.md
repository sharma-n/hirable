# SPEC — Job Application Assistant ("hirable")

A self-hosted, multi-user web app that helps people **write, tailor, and track** job applications:
upload a resume → parse it into a rich master profile → save job postings → chat with an agent that
enriches the profile and generates a **tailored, publication-quality CV + cover letter** per job →
edit the source → export a professional PDF → track applications with automation and analytics.

This document is the implementation contract. It is paired with [`docs/good_resume.md`](docs/good_resume.md),
the rulebook the agent uses to write and critique resumes/cover letters.

---

## 1. Goals & non-goals

**Goals**
- Multi-tenant from day one; strict per-user data isolation.
- One-command self-host: `docker compose up`.
- Provider-agnostic LLM (OpenAI / Anthropic / Gemini / Ollama / vLLM / any OpenAI-compatible) via a
  single config block — **no hard-coded model or provider anywhere**.
- Professional, publication-quality PDF output (via RenderCV/Typst — not LaTeX, see §2) with a
  user-editable source.
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
        ├── SQLite (app DB)  +  file store (uploads only — see M5 note below)
        ├── llm_kit client (provider-agnostic; structured outputs)
        └── RenderCV (renders via Typst, not LaTeX/TinyTeX — see M5 note)  → PDF
```

**M5 correction to this diagram (RenderCV v2.8 renders via Typst, not LaTeX):**
RenderCV v2.8 typesets through **Typst** (a Rust-based typesetter shipped as a
prebuilt-binary Python wheel, `typst-py`), not LaTeX/TinyTeX — there is no `.tex`
output at all. This is lighter to provision than originally planned (no system
LaTeX toolchain, just two pure-wheel pip packages, `rendercv[full]`). Generated
CVs are also **DB-only** — only the RenderCV YAML source is persisted
(`documents.source_text`); PDFs are compiled on demand into a temp directory
and streamed back, never written to the file store, for privacy (the file
store still holds resume *uploads*, per M2). See `backend/app/rendercv/`.

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
│  └─ app/  (auth, admin, profile, jobs, editor, tracker, analytics) + components/ + lib/api
│     # No standalone chat page — the agent is embedded via components/agent-panel.tsx
│     # inside the profile and job-detail pages (see SPEC §6.0).
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
│     ├─ rendercv/             # RenderCV YAML build + compile — CV (tailor/build) and cover
│     │                        #   letter (letter.py) both live here; no separate letters/
│     │                        #   package was needed (M6 reuses this pipeline, see §8.4)
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

### 6.0 No standalone chat tab — two contextual agent panels

**Design pivot from the original spec (decided during M4 planning):** there is no general-purpose
"Chat" nav tab. Instead the agent appears embedded in a split-screen panel on the two pages where
a conversation is actually useful:

1. **Profile page** (`/profile`) — the agent gathers/enriches profile information per
   `docs/good_resume.md`, with no specific job in view. The right-hand pane shows the full profile
   updating live as the agent writes, with the section(s) it just touched briefly highlighted.
2. **Job detail page** (`/jobs/{id}`) — the agent already has the base profile *and* this job's
   parsed JD; it does gap analysis and asks clarifying questions specific to that role. (From M5
   onward this panel also gains an artifact pane — RenderCV YAML + PDF preview.)

Both panels are the same `AgentPanel` component, parameterized by a **conversation-id base**:
`profile` or `` job:{job_id} ``. The chat proxy (`backend/app/api/chat.py`) namespaces this by the
authenticated `user_id` before forwarding upstream (`{user_id}:{base}`), because agent_kit
conversations are globally keyed and user-owned — a bare id like `profile` would otherwise collide
across users. A client-side "new chat" button appends a generation suffix (`profile.2`) to start a
fresh thread without losing the stable id's resumability; the internal API strips both the
namespace prefix and the generation suffix before interpreting the conversation's mode.

### 6.1 Bootstrap (native tools, no MCP, no read tools)
`agent/bootstrap.py` builds the agent_kit app by loading the shared `config.yaml`, stripping the
`app:` block (agent_kit rejects unknown top-level keys), embedding `docs/good_resume.md` into the
static `agent.system_prompt`, and calling:

```python
from agent_kit.config.loader import load_dict
from agent_kit.config.schema import AgentKitConfig
from agent_kit.service import AgentService
from agent_kit.serving.app import create_app

service = AgentService.build(
    load_dict(AgentKitConfig, agent_raw),
    extra_tools=build_tools(internal_client),          # agent/tools/
    system_prompt_fn=build_system_prompt_fn(internal_client),  # agent/tools/context.py
)
app = create_app(service)
```

Each custom tool is a native agent_kit `Tool`:
```python
Tool(
    definition=ToolDefinition(name=..., description=..., parameters={...JSON schema...}),
    handler=async (user_id: str, args: dict) -> str,   # calls backend internal API w/ shared secret
)
```

**Per-turn dynamic context, not read tools.** agent_kit calls `system_prompt_fn(user_id,
conversation_id)` fresh on every turn and appends its return value to the system prompt as a
tier-0 (never-evicted) block. `build_system_prompt_fn` (in `agent/tools/context.py`) fetches this
from the backend's `POST /internal/context`, which returns the user's current profile JSON (and,
in job mode, the job's parsed JSON) plus mode-specific instructions. Because the agent's own writes
are reflected in the very next turn's context automatically, there is **no `get_profile` /
`list_jobs` / `get_job` read tool** — that would just be a redundant round trip. Tools are
**write-only**.

Tools are permission-gated via `service.stores.permissions.grant(user_id, tool_names)`;
`tools.default_allowed` in `config.yaml` is the global fallback and is what M4 uses (every user
gets the same three write tools — no per-user tiering needed yet). Tool errors become observations,
never exceptions — the registry itself converts an uncaught handler exception into
`ToolResult(ok=False)`, so handlers only need to special-case *expected* failures (404/422) into a
readable message.

### 6.2 Tool catalogue (all `user_id`-scoped via the internal API)
| Tool | Purpose |
|---|---|
| `update_profile_section(section, value)` | Replace an entire profile section (overwrites) |
| `add_profile_item(section, item)` | Append one item to a list-type profile section, without clobbering existing items |
| `record_clarification(key, value)` | Persist a clarifying-question answer into the profile's `enrichment` list (implemented as `add_profile_item` with `section="enrichment"`) |
| `draft_cv(job_id, instructions?)` | **(M5, done)** Tailor + assemble a RenderCV YAML CV for a job and persist it as a new document version (§8.3) |
| `draft_cover_letter(job_id, instructions?)` | **(M6, done)** Tailor + assemble a cover letter (reusing the CV's RenderCV/Typst pipeline) for a job and persist it as a new document version (§8.4) |
| `list_application_status(job_id)` | **(M7, done)** Read the tracked application status for a specific job — stage, submission date, next action, finalized documents |
| `change_application_status(job_id, stage)` | **(M7, done)** Transition a job's application to a new stage; entering "Applied" for the first time auto-finalizes the latest CV + cover letter as the submitted documents |

`get_profile` / `list_jobs` / `get_job` from the original catalogue were **dropped** — see §6.1;
the same data reaches the agent via `system_prompt_fn` instead. **`compile_document`/`save_document`
were also dropped from the M5 tool set** (decided during M5 implementation, not just planning):
the CV panel sits directly next to the editor in the job-detail page, so compiling and saving are
one-click UI actions against the public API (`POST /api/documents/compile`, `PUT /api/documents/{id}`)
— giving the agent its own redundant tools for the same two actions would be pure overhead under the
write-only-tools philosophy (§6.1). `draft_cv` takes `job_id` as an explicit argument (not derived
from `conversation_id`) because agent_kit's `Tool` handler signature is `(user_id, arguments)` only —
it has no access to the conversation id the way `system_prompt_fn` does — but this costs nothing
since the job's id is already shown to the model in the job-mode context block (`system_prompt_fn`),
so the model just echoes it back as a tool argument. **`list_application_status` (M7) is the one
deliberate exception to the write-only-tools philosophy** — unlike profile/job data, application
tracking state is not injected into the system prompt every turn (§6.1's per-turn injection only
covers profile/job), so a genuine read tool is the only channel for the agent to learn a job's
current stage. Both M7 tools are job-scoped (`job_id` argument, same reasoning as `draft_cv` above)
since applications are 1:1 with jobs (§7).

### 6.3 Memory configuration — and why episodic is OFF
- **Working memory + session store: ON** — needed for multi-turn coherence within a conversation.
- **Episodic (vector) recall: OFF.** The source of truth (profile, jobs, documents) lives in the app
  DB and is injected **deterministically per turn** (§6.1), so the agent never needs fuzzy vector
  recall to "remember" facts. Episodic only adds marginal cross-conversation fuzzy recall while
  **forcing an embedding model into the install** (hurting the one-command setup goal). It is a
  config flag (`memory.episodic.enabled`) we can flip on later if we want "you mentioned X on
  another job" recall.
- **agent_kit factual auto-extraction: OFF.** Enrichments are persisted **explicitly** via
  `record_clarification` into the canonical profile, keeping a single source of truth (no duplicate
  fact store to reconcile).

### 6.4 Model selection & mid-conversation switching
- The provider/model is set once in `config.yaml` (`llm_kit.llm`).
- `app.selectable_models` is surfaced in each `AgentPanel` as a picker (`GET /api/chat/models`).
  Choosing a model sends `{"type": "set_model", "model": model_id}` over the existing WS
  connection; the backend's chat proxy already forwards arbitrary JSON frames with the trusted
  `user_id` injected, so no dedicated REST mutation endpoint or proxy change was needed — the
  sidecar's own WS handler resolves this to `service.set_conversation_model(conversation_id,
  user_id, model_id)`.
- Models sharing the configured endpoint switch natively. For **true cross-provider** switching, the
  admin can point `llm_kit.llm` at an **OpenAI-compatible gateway (e.g. LiteLLM)** that fronts multiple
  providers — documented as optional, not required.

### 6.5 Chat transport
Each `AgentPanel` opens a WebSocket to the backend chat proxy (`/api/chat/ws/{conversation_id}`,
where `conversation_id` is `profile`, `` job:{job_id} ``, or one with a `.{n}` "new chat"
generation suffix) → backend resolves the session cookie to a trusted `user_id`, namespaces the
conversation id (`{user_id}:{conversation_id}`), and relays to the sidecar's WS with
`X-Internal-Secret` → streams typed `AgentEvent` frames (`text` / `tool_call` / `tool_result` /
`turn_complete` / `error`) back to the frontend. The frontend never contacts the sidecar directly.
Conversation end (disconnect/idle) is signalled to the sidecar to finalize working memory; the
stable (non-suffixed) conversation id is what lets a user navigate away and back and resume the
same thread, until agent_kit's idle `ttl_s` expires it.

### 6.6 Profile version history & undo *(M5)*
Every profile write snapshots the **pre-change** state into `profile_versions` (§7) before applying
the change, so "restore version N" reads as "go back to how things were right before that change."
- **User saves** (`PUT /api/profile`, resume re-upload) snapshot **immediately, every time**.
- **Agent writes** (`/internal/profile/update-section`, `/internal/profile/add-item`) snapshot
  through a **debounce window** (`app.profile_history.agent_debounce_minutes`, default 15): a new
  snapshot is created only if the newest existing version isn't already agent-sourced and still
  within the window. This coalesces a whole conversation's burst of tool-call edits into **one**
  undo step — matching the mental model of undoing "what the agent did," not stepping through each
  individual tool call.
- History is capped at `app.profile_history.max_versions` (default 20) per user, pruned oldest-first
  on insert.
- **Restore** (`POST /api/profile/versions/{id}/restore`) snapshots the *current* state first (so the
  restore itself is undoable), then applies the old snapshot's data as a new profile version — never
  rewriting history in place.

---

## 7. Data model (SQLite, owned by backend)

| Table | Key columns |
|---|---|
| `users` | id, email (unique), password_hash, role (`admin`/`user`), is_active, created_at |
| `sessions` | token_hash (pk — SHA-256 of the opaque cookie token), user_id → users, expires_at |
| `resumes` | id, user_id, filename, format (`pdf`/`docx`/`tex`), raw_text, uploaded_at |
| `profiles` | id, user_id, version, data (JSON master profile), updated_at |
| `jobs` | id, user_id, source_url, raw_text, parsed (JSON), shortlist_status, created_at |
| `documents` | id, user_id, job_id → jobs, type (`cv`/`cover_letter`), source_format, source_text, version, is_finalized, created_at |
| `profile_versions` | id, user_id, version, data (JSON pre-change snapshot), source (`user`/`agent`/`restore`), created_at |
| `applications` | id, user_id, job_id → jobs (**unique** — 1:1), stage, submitted_at, last_activity_at, next_action, auto_stale_at, notes, created_at, updated_at |
| `application_documents` | id, application_id → applications, document_id → documents, doc_type (`cv`/`cover_letter`), created_at (snapshot of the finalized CV + cover letter used — by id only, no content copy) |
| `application_events` | id, application_id, from_stage, to_stage, at, note |

**Master profile JSON shape** (`profiles.data`): `contact`, `summary`, `skills[]`,
`experience[]{company,title,start,end,location,bullets[],tech[]}`, `projects[]{name,link,bullets[],tech[]}`,
`education[]`, `extras[]` (patents/talks/OSS/interests), `enrichment[]` (clarification key/values).

All user-owned tables carry `user_id`; **deleting a user cascades** to all of the above. Resume
uploads live in a per-user directory in the file store; deletion removes them too. **`documents` has
no `pdf_path`** (M5 decision) — only the RenderCV YAML source is persisted; PDFs are compiled
on demand and never written to disk, so there is nothing to clean up for documents beyond the ORM
row itself. **`documents` versions are append-only** — saving an edited CV inserts a new row rather
than mutating the existing one, so a finalized application (M7) can snapshot the exact version
submitted even after later edits. **`profile_versions` stores the *pre-change* snapshot** (the state
right before a write is applied), capped at a configurable count per user (`app.profile_history.
max_versions`, default 20, pruned oldest-first on insert) — see §6.6.

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

### 8.3 CV generation (`draft_cv` tool / `POST /api/documents/draft`) — **done, M5**
Built as **deterministic skeleton + LLM tailoring**, not a single structured-output call against a
full RenderCV-mirroring schema — decided during M5 planning after two considerations: (1) RenderCV's
real schema (`sections: dict[str, list[Entry]]`, 9 entry types) isn't expressible as a single static
JSON-Schema for constrained decoding, and a rigid fixed-section approximation of it would have ~7
nested list-of-object fields — more than the 4 that already forced `ProfileModel`'s Part1/Part2 split
(§8.1) — and (2) letting the LLM regenerate factual fields (dates, company names, emails, URLs) it
should never touch is unnecessary hallucination risk on exactly the data that must be exact. Instead:
1. `llm.invoke(..., response_model=TailoredCV)` — **one** call (confirmed empirically against the
   real Anthropic API, no Part-split needed) — takes the master profile (list items numbered) + job +
   `good_resume.md` rules, and returns an **index-based selection/rewrite** (by 0-based index into the
   profile's own lists, facts never re-emitted), in CV order, plus reworded `summary`/`highlights`
   (quantified, JD-mirrored, §7/§8-compliant) and regrouped `skills`. **Inclusion policy differs per
   section, to stop the model silently dropping jobs/degrees:**
   - **experience — include-all.** The model returns one entry *per* profile experience, each with an
     explicit `include` flag; a role is dropped only when the model sets `include: false` **and** it
     is old enough (a server-side recency floor in `build.py` refuses to drop anything ended within 5
     years / ongoing / undatable). Older *included* roles are made terser, not omitted.
   - **education — always included.** Every degree renders; the model contributes reworded highlights
     only, never a drop decision.
   - **projects / publications / extras — selectable.** Presence-based: only the returned indices
     render (these are legitimately skippable).
   Facts are never in this model's output.
2. `backend/app/rendercv/build.py` deterministically assembles the RenderCV YAML in Python: contact
   block copied **verbatim** from the profile (phone/website format-validated, invalid values
   omitted rather than passed through — RenderCV's own schema is the final gate for anything that
   still doesn't validate), experience/education/publications/extras looked up by index and merged
   with the tailored rewrite, a fixed `design: {theme: <app.rendercv.theme config>}` (never
   LLM-generated), and job keywords → `settings.bold_keywords`.
3. The assembled YAML is `documents.source_text` — **not** rendered to PDF at this point.
4. Compiling (`POST /api/documents/compile {source_text}`) validates + renders **in-process** via
   RenderCV's own Python API (`rendercv.schema.rendercv_model_builder.build_rendercv_dictionary_and_model`
   → `rendercv.renderer.{typst,pdf_png}`) into a `TemporaryDirectory`, and streams PDF bytes back —
   **no PDF or Typst source is ever persisted** (privacy decision, §2). This one stateless endpoint
   covers both "preview my unsaved edits" and "view a saved version," since the frontend always has
   the source text in hand either way.
5. Saving an edit (`PUT /api/documents/{id} {source_text}`) inserts a **new** `documents` row
   (append-only versioning, §7) rather than mutating in place.
- User edits the YAML directly in-app (CodeMirror) → compile-preview → PDF renders inline. Compile
  errors are structured `{stage: "yaml"|"schema"|"render", errors: [...]}`, shown next to the editor.

### 8.4 Cover letter (`draft_cover_letter` tool / `POST /api/documents/draft-cover-letter`) — **done, M6**
Resolved the "TBD at M6 planning time" typesetting decision by **reusing the CV's RenderCV/Typst
pipeline** rather than introducing a second toolchain (a standalone Typst letter template was
considered and rejected — it would need its own compile path and editing surface, plus manual
theme-matching):
1. `llm.invoke(..., response_model=TailoredCoverLetter)` — **one** call (flat schema: `worth_it`,
   `recipient`, `salutation`, `body_paragraphs: list[str]`, `closing` — confirmed against the real
   Anthropic API, no Part-split needed, same reasoning as `JobModel`). Prose only, per
   `good_resume.md` §12 (company-first, role understanding, 2–3 qualifications tied to the JD with
   proof, named company); never re-emits facts (name, contact details, company name).
2. `backend/app/rendercv/letter.py`'s `build_cover_letter_yaml` assembles the RenderCV YAML: contact
   block via the same `build._build_contact` the CV uses (verbatim from the profile), one
   `cv.sections` entry (`TextEntry` — a list of plain-string paragraphs: today's date, computed in
   Python, never asked of the LLM; salutation; each body paragraph; closing + name), and the same
   `design: {theme: <app.rendercv.theme config>}` as the CV — this is what makes the letter visually
   consistent with the CV "for free." No `bold_keywords` (auto-bolding keywords in prose reads as
   keyword stuffing, unlike in CV bullet highlights).
3. Compile/edit/preview/versioning are **entirely unchanged** from §8.3 — `compile_pdf`,
   `POST /api/documents/compile`, `PUT /api/documents/{id}`, and the CodeMirror-editor + `<iframe>`-
   preview UI all already operate on `documents.source_text` regardless of `type`, so no new code
   was needed there. `GET /api/documents` already took a `type` query param (default `"cv"`) since
   M5, ready for `type=cover_letter` with no schema change.
- Frontend: `frontend/components/cv-artifact.tsx` was generalized into
  `frontend/components/document-artifact.tsx`'s `DocumentArtifact`, parameterized by
  `documentType: "cv" | "cover_letter"` plus display strings — the job-detail page's Application tab
  now renders two instances (CV, then cover letter, stacked).
- `draft_cover_letter` is the only new agent tool (mirrors §6.2's `draft_cv` reasoning — compiling/
  saving stay one-click UI actions, not agent tools).

### 8.5 Clarifying-question loop
The agent compares the profile against `good_resume.md` to find gaps (missing numbers/impact, thin
projects, unclear target role/level, JD-relevant skills not evidenced) and asks targeted questions;
answers persist via `record_clarification`, enriching the master profile for all future documents.

---

## 9. Application tracking & automation

- **Stages:** `Draft → Applied → Recruiter Screen → Technical → Onsite → Offer → Accepted / Declined`,
  plus terminal `Rejected` and automatic `Stale`.
- **On submission:** snapshot the **finalized CV + cover letter** into `application_documents` so the
  exact materials used are preserved for future reference, even if the user later regenerates
  documents. **Implemented (M7) as a reference to the exact `documents` row id, not a content or PDF
  copy** — consistent with M5's DB-only, no-PDF-persistence decision (§2, §8.3): `documents` rows are
  already immutable/append-only, so the latest CV/cover-letter version at submit time simply has
  `is_finalized` flipped and its id recorded; the PDF is still compiled on demand from that row's
  `source_text`, same as any other version.
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
- `GET /api/chat/models` (selectable-model list for the `AgentPanel` picker); `WS
  /api/chat/ws/{conversation_id}` (proxy to the sidecar — see §6.5). Model switching is a WS frame
  (`{"type": "set_model", "model": ...}`), not a separate REST endpoint — the proxy already
  forwards arbitrary JSON frames with the trusted `user_id` injected (§6.4).
- **Admin** (`role=admin`): `GET /api/admin/users`, `DELETE /api/admin/users/{id}`,
  `POST /api/admin/users/{id}/reset-password`, `POST /api/admin/users/{id}/disable`

**Internal (`/internal/*`, requires `X-Internal-Secret`, `user_id` in body/params)** — the tool
callbacks and context feed backing §6.1/§6.2:
- `POST /internal/context` `{user_id, conversation_id}` → `{context: str}` — backs
  `system_prompt_fn` (§6.1).
- `POST /internal/profile/update-section` `{user_id, section, value}` — backs
  `update_profile_section`.
- `POST /internal/profile/add-item` `{user_id, section, item}` — backs `add_profile_item` and
  `record_clarification`.
- `POST /internal/documents/draft-cv` / `draft-cover-letter` `{user_id, job_id, instructions?}` —
  back `draft_cv` / `draft_cover_letter`.
- `POST /internal/applications/status` `{user_id, job_id}` → `{summary: str}` — backs
  `list_application_status`.
- `POST /internal/applications/set-stage` `{user_id, job_id, stage}` — backs
  `change_application_status`; routes through the same `transition_stage` the public API uses, so
  entering `Applied` here also snapshots the latest CV + cover letter (§9).

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

**M2 — Resume upload → master profile** ✅
- Upload pdf/docx/tex → docling/text extraction → `response_model=ProfileModel` → `profiles` v1;
  full profile editor UI (every section editable; save bumps version).
- **Acceptance:** ✅ sample pdf, docx, and tex each parse into a coherent, editable profile; edits persist.

**M3 — Jobs shortlist** ✅
- Add job by URL (trafilatura) with **paste fallback**; `response_model=JobModel`; shortlist list +
  detail UI; editable parsed fields.
- **Acceptance:** ✅ a normal URL parses; a blocked URL cleanly falls back to paste; fields editable.

**M4 — Contextual agent panels + profile-enrichment tools** ✅
- Design pivot from the original spec (§6.0): no standalone chat tab — the agent is embedded as a
  split-screen `AgentPanel` on the profile page and each job detail page.
- New `backend/app/internal/` package: `POST /internal/context` (backs `system_prompt_fn`, injects
  the profile — and job, in job mode — into the prompt every turn) and
  `POST /internal/profile/{update-section,add-item}` (backs the three write tools), all gated by
  `X-Internal-Secret` with explicit `user_id`.
- `agent/tools/`: `update_profile_section`, `add_profile_item`, `record_clarification` — write-only,
  no read tools (§6.1); registered via `AgentService.build(..., extra_tools=..., system_prompt_fn=...)`;
  `docs/good_resume.md` embedded in the static system prompt.
- Chat proxy namespaces conversation ids by `user_id`; `AgentPanel` renders `tool_call`/`tool_result`
  frames inline, has a model picker (`GET /api/chat/models` + WS `set_model` frame — §6.4), and a
  "new chat" button (generation-suffixed conversation id).
- Profile page shows the master profile updating live next to the panel, with agent-touched
  sections briefly highlighted; job detail page shows JD-gap-analysis chat plus an M5 artifact
  placeholder.
- **Acceptance:** ✅ in the profile panel, the agent enriches the profile (new items appear in
  DB/UI, visible live without a manual reload); in the job panel it does gap analysis using
  injected profile+job context (no read-tool round trips); switching model mid-conversation works;
  user A's tools/context cannot touch user B's data (`backend/tests/test_internal.py`); the
  internal API rejects calls without `X-Internal-Secret`.

**M5 — CV generation + source editor + PDF preview + profile version history** ✅
- Deterministic-skeleton + LLM-tailoring generation (§8.3, `TailoredCV` schema — one call, no
  Part-split needed): `backend/app/rendercv/{tailor,build,compile,service}.py`. RenderCV renders via
  **Typst**, not LaTeX/TinyTeX — no `.tex` output, no system LaTeX toolchain (correction from the
  original plan, §2). `documents` stores YAML source only — **no PDF is ever persisted**; compiling
  is in-process (`rendercv.schema.rendercv_model_builder` + `rendercv.renderer.*`) into a temp dir.
  Versions are append-only rows.
- New `backend/app/internal/documents.py` (`POST /internal/documents/draft-cv`) + `draft_cv` agent
  tool (`agent/tools/documents.py`) — the only new agent tool; `compile_document`/`save_document`
  were **not** added as tools (§6.2) since compiling/saving are one-click UI actions next to the
  editor. New public API: `backend/app/api/documents.py` (draft/list/get/save/delete/compile).
- Frontend: `frontend/components/cv-artifact.tsx` (CodeMirror YAML editor + `<iframe>` PDF preview,
  zero new PDF-viewer dependency) replaces the M4 artifact placeholder in the job-detail page;
  refetches on the agent's `draft_cv` tool_result frame via an imperative ref handle, mirroring the
  profile page's existing tool-result-driven refresh pattern.
- **Added to M5's scope during planning** (not in the original SPEC): profile version history with
  undo (§6.6, §7's `profile_versions` table) — debounced agent-write snapshots, immediate user-save
  snapshots, capped history, restore-as-new-version. UI: a "Version history" card on the profile page.
- **Acceptance:** ✅ generate a tailored CV for a job (via the agent tool AND the UI "Generate CV"
  button); edit the YAML; re-compile; preview updates; saving creates a new version, versions are
  listable/switchable; contact facts in the output match the profile exactly (no hallucinated
  emails/dates — verified via `build.py`'s unit tests); a conversation's burst of agent profile edits
  produces one coalesced undo step, a user save produces its own, restore works and is itself
  undoable; cross-user isolation verified for documents and profile versions; no PDFs or generated
  files persisted anywhere on disk. 124 backend tests + 23 agent tests green; `npm run build` clean.
  Real Docker-image compile (vs. wheel-portability inspection) not verified in this environment — see
  CLAUDE.md's M5 gotchas.

**M6 — Cover letter generation + editor** ✅
- `draft_cover_letter` (company-first, JD-tied, §12); reuses the CV's RenderCV/Typst pipeline rather
  than a second toolchain (§8.4's resolution of the "TBD" typesetting decision) — a `TailoredCoverLetter`
  LLM call (flat schema, one `llm.invoke()`, confirmed against the real Anthropic API) + deterministic
  YAML assembly (`build_cover_letter_yaml`, reusing `build._build_contact`); compile/edit/preview/
  versioning are the same §8.3 code paths, unchanged.
- Frontend: `cv-artifact.tsx` generalized into `document-artifact.tsx`'s `DocumentArtifact`
  (parameterized by `documentType`), rendered twice (CV, then cover letter) in the job-detail page's
  Application tab.
- **Acceptance:** ✅ generate/edit/compile a cover letter via the agent tool AND the UI "Generate cover
  letter" button; PDF is professional and visually consistent with the CV (same theme/fonts/header —
  verified by rendering a real letter through the actual Typst compiler); cross-user isolation verified
  for cover-letter documents (internal + public API); CV and cover-letter versions for the same job
  number independently. 150 backend tests + 29 agent tests green; `npm run build` clean.

**M7 — Application tracking + automation + finalized-doc history** ✅
- One `Application` row **auto-created per job** on ingest (1:1, `job_id unique`), plus an idempotent
  startup backfill (`backend/app/applications/service.py`) for jobs created before M7 shipped. New
  `application_events` (one row per transition, manual or automated) and `application_documents`
  (snapshot association — stores only the `document_id` of the exact finalized version, since
  `documents` rows are already immutable/append-only) tables.
- `backend/app/applications/{service,automation,scheduler,stages}.py`: `transition_stage` (records
  an event; entering `Applied` for the first time snapshots the latest CV + cover-letter `Document`
  versions via `finalize_documents`, flipping `is_finalized`); `apply_automation(db, now)` — a pure
  function of time so it's time-travel-testable — marks idle **Applied/Recruiter Screen/Technical/
  Onsite/Offer** apps `Stale` past `stale_after_days`, then `Rejected` past `auto_reject_after_days`
  (checking the reject threshold first so a long-idle app can skip straight past `Stale` in one pass).
  An APScheduler `BackgroundScheduler` runs this daily (+ once at startup), wired into `main.py`'s
  lifespan; skipped under pytest since it bypasses `get_db`'s test override and would otherwise touch
  the real dev DB file directly via its own `SessionLocal()`.
- New `backend/app/api/applications.py` (`GET ""` w/ optional `job_id` filter, `GET/PATCH "/{id}"`,
  `POST "/{id}/submit"`) and secret-gated `backend/app/internal/applications.py`
  (`/internal/applications/{status,set-stage}`) backing two new **job-scoped** agent tools —
  `list_application_status(job_id)` (the one deliberate read-tool exception to §6.1's write-only
  philosophy, since application state isn't injected per-turn) and `change_application_status(job_id,
  stage)` (write; routes through the same `transition_stage`, so an agent-driven "Applied" also
  snapshots documents).
- Frontend: `/applications` (nav entry) with a **`@dnd-kit`** drag-and-drop kanban board (columns per
  stage) + sortable/filterable table toggle (`Tabs`); no separate `/applications/[id]` page since
  applications are 1:1 with jobs — cards/rows link straight to `/jobs/{job_id}`. The job-detail page's
  Application tab gained `components/application-status-card.tsx` (stage select, Submit-application
  `AlertDialog`, next_action/notes editing, finalized-document PDF preview via the existing
  `apiCompileDocument` blob-URL flow, events timeline) above the CV/cover-letter `DocumentArtifact`s.
- **Acceptance:** ✅ a new job gets a Draft application automatically; submitting finalizes the latest
  CV + cover letter (`is_finalized`, `application_documents`) and is idempotent (no duplicate snapshot
  on a second submit); dragging a kanban card or using the job-detail stage select persists the
  transition and appends an event; a time-travel unit test (backdating `last_activity_at`, then
  calling `apply_automation` directly) proves `Stale` then `Rejected`, including the SQLite
  tz-naive-on-read comparison; the agent answers "what's the status of this application?" via
  `list_application_status` and can move stages via `change_application_status`; cross-user isolation
  and cascade-on-delete (user, job) verified for all three new tables; the internal endpoints reject
  calls without `X-Internal-Secret`. 180 backend tests (150 + 30 new) + 39 agent tests (29 + 10 new)
  green; `npm run build` clean; `npm audit` / `uv audit` clean (both services).

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
4. Profile panel: run the clarifying-question loop and confirm enrichments appear live; open the
   job detail panel and confirm JD-gap analysis; **switch models** mid-conversation in either panel.
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
  (brings `llm_kit`), docling, trafilatura, `rendercv[full]` (brings `typst` + `rendercv-fonts` —
  prebuilt-wheel Typst compiler, **not TinyTeX/LaTeX**, §2), APScheduler, pydantic.
- **Agent sidecar:** `agent_kit` (configured per §4/§6), our custom tools.
- **Frontend:** Next.js, React, TypeScript; `@uiw/react-codemirror` (+ `@codemirror/lang-yaml`) for
  the YAML/letter source editor; PDF preview via a plain `<iframe>` blob URL (no dedicated PDF-viewer
  library needed); charts for analytics.
- **LLM:** any provider/model via the `llm_kit.llm` block — no hard-coded model anywhere.

# CLAUDE.md — hirable project context

## Security philosophy

Security is a core pillar of this project, not an afterthought or add-on. Every feature must
be built with security in mind from the start. We do not take shortcuts that introduce
vulnerabilities, and we do not defer security concerns to "later". Concretely:

- Dependencies are kept up to date and audited (`npm audit`, `uv audit`). Vulnerabilities are
  fixed immediately — use `overrides`/`dependency_overrides` to force patched transitive deps
  rather than accepting known CVEs.
- The three trust boundaries in SPEC §5 are enforced in code, not just documented.
- User data isolation is strict: every query is scoped to `user_id`; cross-user access returns
  404/403. This must be verified, not assumed.
- The agent sidecar has no published port. The `X-Internal-Secret` middleware is not optional.
- Passwords are hashed with argon2 (not bcrypt, not SHA). Sessions are opaque random tokens.
- `user_id` is always derived from the authenticated session server-side — never trusted from
  the client or from the agent sidecar's request body.

---

## Dependency management (uv only — do not hand-edit)

- **Never hand-write a package version or edit `pyproject.toml`/`uv.lock` directly.** Do not
  guess, recall, or assert what version of a package is "current" — you will be wrong.
- To add or change a dependency, run `uv add <package>` (or `uv add <package> --dev`,
  `uv remove <package>`) and let uv resolve and pin it. Same for the agent: `cd agent && uv add …`.
- If a specific constraint is genuinely needed, still go through uv: `uv add "package>=x,<y"`.
- To learn what version is installed, ask the tooling (`uv pip show <pkg>`, `uv tree`), never
  memory.

---

## What this is
A self-hosted, multi-user job-application assistant (resume parsing → master profile → tailored
CV/cover letter generation via an agentic chat → application tracking + analytics). Full spec in
`SPEC.md`. Implementation is milestone-based (M0–M9); **M0–M7 are complete** (three-service
skeleton + one-command setup; full auth + session management + admin console + UI redesign;
resume upload → master profile; job ingest by URL/paste → shortlist; contextual agent panels
with profile-enrichment write tools — see SPEC.md §6.0 for the chat-tab → embedded-panel pivot;
tailored CV generation + YAML editor + on-demand PDF preview + profile version history/undo —
see SPEC.md §8.3/§6.6 and this file's M5 gotchas for the Typst-not-TinyTeX correction; tailored
cover-letter generation reusing the CV's RenderCV/Typst pipeline — see SPEC.md §8.4 and this
file's M6 gotchas for the "reuse RenderCV YAML, don't build a second toolchain" decision;
application tracking + staleness/auto-reject automation + finalized-doc snapshotting — see
SPEC.md §9 and this file's M7 gotchas for the auto-create-per-job and snapshot-by-id decisions).

---

## Architecture — three services

```
[ Next.js :3000 ] ──WS/REST──▶ [ FastAPI :8000 ] ──WS──▶ [ agent_kit sidecar :8000 (internal) ]
```

- **frontend/** — Next.js 16 / TypeScript. Only published UI. Connects to backend only.
- **backend/** — FastAPI / Python 3.13. System of record. DB, auth, public API, chat proxy,
  document rendering, scheduler. The only component with DB access.
- **agent/** — agent_kit sidecar. Chat brain. **No published port** — Docker internal network only.
  Backend reaches it at `http://agent:8000`; locally override with `AGENT_BASE_URL`.

---

## Configuration split (important — do not mix these up)

| File | What goes here |
|---|---|
| `.env` | Secrets only: `AGENT_INTERNAL_SECRET`, `ANTHROPIC_API_KEY` |
| `config.yaml` | Everything else: LLM model/endpoint, agent settings, tracking thresholds |

`config.yaml` supports `${VAR:-default}` env expansion. The backend expands it via a small
regex expander in `backend/app/config.py`. The agent sidecar expands it via agent_kit's own
`_interpolate_env` (called inside `load_dict`).

---

## agent_kit facts (learned from source / examples)

- **Install:** git URL only (not on PyPI): `agent_kit @ git+https://github.com/sharma-n/agent_kit`
  — pulls `llm_kit` transitively. Requires `[tool.hatch.metadata] allow-direct-references = true`
  in any `pyproject.toml` that lists it as a dependency.
- **Python:** requires **3.13+**.
- **Server:** ships a runnable ASGI app via `create_app_from_yaml` factory, but **we do not
  call it directly** — it rejects unknown top-level keys (our `app:` block). Instead we load
  the YAML ourselves, strip `app:`, and call:
  ```python
  from agent_kit.config.loader import load_dict
  from agent_kit.config.schema import AgentKitConfig
  from agent_kit.service import AgentService
  from agent_kit.serving.app import create_app
  service = AgentService.build(load_dict(AgentKitConfig, agent_raw))
  app = create_app(service)
  ```
  This is the same internal path `create_app_from_yaml` uses, so env-var interpolation runs.
- **WS endpoint:** `/ws/{conversation_id}`. Client sends `{"user_id": "...", "message": "..."}`.
- **Streamed event types** (`type` field in each JSON frame):
  - `text` — `{text: str}` (stream chunks, concatenate)
  - `tool_call` — `{name, arguments}`
  - `tool_result` — `{name, ok, content}`
  - `turn_complete` — `{stop_reason, usage}`
  - `error` — `{error}`
- **Programmatic API** (for multi-user use without the server):
  `AgentService.from_yaml("config.yaml")` → `await service.astart()` → `service.agent.run_turn(user_id, conv_id, msg)` (async generator of events) → `await service.aclose()`.
- **Permissions:** `await service.stores.permissions.grant(user_id, set_of_tool_names)` /
  `.revoke(...)`. `tools.default_allowed` in `config.yaml` is the global fallback — a tool present
  in `extra_tools` but absent from `default_allowed` (and never explicitly `grant`ed) is silently
  invisible to the model *and* blocked at execution. M4 uses `default_allowed` only (no per-user
  grants needed — every user gets the same core write tools).
- **Tool injection (confirmed in M4):** `Tool(definition=ToolDefinition(name, description,
  parameters), handler=async (user_id: str, args: dict) -> str)` — `ToolDefinition`/`ToolCall` are
  re-exported from `llm_kit`, `Tool` from `agent_kit.tools.base`. Register via
  `AgentService.build(cfg, extra_tools=[...], system_prompt_fn=...)` — both are keyword params on
  `build()`, not a post-construction call. **The registry converts an uncaught handler exception
  into `ToolResult(ok=False)`** — handlers don't need a blanket try/except, only special-case
  *expected* failures (404/422 from our internal API) into a readable observation string.
- **Per-turn dynamic system prompt:** `system_prompt_fn: Callable[[str, str], Awaitable[str]]`
  passed to `AgentService.build(...)`; agent_kit calls `await system_prompt_fn(user_id,
  conversation_id)` **fresh on every turn** and appends the result to the system prompt as a
  tier-0 (never-evicted) block. This is what lets hirable's tools be **write-only** — no
  `get_profile`/`list_jobs`/`get_job` tool is needed because the current profile (and job, in job
  mode) is injected automatically every turn instead of fetched on demand.
- **Conversation ids are global and user-owned — namespace them.** agent_kit's `SessionStore.load`
  raises `UnauthorizedError` on cross-user access to the *same* conversation id, so a
  client-chosen fixed id like `"profile"` would collide across different users. The backend's
  chat proxy (`app/api/chat.py`) prefixes every upstream conversation id with the trusted
  `user_id` (`f"{user_id}:{conversation_id}"`); `/internal/context` strips that prefix (and an
  optional `.{n}` "new chat" generation suffix) back off before interpreting the conversation's
  mode.
- **Model switching:** inbound WS frame `{"type": "set_model", "user_id": ..., "model": ...}` (or
  `"model": null` to clear) resolves server-side to
  `service.set_conversation_model(conversation_id, user_id, model)`. The backend's chat proxy
  already JSON-parses every inbound browser frame and unconditionally overwrites
  `payload["user_id"]` before forwarding upstream verbatim — so a `{"type": "set_model", "model":
  ...}` frame from the browser works with **zero proxy code changes**; no dedicated REST mutation
  endpoint was needed.
- **Conversation end:** `await service.agent.end_conversation(user_id, conv_id)` — call on WS
  disconnect to finalize working memory.

## agent_kit config schema (key fields, as of M0)

```yaml
agent:
  max_iterations: 6
  per_tool_timeout_s: 30.0   # NOT per_turn_budget_s
  system_prompt: |...        # good_resume.md injected here in M4

memory:
  working:
    buffer_turns: 12
    buffer_token_budget: 4000
    idle_finalize_s: 900
    ttl_s: 3600
    sweep_interval_s: 60
  episodic:
    enabled: false            # OFF — tools fetch data deterministically
  factual:
    extraction_enabled: false # OFF — enrichments via record_clarification tool

context:
  max_input_tokens: 128000
  output_reserve_tokens: 4096

stores:
  session_backend: memory
  profile_backend: memory
  vector_backend: memory
  permission_backend: memory

tools:
  default_allowed: []         # populated in M4 with custom tool names

mcp:
  servers: []
```

---

## Security boundaries (SPEC §5)

1. Browser ↔ backend: httpOnly session cookie (added M1).
2. Backend ↔ sidecar: `X-Internal-Secret` header (env var `AGENT_INTERNAL_SECRET`).
   Middleware in `agent/bootstrap.py` enforces this on every request except `/health`.
3. Network: sidecar has no `ports:` in `docker-compose.yml` — not host-reachable.

The backend injects the trusted `user_id` into every WS message forwarded to the sidecar
(`app/api/chat.py`). The client-supplied `user_id` field is overwritten — never trusted.

---

## Key files

| Path | Purpose |
|---|---|
| `config.yaml` | Single source of truth for LLM + agent config (mounted into backend + agent) |
| `docker-compose.yml` | Three services; agent has no published port |
| `backend/app/config.py` | YAML loader with `${VAR:-default}` expansion |
| `backend/app/api/auth.py` | Signup / login / logout / me routes |
| `backend/app/api/admin.py` | Admin console routes (list / delete / disable / reset-password) |
| `backend/app/api/chat.py` | WS proxy: browser ↔ backend ↔ sidecar; injects user_id + secret; namespaces conversation id (`{user_id}:{conversation_id}`); `GET /api/chat/models` |
| `backend/app/auth/` | `password.py` (argon2), `sessions.py` (token lifecycle), `dependencies.py` (FastAPI guards) |
| `backend/app/db/` | SQLAlchemy engine, Base, User + Session models, `create_all()` migration runner |
| `backend/app/schemas.py` | Pydantic request/response schemas (`SignupRequest`, `UserOut`, …) |
| `backend/tests/` | pytest suite: auth lifecycle, isolation, admin cascade, 403 guards, WS auth, profile CRUD, job ingest/CRUD/isolation/needs_paste, internal API secret+context+isolation, M7 `test_applications.py` (auto-create/backfill, stage transitions, submit snapshotting, automation time-travel, isolation/cascade) |
| `backend/app/llm/` | `client.py` (build LLMClient from config), `deps.py` (FastAPI `get_llm` dep), `schemas.py` (ProfileModel, JobModel) |
| `backend/app/parsing/` | `extract.py` (docling + LaTeX strip), `profile.py` (resume LLM structured extraction), `jobs.py` (trafilatura fetch + job LLM structured extraction); `deps.py` deleted (docling converter no longer injected via FastAPI) |
| `backend/app/files.py` | Per-user upload storage: `/app/data/uploads/{user_id}/{uuid}.{ext}` |
| `backend/app/api/profile.py` | `POST /resume`, `GET /`, `PUT /` — all scoped to `current_user` |
| `backend/app/api/jobs.py` | `POST /` (url/paste ingest + `needs_paste` signal), `GET /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` — all scoped to `current_user` |
| `backend/app/internal/` | Secret-gated `/internal/*` routes: `context.py` (`system_prompt_fn` backend — builds the per-turn profile/job block from `conversation_id`'s mode, plus M5's "a CV already exists at v{n}" hint and M6's matching cover-letter hint in job mode), `profile.py` (`update-section`, `add-item` — now snapshot via `db/profile_history.py` before writing), `documents.py` (M5: `draft-cv`; M6: `draft-cover-letter` — both back their agent tools), `applications.py` (M7: `status`, `set-stage` — back `list_application_status`/`change_application_status`), `deps.py` (`verify_internal_secret`) |
| `backend/app/db/profile_history.py` | M5: `snapshot_profile` (unconditional, user saves) / `snapshot_for_agent_write` (debounced, agent writes) + prune-to-`max_versions` |
| `backend/app/rendercv/` | M5: `tailor.py` (`TailoredCV` LLM call), `build.py` (deterministic YAML assembly from profile+tailored+job), `compile.py` (in-process Typst compile, `CompileError` w/ yaml/schema/render stage), `service.py` (`draft_cv_document`/`draft_cover_letter_document` — shared by internal routes + public API); M6: `letter.py` (`TailoredCoverLetter` LLM call + `build_cover_letter_yaml`, reusing `build._build_contact`), `rules.py` (shared `good_resume_rules()` loader, extracted from `tailor.py` so `letter.py` doesn't duplicate it) |
| `backend/app/api/documents.py` | M5: `POST /draft`, `GET ""` (list, job-scoped, `type` query param), `GET/PUT/DELETE /{id}`, `POST /compile` (stateless, source-text-in/PDF-bytes-out); M6: `POST /draft-cover-letter` — all scoped to `current_user` |
| `backend/app/applications/` | M7: `stages.py` (`STAGES`/`ACTIVE_STAGES`/`STALE_OR_ACTIVE` constants + `validate_stage`), `service.py` (`get_or_create_application`, `backfill_applications`, `transition_stage` — records an `ApplicationEvent` + snapshots docs on first entry into `Applied` via `finalize_documents`), `automation.py` (`apply_automation(db, now)` — pure function of time, Stale→Rejected), `scheduler.py` (`build_scheduler()`/`run_automation_once()` — APScheduler `BackgroundScheduler`, daily) |
| `backend/app/api/applications.py` | M7: `GET ""` (optional `job_id` filter), `GET/PATCH /{id}`, `POST /{id}/submit` — all scoped to `current_user` |
| `frontend/app/(app)/profile/` | Split-screen: `AgentPanel` (conversationBase=`"profile"`) + resume dropzone / section-by-section profile editor; live-refreshes + highlights sections the agent just wrote; M5: `VersionHistorySection` (list + restore, `AlertDialog` confirm) |
| `frontend/app/(app)/jobs/` | Job shortlist list page (add by URL/paste, table) + `[id]/` split-screen detail/edit page (`AgentPanel` with conversationBase=`` `job:${id}` ``) + M5/M6: two `DocumentArtifact`s (CV, then cover letter, stacked in the Application tab); M7: `ApplicationStatusCard` above them |
| `frontend/app/(app)/applications/` | M7: kanban board (`@dnd-kit` drag-and-drop between stage columns) + sortable/filterable table view (`Tabs` toggle) — no `[id]` detail page since applications are 1:1 with jobs; cards/rows link to `/jobs/{job_id}` |
| `frontend/components/agent-panel.tsx` | Reusable chat panel (M4): WS connect, ordered text/tool_call/tool_result message parts (markdown-rendered via `react-markdown`), model picker, "new chat" generation-suffix button, one-click `starterPrompt` chip, localStorage transcript persistence keyed by `conversationId` |
| `frontend/components/document-artifact.tsx` | M5 (as `cv-artifact.tsx`), generalized in M6 into `DocumentArtifact` parameterized by `documentType: "cv" \| "cover_letter"` + display strings: CodeMirror YAML editor + `<iframe>` PDF preview (blob URL, no PDF-viewer dep) + version picker; exposes an imperative `refetch()` handle (`forwardRef`/`useImperativeHandle`) so the job-detail page can refresh either instance from `AgentPanel`'s `onToolResult` on `draft_cv`/`draft_cover_letter` |
| `frontend/components/application-status-card.tsx` | M7: stage `<select>`, Submit-application `AlertDialog` (snapshots docs), next_action/notes editing, finalized-document PDF preview (reuses `apiCompileDocument`'s blob-URL flow), events timeline — same imperative `refetch()`-handle pattern as `DocumentArtifact`, refreshed on `AgentPanel`'s `onToolResult` for `change_application_status` |
| `frontend/components/ui/textarea.tsx` | Native textarea with base-nova Tailwind styling |
| `agent/bootstrap.py` | Builds `AgentService` with `extra_tools`/`system_prompt_fn`, embeds `good_resume.md`, secret middleware, /health |
| `agent/tools/` | `client.py` (shared internal-API `httpx.AsyncClient` + `post_json`/`error_detail` helpers, relocated here in M5 so `documents.py` doesn't cross-import `profile.py`'s privates), `profile.py` (the 3 write tools), `documents.py` (M5: `draft_cv` tool; M6: `draft_cover_letter` tool), `applications.py` (M7: `list_application_status`, `change_application_status` — both job-scoped), `context.py` (`build_system_prompt_fn`) |
| `frontend/app/(app)/` | Authenticated route group: profile, jobs, applications, admin (layout enforces session cookie) — no chat route (see CLAUDE.md's M4 notes) |
| `frontend/app/(auth)/` | Auth route group: login, signup (layout redirects if already authed) |
| `frontend/components/app-shell.tsx` | Sticky nav (Profile/Jobs/Applications/Admin) + theme toggle + user dropdown |
| `frontend/components/ui/` | shadcn base-nova components (button, input, card, table, etc.) |
| `frontend/lib/api.ts` | `apiFetch` helper + typed auth/admin/chat API functions |
| `frontend/lib/auth.tsx` | `AuthProvider` + `useAuth()` context |

---

## RenderCV integration  (M5)

See **`docs/rendercv.md`** for the full RenderCV v2.8 schema reference (Pydantic models, all entry
types, design/locale/settings options, CLI reference, complete examples).

The master `ProfileModel` (`backend/app/llm/schemas.py`) is intentionally a superset of RenderCV:

| ProfileModel field | RenderCV mapping |
|---|---|
| `contact.headline` | `cv.headline` (only when no tailored summary is present; mutually exclusive to avoid duplication) |
| `contact.website` | `cv.website` |
| `contact.social_networks[].network/username` | `cv.social_networks[].network/username` |
| `experience[].position` | `ExperienceEntry.position` |
| `experience[].start_date / end_date` | `ExperienceEntry.start_date / end_date` |
| `experience[].highlights` | `ExperienceEntry.highlights` |
| `experience[].summary` | `ExperienceEntry.summary` |
| `projects[]` | `NormalEntry` (name, start/end, location, summary, highlights) |
| `education[].area` | `EducationEntry.area` |
| `education[].highlights` | `EducationEntry.highlights` |
| `skills[].label / details` | `OneLineEntry.label / details` |
| `publications[]` | `PublicationEntry` (title, authors, doi, url, journal, date) |
| `extras[]` | `NormalEntry` / `BulletEntry` (title, highlights) |
| `experience[].tech`, `projects[].tech`, etc. | our extension — not in RenderCV schema |
| `enrichment[]` | our extension — not in RenderCV schema |

In M5, the CV generation step will map `ProfileModel` → RenderCV YAML, call `rendercv render`, and
stream back the PDF. The `date` field (free-form) on experience/education/projects is for cases
where a clean `start_date`/`end_date` range cannot be expressed; use `start_date`/`end_date`
preferentially.

---

## Milestone status

| Milestone | Status | Notes |
|---|---|---|
| M0 — skeleton + chat round-trip | **Done** | Chat round-trip verified locally |
| M1 — auth, sessions, admin | **Done** | argon2, httpOnly cookie sessions, first-user admin, admin console, full UI redesign (Tailwind v4 + shadcn base-nova, dark mode, app shell) |
| M2 — resume upload → profile | **Done** | docling extraction, llm_kit structured parse, Resume+Profile DB models, section editor with useFieldArray, enrichment stub |
| M3 — jobs shortlist | **Done** | trafilatura fetch+extract with `needs_paste` fallback signal; flat `JobModel` designed for a single `llm.invoke()` call (no Part1/Part2 split, unlike `ProfileModel`) — verified with mocked LLM in tests, **not yet confirmed against the real Anthropic API**; list+detail UI; no `shortlist_status`/no versioning by design (deferred to M7) |
| M4 — contextual agent panels + profile-enrichment tools | **Done** | Design pivot: no standalone chat tab — `AgentPanel` embedded split-screen in profile + job-detail pages; 3 write-only tools (`update_profile_section`, `add_profile_item`, `record_clarification`) — no read tools, profile/job context injected per-turn via `system_prompt_fn` instead |
| M5 — CV generation + editor + PDF + profile version history | **Done** | Deterministic-skeleton + LLM-tailoring (`TailoredCV`, one call — no Part-split needed); RenderCV renders via **Typst, not TinyTeX** (corrects the original plan — see M5 gotchas); DB-only document storage (no PDFs ever on disk); `draft_cv` is the only new agent tool (`compile_document`/`save_document` dropped — one-click UI actions instead); profile version history/undo added to scope mid-planning |
| M6 — cover letter | **Done** | Resolved the §8.4 "TBD" typesetting decision: the cover letter **reuses the CV's RenderCV/Typst pipeline** (contact header + one `TextEntry` section of prose paragraphs) rather than a second toolchain — see M6 gotchas. `TailoredCoverLetter` (flat schema, one `llm.invoke()` call, confirmed against the real Anthropic API). `draft_cover_letter` is the only new agent tool; UI reuses the generalized `DocumentArtifact` component stacked below the CV in the job-detail page's Application tab |
| M7 — application tracking + automation | **Done** | One `Application` auto-created per job (1:1, idempotent backfill for pre-M7 jobs); `transition_stage` snapshots the latest CV+cover-letter `Document` (by id, no content/PDF copy — consistent with M5's DB-only decision) on first entry into `Applied`; `apply_automation(db, now)` is a pure function of time (Stale→Rejected) run by an APScheduler `BackgroundScheduler` (daily + once at startup, skipped under pytest — see M7 gotchas); two new job-scoped agent tools, `list_application_status` (the one read-tool exception to write-only) and `change_application_status`; frontend `/applications` kanban (`@dnd-kit`) + table, plus an `ApplicationStatusCard` on the job-detail page |
| M8 — analytics dashboard | Pending | |
| M9 — polish, hardening, docs | Pending | |

---

## Local dev (no Docker)

```bash
# Agent (port 8001 to avoid clash with backend) — INTERNAL_BASE_URL is required
# locally (M4): config.yaml's default (http://backend:8000) is the Docker-only
# hostname and is NOT reachable outside docker-compose's network.
cd agent && ANTHROPIC_API_KEY=... AGENT_INTERNAL_SECRET=dev-secret \
  INTERNAL_BASE_URL=http://localhost:8000 \
  uv run uvicorn bootstrap:create_app --factory --port 8001 --reload

# Backend (override agent URL)
cd backend && ANTHROPIC_API_KEY=... AGENT_INTERNAL_SECRET=dev-secret \
  AGENT_BASE_URL=http://localhost:8001 \
  uv run uvicorn app.main:app --port 8000 --reload

# Frontend
cd frontend && NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 npm run dev
```

---

## Gotchas encountered during M0

- **`app:` block must be stripped before passing config to agent_kit.** `AgentKitConfig`
  rejects unknown top-level keys. In `bootstrap.py` we load the YAML ourselves, drop `app:`,
  and call `AgentService.build(load_dict(AgentKitConfig, agent_raw))` directly — the same
  path `create_app_from_yaml` uses internally, so env-var interpolation still runs.

- **Config path is never hardcoded to `/app/config.yaml`.** Both `agent/bootstrap.py` and
  `backend/app/config.py` resolve `config.yaml` relative to their own `__file__`, checking
  the Docker mount location first then the repo root. This makes local dev work without env
  var juggling. Pattern: walk up parent dirs until the file is found.
- **`allow-direct-references = true`** must be set under `[tool.hatch.metadata]` in any
  `pyproject.toml` that uses git-URL dependencies, or hatchling refuses to build.
- **No `public/` directory** in the Next.js frontend — don't add a `COPY public` step in
  the Dockerfile unless static assets are actually added.
- **`per_tool_timeout_s`** is the correct agent_kit field name — not `per_turn_budget_s`.
- **`memory.working.*`** is the correct nesting — the buffer config is not a flat `memory.*`.
- agent_kit + llm_kit are **not on PyPI** — git URL install only.
- agent_kit requires **Python 3.13+** — use `python:3.13-slim` in Dockerfiles.

## Gotchas encountered during M1

- **shadcn `base-nova` style uses `@base-ui/react`, not Radix UI.** No `asChild` prop on
  Trigger components. Use the `render` prop instead:
  `<AlertDialogTrigger render={<Button .../>}>content</AlertDialogTrigger>`.
- **Tailwind v4 has no `tailwind.config.js`** — config lives in CSS via `@import "tailwindcss"`
  and `@theme` blocks. `shadcn@4.x` requires v4. PostCSS plugin is `@tailwindcss/postcss`.
- **Session tokens: only the SHA-256 hash is stored in the DB** — the raw token lives only in
  the httpOnly cookie. `resolve_session(db, raw_token)` hashes before lookup.
- **WS auth uses the session cookie** — `websocket.cookies.get(COOKIE_NAME)` before
  `websocket.accept()`; unauthenticated connections close with code 4401.
- **In-memory SQLite tests need `StaticPool`** — without it each connection sees a different
  in-memory database, so `create_all` and the session share different data. Use
  `create_engine("sqlite:///:memory:", poolclass=StaticPool)`.
- **Frontend route groups:** authenticated pages live in `app/(app)/`, auth pages in
  `app/(auth)/`. Route protection is done in the server-component group layouts via
  `cookies()` from `next/headers` — no `middleware.ts`.
- **Do not use `frontend/middleware.ts` (deprecated in Next.js 16).** Use `cookies()` from
  `next/headers` inside async server-component layouts: `(app)/layout.tsx` redirects to
  `/login` if the `hirable_session` cookie is absent; `(auth)/layout.tsx` redirects to
  `/profile` if it is present (was `/chat` pre-M4 — see M4's chat-tab → embedded-panel pivot).
  This is the modern, non-deprecated pattern — it runs in the Node.js runtime (not the Edge
  runtime), has full access to the cookie jar, and does not require any matcher config.

## Gotchas encountered during M2

- **DocumentConverter is instantiated fresh per upload.** docling's model initialization
  takes seconds, so each resume upload pays that cost. Since resume uploads are expected only
  once per account (at signup), it's not worth keeping the model resident in memory for the
  process's entire lifetime. A `DocumentConverter()` is constructed fresh in
  `backend/app/parsing/extract.py`'s `_extract_with_docling()` on each call.
- **LLMClient is built once in FastAPI lifespan** (`app.state.llm = build_llm()`) and injected
  via `get_llm(request) → request.app.state.llm`. Tests override `get_llm` via
  `app.dependency_overrides[get_llm] = lambda: fake_llm` before creating `TestClient`. The
  lifespan must guard with `if get_llm not in app.dependency_overrides` to avoid real network
  calls during tests.
- **`LLMClient` from llm_kit is built via `LLMClient(AppConfig.from_dict(config["llm_kit"]))`** —
  the backend's `config.yaml` wraps the llm_kit block under a `llm_kit:` key, so
  `LLMClient.from_yaml` cannot read it directly.
- **Profile is a single-row-per-user upsert** — `POST /resume` creates v1 or bumps version on
  re-upload; `PUT /profile` also bumps version. No history table; `version` is a monotonic counter.
- **Resume file storage is per-user** — `/app/data/uploads/{user_id}/{uuid}.{ext}`. `delete_user_uploads`
  must be called in the admin delete-user flow before ORM delete to avoid orphaned files on disk.
- **Bullets stored as `list[str]`; edited as textarea** — form boundary transforms:
  `bullets.join("\n")` to display, `value.split("\n").map(strip "- ").filter(Boolean)` to save.
  Tech stacks use comma-separation. Both conversions happen in `profileToForm` / `formToProfile`.
- **`apiUploadResume` must use bare `fetch` with `FormData`** — never set `Content-Type` header
  manually; the browser must set it with the multipart boundary. `apiFetch` always sets
  `Content-Type: application/json`, so it cannot be reused for multipart uploads.
- **`@base-ui/react` has no Textarea primitive** — `frontend/components/ui/textarea.tsx` wraps
  a plain `<textarea>` with the same Tailwind classes as Input.
- **Anthropic's structured-output grammar compiler rejects `ProfileModel` outright** with HTTP
  400 `"The compiled grammar is too large"` — this is NOT about the documented 24-optional-
  parameter cap (making every field required, via `_require()` in `backend/app/llm/schemas.py`,
  was tried first and did not fix it). Bisection (send the same tiny résumé through hand-built
  subset schemas, see the repro pattern below) proved grammar size is a function of the
  **schema alone**, independent of résumé content/length, and pinned the cause to the four
  nested list-of-object fields — `experience`, `projects`, `education`, `publications` (each
  ~7-9 string fields per item). Any 3 of those 4 fields fit under the limit together with the
  light fields (`contact`, `summary`, `skills`, `extras`); all 4 together do not. Fix:
  `parse_resume()` in `backend/app/parsing/profile.py` splits extraction into two concurrent
  `llm.invoke()` calls against `ProfileModelPart1` (`contact`+`summary`+`skills`+`experience`+
  `projects`) and `ProfileModelPart2` (`education`+`publications`+`extras`+`enrichment`), then
  merges the two parsed halves into one `ProfileModel` in Python. Tests assert
  `fake_llm.invoke.call_count == 2`, not `assert_called_once()`. **If `ProfileModel` grows a
  new nested list-of-object field in a future milestone, re-bisect** — don't assume the 2-call
  split still has margin; the repro script pattern is: build ad hoc Pydantic models from subsets
  of the existing item classes, call `llm.invoke(response_model=candidate)` for each, and see
  which combinations 400.

## Gotchas encountered during M3

- **`JobModel` is intentionally flat** (scalar strings + `list[str]`, no nested list-of-object
  fields) so it was designed to need only a single `llm.invoke(..., response_model=JobModel)`
  call, unlike `ProfileModel`'s Part1/Part2 split. This has only been verified with a mocked
  LLM in `test_jobs.py` (`fake_llm.invoke.call_count == 1`) — **it has not yet been confirmed
  against the real Anthropic API**. If it 400s with "compiled grammar is too large" once
  exercised for real, apply the exact same fix as `parse_resume()`: split into
  `JobModelPart1`/`JobModelPart2`, call both concurrently via `asyncio.gather`, merge in Python.
- **trafilatura's two-step API**: `trafilatura.fetch_url(url) -> str | None` (downloads HTML) then
  `trafilatura.extract(html, url=...) -> str | None` (extracts main content) — either step can
  independently return `None`/empty on a blocked or JS-rendered page. `fetch_job_text()` in
  `backend/app/parsing/jobs.py` treats any failure in either step (or an unexpected exception) as
  `None`, never raises, and never needs a separate readability library — trafilatura's `extract()`
  already has its own fallback extraction built in.
- **The `needs_paste` signal is a `200` with a discriminated envelope, not an error.**
  `POST /api/jobs` returns `JobCreateResult {needs_paste: bool, job: JobOut | None}`. A blocked/
  empty fetch is an expected branch of the ingest flow (most job boards block bots), so it must
  not be a 4xx — `frontend/lib/api.ts`'s `apiFetch` treats non-2xx as an error and throws, which
  would incorrectly surface a toast instead of prompting the paste fallback.
- **Client-supplied `raw_text` always bypasses the fetch step, even when `url` is also present.**
  This is what makes the two-step paste-fallback flow work: `{url}` → `needs_paste: true` →
  `{url, raw_text}` (same URL, now with pasted text) → the presence of `raw_text` skips
  `fetch_job_text` entirely. `frontend/app/(app)/jobs/page.tsx` relies on this — it keeps the
  original `url` around when showing the paste textarea so the resubmit includes both.
- **No per-user file storage for jobs**, unlike `resumes`. `raw_text` (fetched or pasted) lives
  directly in the `jobs.raw_text` column — no `app/files.py` involvement, nothing to clean up on
  job delete beyond the ORM row itself. `User.jobs` cascade (`cascade="all, delete-orphan"`)
  handles user-delete cleanup automatically, same as `sessions`/`resumes` — confirmed by reading
  `admin.py`'s `delete_user`, which relies purely on ORM cascade (plus a manual
  `delete_user_uploads` call for on-disk files, which jobs don't have).
- **`jobs.updated_at` was added beyond SPEC §7's literal column list**, for parity with
  `profiles.updated_at` (both are user-edited-and-resaved rows). **`shortlist_status` was
  intentionally omitted** — the user explicitly deferred any triage/staging concept to M7's
  application-stage tracking. `JobModel` also has two fields beyond SPEC §8.2's literal list,
  added at the user's request: `responsibilities[]` (what the role *does*, distinct from
  `must_have`/`nice_to_have` which describe candidate requirements) and `team_name`/
  `team_description` (the specific hiring team, distinct from `company`/`company_type`).

## Gotchas encountered during M4

- **`app.internal_base_url` needs its own env-var expansion in `agent/bootstrap.py` — it does NOT
  get one for free from agent_kit.** The `app:` block is read (`app_block = raw.get("app", {})`)
  and then stripped out of the dict passed to `load_dict(AgentKitConfig, agent_raw)`; agent_kit's
  own `_interpolate_env` only ever sees `agent_raw`, never `app_block`. So `${VAR:-default}` syntax
  in `config.yaml`'s `app:` section (used e.g. by `internal_base_url`) is inert unless `bootstrap.py`
  expands it itself — added a small `_expand_env()` regex helper mirroring `backend/app/config.py`'s
  `_expand`, applied to `app_block.get("internal_base_url", ...)` before building the internal
  client. Symptom when this was missing: `internal_base_url` silently stayed hardcoded at
  `http://backend:8000` (the Docker-only hostname) even locally, so **every** write tool
  (`update_profile_section`/`add_profile_item`/`record_clarification`) and the per-turn
  `system_prompt_fn` context fetch failed to reach the backend at all in local (no-Docker) dev —
  the tool calls raised a raw `httpx.ConnectError` ("Name or service not known") with no actionable
  detail, and `system_prompt_fn`'s catch-all silently degraded to an empty context block instead of
  surfacing anything. Local dev now requires `INTERNAL_BASE_URL=http://localhost:8000` when
  starting the agent (see "Local dev" above) — **if you add a new `app:`-block config value that
  the agent reads directly (not via agent_kit's own config), remember it needs `_expand_env()` too,
  or it'll look fine in Docker and silently misbehave locally.**
- **Tool handlers now catch `httpx.RequestError` explicitly** (`agent/tools/profile.py`'s `_post`
  helper) and turn it into a plain-language `"error: the profile service is temporarily
  unreachable…"` observation, rather than relying solely on agent_kit's registry-level exception→
  `ToolResult(ok=False)` conversion — the raw exception text (e.g. "Name or service not known") is
  technically an observation the model receives, but it's not something the model can act on or
  explain to the user, so a readable message is substituted before it ever reaches the registry.
- **Design pivot away from a standalone chat tab, decided mid-milestone.** The original SPEC had a
  general `/chat` page. Partway through planning, the user redirected: the agent should appear
  embedded in the profile page (enrichment) and each job detail page (JD-gap analysis) instead,
  each with live-updating context on the other side of a split screen. `/chat` and its nav entry
  were deleted; every post-login/post-signup/admin-guard redirect target that pointed at `/chat`
  had to be updated to `/profile` (grep for `"/chat"` across `frontend/` if adding a new one).
- **Tools ended up write-only — no `get_profile`/`list_jobs`/`get_job`.** Once `system_prompt_fn`
  injects the current profile/job into the prompt every turn, a read tool is pure overhead (a
  wasted round trip to see data already in context). If a future milestone needs the agent to read
  something NOT already injected per-turn (e.g. comparing against a different job), add a
  narrowly-scoped read tool then — don't reintroduce the full original read-tool set speculatively.
- **This Starlette version has removed both `app.on_event` and `router.on_shutdown`** (confirmed:
  `hasattr(FastAPI, "add_event_handler")` is `False`, `hasattr(Starlette(), "on_event")` is
  `False`). There's no clean post-hoc shutdown hook to close the agent's shared internal-API
  `httpx.AsyncClient` without reaching into `agent_kit`'s own internal `create_app(service)`
  lifespan. Decision: don't try — the client lives for the sidecar process's lifetime, which is
  fine for a single-process container. Re-evaluate only if `agent_kit` ever exposes its own
  extensible lifespan hook.
- **`agent/` needed `httpx` added as an explicit direct dependency** (`uv add httpx` from
  `agent/`) even though it was already pulled in transitively via `llm_kit` — the rule (see
  "Dependency management" above) is about not hand-editing versions, not about avoiding `uv add`
  for something already present transitively; `agent/tools/client.py` imports it directly. Same
  for `pytest`/`pytest-asyncio` as `--dev` deps (`agent/tests/` didn't exist before M4).
- **SQLAlchemy JSON-column mutation must reassign a new dict, not mutate in place.** Both
  `/internal/profile/update-section` and `/internal/profile/add-item` do
  `profile.data = {**profile.data, section: new_value}` — never `profile.data[section] = ...`
  followed by `db.commit()`. The latter mutates the same Python object SQLAlchemy already has
  cached and won't be detected as a change without `MutableDict`/`flag_modified`; reassigning a
  new dict object is the simplest way to get correct change-detection on a plain `JSON` column.
- **`record_clarification` is not its own backend endpoint.** It's implemented agent-side as a
  thin wrapper tool that calls `/internal/profile/add-item` with `section="enrichment",
  item={"key": key, "value": value}` — reusing the same validation (against `EnrichmentItem`) and
  version-bump logic as every other list-section append, rather than adding a fourth internal
  route.
- **Conversation ids must be namespaced by `user_id` before reaching the sidecar.** agent_kit's
  session store is keyed globally by `conversation_id` and raises `UnauthorizedError` on
  cross-user access to the same id — since `AgentPanel` uses fixed, predictable ids (`"profile"`,
  `` `job:${jobId}` ``) so that revisiting a page resumes the same thread, two different users
  would otherwise collide on the exact same upstream conversation. `chat.py`'s proxy prepends
  `f"{user_id}:"` before opening the upstream WS; `/internal/context` strips it back off (along
  with an optional `.{n}` "new chat" generation suffix) to recover the mode (`profile` vs.
  `job:{id}`).
- **Tool-call argument JSON schemas are a different, more permissive code path than
  `response_model=` structured-output extraction** — the M2 "compiled grammar is too large" 400
  was specific to Anthropic's constrained-decoding grammar compiler for `llm.invoke(...,
  response_model=...)`. `update_profile_section`'s `value` parameter is deliberately left
  type-unconstrained in its JSON schema (works for a `contact` object, a `summary` string, or a
  list-of-objects section) with no grammar-size issues — don't assume the same ceiling applies to
  tool parameter schemas.

### Post-build fixes (found after the M4 acceptance pass, via real user testing)

- **React callback props read inside a `useEffect` with a narrow dependency array go stale —
  route them through a ref.** `AgentPanel`'s WS-connect effect depends only on `[conversationId]`,
  so its `onFrame` closure originally captured whatever `onToolResult` prop existed at that
  effect's *last run* (mount, or a `conversationId` change) and kept calling that exact function
  forever, even though the parent (`ProfilePage`) redefines `handleAgentToolResult` fresh on every
  render (it's not `useCallback`'d) closing over the current `profile` state. Symptom: the agent
  added a project via `add_profile_item`, the profile visibly updated (because `setProfile` itself
  is a stable setter, unaffected by staleness), but the "highlight the changed section" logic
  silently no-opped, because the stale closure's `profile` was permanently `"loading"` from the
  very first render. Fix: `onToolResultRef = useRef(onToolResult)` kept current via a separate
  `useEffect(() => { onToolResultRef.current = onToolResult }, [onToolResult])`, and call
  `onToolResultRef.current?.(...)` inside the frame handler instead of the prop directly. **Watch
  for this pattern anywhere a callback prop is invoked from inside an effect whose dependency
  array doesn't include that prop** — it will silently reference stale outer state indefinitely,
  with no error, no warning, just quietly-wrong behavior.
- **`position: sticky`, not a fixed-height flex row, is what actually keeps `AgentPanel` pinned
  while the right-hand pane scrolls.** The first attempt (`main`/wrapper divs all constrained to
  `h-[calc(100vh-3.5rem)]` with `min-h-0` + `overflow-y-auto` on the scrolling pane) is the
  textbook nested-flex-containment pattern, but getting every intermediate flex container's
  `min-h-0` exactly right is fragile and it still didn't hold in practice. Replaced with the
  simpler, more robust pattern: the page scrolls normally (no artificial height ceiling anywhere),
  and the agent-panel column is `sticky top-[4.5rem] h-[calc(100vh_-_5.5rem)]` (4.5rem clears the
  `h-14` sticky nav header + the page's own `p-4` top padding; 5.5rem leaves a matching bottom
  gap) — `profile/page.tsx` and `jobs/[id]/page.tsx` both use this. **Tailwind arbitrary-value
  `calc()` needs underscores in place of spaces** (`calc(100vh_-_5.5rem)`, not
  `calc(100vh-5.5rem)`) — Tailwind's own escaping convention, and some browsers are stricter than
  others about bare-`calc()`-without-whitespace being technically invalid CSS.
- **The frontend transcript is client-side-only persistence, not a real conversation-history
  fetch.** `AgentPanel`'s `messages` React state used to reset to `[]` on every mount, so
  navigating away from `/profile` and back showed an empty chat even though the underlying
  agent_kit session (same namespaced `conversationId`) was still alive server-side and the agent
  kept replying with full context of the "invisible" prior turns. Fixed by mirroring the
  transcript to `localStorage` keyed by `messagesKey(conversationId)` (load on mount/reconnect,
  write on every update, via a `send()`/`updateMessages()` wrapper). This is per-browser only — a
  different browser or cleared storage shows an empty transcript on first load despite the agent
  still remembering everything. True cross-device history would need a new internal/backend
  endpoint to replay agent_kit's stored turns; not built, since agent_kit's working-memory store
  wasn't explored for a turn-by-turn replay API during M4.
- **Profile sections are collapsible with auto-expand-on-highlight**, not always-expanded.
  `SectionCard`/`EnrichmentSection` (`profile/page.tsx`) each hold local `open` state (chevron
  toggle in the header) and force `setOpen(true)` via `useEffect` when their `highlighted` prop
  flips true — added specifically because a just-updated section could otherwise be invisible
  behind a collapsed card once collapsing was added.
- **`react-markdown` renders assistant/user text**, with a custom compact `components` map in
  `agent-panel.tsx` (tight margins on `p`/`ul`/`ol`, styled `strong`/`code`/`a`) — the project has
  no `@tailwindcss/typography` plugin, and react-markdown's default HTML output carries
  full-document-sized block margins that look wrong in a narrow chat bubble.
- **`npm audit`'s 2 moderate `postcss` vulnerabilities (pre-dating M4) were fixed via
  `overrides`, not `npm audit fix --force`.** They were in `next`'s own bundled copy
  (`node_modules/next/node_modules/postcss@8.4.31`) — `next@16.2.9`'s own `package.json` pins
  `"postcss": "8.4.31"` as an **exact** version (no range), so plain `npm install`/dedupe can
  never lift it to a patched version on its own, and `npm audit fix --force` only knew how to
  "fix" it by downgrading `next` itself to `9.3.3` (a real breaking change — do not do this). The
  correct fix, per this file's own security-philosophy rule ("use overrides to force patched
  transitive deps"): add `"overrides": {"postcss": "^8.5.16"}` to `frontend/package.json` (must
  match/be compatible with the existing direct `postcss` dependency's range — npm's `overrides`
  validation rejects an override that conflicts with a direct dependency), then `npm install`.
  This forces every nested `postcss` copy (including next's) to dedupe to the same patched
  top-level instance — confirmed via `npm ls postcss` (no more nested copy at all) and a clean
  `npm run build` afterward (Next's CSS/Turbopack pipeline is unaffected by the newer patch
  version). `npm audit` now reports 0 vulnerabilities. **General lesson: before accepting
  `npm audit fix --force`'s suggested resolution, check whether the vulnerable package is pinned
  exactly by a parent dependency (`npm ls <pkg>`, or grep the parent's own `package.json`) — an
  `overrides` entry is very often the non-destructive fix, especially for a mature, API-stable
  tool like postcss where a transitive minor/patch bump is safe.**

## Gotchas encountered during M5

- **RenderCV v2.8 renders via Typst, not LaTeX/TinyTeX — this contradicted SPEC.md's and this
  file's own original M5 plan.** `docs/rendercv.md` (the reference doc itself) says so explicitly,
  and reading the installed package confirmed it: `rendercv.renderer.pdf_png` imports `typst` (the
  `typst-py` Rust-based compiler, a prebuilt-binary wheel) and `rendercv_fonts` (bundled font
  assets) — no `.tex` output exists at all. Practically this is a *simplification*: no system LaTeX
  toolchain to provision, just two pip packages. But it means `rendercv>=2.8` alone isn't enough —
  the plain (non-`[full]`) install is missing the compiler/fonts entirely
  (`ModuleNotFoundError: No module named 'rendercv_fonts'` at import time, with rendercv's own error
  pointing at the fix). Fixed via `uv add "rendercv[full]"` — pulls in `typst` (`manylinux_2_17_x86_64`
  wheel — portable, no apt-get needed even in `python:3.13-slim`) and `rendercv-fonts` (pure
  `py3-none-any` wheel). **If you see `rendercv`-related `ModuleNotFoundError`s, check the `[full]`
  extra first**, not a missing system package.
- **RenderCV has a clean in-process Python API — don't shell out to the CLI.**
  `rendercv.schema.rendercv_model_builder.build_rendercv_dictionary_and_model(yaml_text,
  input_file_path=...)` → `(dict, RenderCVModel)`, then `rendercv.renderer.typst.generate_typst(model)`
  → `rendercv.renderer.pdf_png.generate_pdf(model, typst_path)`. This is exactly the pipeline
  `rendercv render` itself calls internally (traced via `cli/render_command/run_rendercv.py`) — using
  it directly gives real Python exceptions instead of CLI output parsing. **Both plain YAML syntax
  errors and schema-validation errors raise the same `RenderCVUserValidationError`** — the only way
  to tell them apart is `all(e.schema_location is None for e in exc.validation_errors)` (syntax
  errors have no schema location; schema errors do). `backend/app/rendercv/compile.py`'s `stage`
  field ("yaml" vs "schema" vs "render") is derived from exactly this check.
- **`generate_typst`/`generate_pdf` still need a real file on disk for path resolution**
  (`rendercv_model._input_file_path`, used for output-path placeholders and photo resolution), even
  though `build_rendercv_dictionary_and_model` itself only needs the YAML as a string. `compile_pdf`
  writes `source_text` into a `tempfile.TemporaryDirectory()` first, for this reason alone — nothing
  is ever read back from disk except the final PDF bytes, and the whole directory is discarded on
  exit (this is also what keeps PDFs from ever touching the file store — see the DB-only-storage
  decision below).
- **RenderCV's `Cv` model has no top-level `summary` field** — only `sections: dict[str, list[Entry]]`.
  A tailored professional summary has to become its own section using `TextEntry` (a section whose
  value is a list of plain strings): `sections: {"Summary": ["<summary text>"]}`. Caught by a unit
  test in `test_rendercv.py` that would otherwise have silently produced YAML which never surfaced
  the summary at all (extra dict keys are ignored by RenderCV's `BaseModelWithoutExtraKeys` in some
  contexts, so a naive `cv["summary"] = ...` doesn't even error — it just vanishes).
- **`agent_kit`'s `Tool` handler signature is `(user_id, arguments) -> str` only — no
  `conversation_id`.** Confirmed by reading `agent_kit/tools/base.py`'s `ToolHandler` type alias and
  `registry.py`'s `tool.handler(user_id, call.arguments)` call site. This matters because the
  original M5 plan assumed `draft_cv` could derive its target job from `conversation_id` the same way
  `system_prompt_fn` does (`_strip_namespace` in `internal/context.py`) — it can't, since only
  `system_prompt_fn` receives `conversation_id`. Fixed by making `job_id` an explicit required tool
  argument instead; this costs nothing because the job's id is already shown to the model in plain
  text in the job-mode context block (`f"Job posting (id={job.id})..."`), so the model just echoes it
  back. **If a future tool seems to need to know "what conversation/job am I in," it can't read that
  from anywhere except values already present in the injected per-turn context — there is no hidden
  channel.**
- **Real, E.164-format-valid phone numbers can still fail RenderCV's *validity* check** — its
  underlying `phonenumbers`-based validator rejects some region/exchange combinations as not-a-real-
  number even though they match `+<countrycode><digits>` syntactically (e.g. numbers with reserved
  NANP area codes). `build.py`'s own `_PHONE_RE` is deliberately just a syntactic E.164 pre-filter
  (format-valid → passed through), not a full validity check — RenderCV's own schema validation at
  compile time is the intended final gate (surfaces as a `"schema"`-stage `CompileError` the user can
  fix in the editor), and that's by design, not a bug: re-implementing full phone-number validity
  checking in `build.py` would just duplicate logic RenderCV already does correctly. (This only bit
  the test suite, which used a fictional `555`-area-code number for a "should compile successfully"
  fixture — fixed by switching to `+14155552671`, a number widely used in phone-library test suites
  specifically because it validates.)
- **SQLite's `DateTime(timezone=True)` columns come back tz-naive on read**, same as the existing
  `app/auth/sessions.py` gotcha (`session.expires_at.replace(tzinfo=timezone.utc)`) — the M5 profile
  version debounce check (`datetime.now(timezone.utc) - newest.created_at`) hit the identical
  `TypeError: can't subtract offset-naive and offset-aware datetimes` until given the same
  `.replace(tzinfo=timezone.utc)` treatment in `db/profile_history.py`. **Any new code comparing a
  DB-read datetime against `datetime.now(timezone.utc)` needs this — it is not automatic just because
  the column is declared `timezone=True`.**
- **`docs/` needed a new volume mount into the `backend` container** — before M5, only `agent`
  mounted `./docs:/app/docs:ro` (for `good_resume.md`, embedded into the agent's system prompt).
  `backend/app/rendercv/tailor.py` also needs `good_resume.md` (as tailoring-prompt rules), so
  `docker-compose.yml`'s `backend` service now mounts `docs/` too. The local-dev (no-Docker) path
  resolution in `tailor.py` mirrors `agent/bootstrap.py`'s `_find_good_resume` pattern — Docker
  candidate vs. repo-root-relative candidate — but one directory level deeper (`rendercv/tailor.py`
  vs. top-level `bootstrap.py`), so the parent-walk count differs; don't copy-paste the exact
  `Path(__file__).parent` chain between the two without checking each file's actual nesting depth.
- **DB-only document storage (privacy decision, made explicitly by the user during planning): no CV
  PDF, and no RenderCV/Typst intermediate file, is ever written to the persistent file store.**
  Only `documents.source_text` (the RenderCV YAML) lives in the DB; PDFs are compiled into a
  `TemporaryDirectory` per request and streamed back as response bytes, never touching
  `backend/app/files.py`'s upload-storage machinery (which still exists, unchanged, for resume
  uploads only). This is also why `documents` has no `pdf_path` column, unlike SPEC §7's original
  plan — there is no path to record.
- **`draft_cv` is the only new M5 agent tool** — `compile_document`/`save_document` from SPEC's
  original §6.2 catalogue were deliberately not built. The CV panel (`cv-artifact.tsx`) sits directly
  next to the chat panel in the job-detail page, so compiling and saving are one-click UI actions
  against the public API (`POST /api/documents/compile`, `PUT /api/documents/{id}`) — adding
  redundant agent tools for the same two actions would be pure overhead under the write-only-tools
  philosophy (§6.1's "no read tools" reasoning generalizes: don't add a tool for something the user
  can already do with one click right next to the chat).
- **Grammar-limit smoke test confirmed `TailoredCV` fits in a single `llm.invoke()` call** — unlike
  `ProfileModel`, which needed the Part1/Part2 split. Verified against the real Anthropic API with an
  8-experience/4-project synthetic profile (502 completion tokens, well under `max_tokens: 4096`, no
  400). The schema's index-based selection (`{index, summary, highlights}` per item, 2-4 fields) is
  much lighter per-item than `ProfileModel`'s item schemas (7-9 fields) — this is *why* it fits, not
  a coincidence, but **re-run the same smoke-test pattern if `TailoredCV` ever grows heavier fields**,
  per the same rule already established for `ProfileModel`/`JobModel`. (The post-M5 `include` bool
  added to `TailoredExperienceEntry` — see next bullet — was re-smoke-tested against the real
  Anthropic API with the same 8-experience/4-project profile shape: no grammar-size 400, and the model
  correctly returned a decision for all 8 roles, setting `include=False` only on the single oldest
  (pre-2011) role while keeping all 7 more-recent ones — confirming both the schema fits and the
  prompt's "only drop old, never recent" instruction is followed in practice.)
- **Post-M5: experience & education are include-all, not LLM-selectable — silent omission was a bug.**
  Original M5 made `TailoredCV.experience`/`.education` pure index-*selections*, so the model could
  drop an entire job or degree just by not returning its index (unexplained employment gaps / missing
  degrees). Now: `build.py`'s `_build_experience_section` iterates **every** profile experience in
  profile order and `_build_education_section` iterates **every** education entry; both fall back to
  the profile's own summary/highlights when the model returns no rewrite for that index (so nothing is
  ever silently lost). Experience carries an explicit per-role `include` flag (`TailoredExperienceEntry`,
  default `True`) — a drop is honored **only** when `include=False` AND `_role_is_recent()` is false
  (server-side floor: ongoing / ended-within-`_RECENT_YEARS`=5 / undatable ⇒ always kept, overriding
  the model). The tailoring prompt tells the model to set `include=false` only for early unrelated
  roles >5 years old, never recent ones. Projects/publications/extras stay presence-based selection
  (legitimately skippable). Facts (dates/company/institution/degree) were already copied verbatim by
  index — that never changed; this fix is purely about **presence**, plus one prompt line forbidding
  fabricated numbers/dates/employers in the free-text bullets (the only remaining hallucination
  surface). **Design principle: the LLM tailors and may explicitly justify dropping an old role; the
  human curates (deletes roles manually in the YAML editor). Silent omission is never allowed.**
- **Full `docker compose up` was not verified in the environment this milestone was implemented in**
  — Docker wasn't reachable (WSL2 without the Docker Desktop WSL integration enabled). Confidence
  that the Docker build will still work rests on inspecting the installed wheels directly: `typst` is
  tagged `manylinux_2_17_x86_64`/`manylinux2014_x86_64` (portable to any glibc≥2.17 Linux, which
  `python:3.13-slim`/Debian satisfies) and `rendercv-fonts` is a pure-Python `py3-none-any` wheel —
  neither needs anything beyond what `uv pip install --system -e .` already does in the existing
  Dockerfile. **This is inference from wheel metadata, not a live Docker build — re-verify with an
  actual `docker compose up` before relying on it for a real deployment.**

## Gotchas encountered during M6

- **Resolved SPEC §8.4's "TBD at M6 planning time" typesetting decision: the cover letter reuses
  the CV's RenderCV/Typst pipeline instead of a second toolchain.** The alternative considered (a
  dedicated Typst letter template with true business-letter layout) was rejected — it would need a
  second compile path (`typst.compile` called directly, dispatched on `documents.source_format`)
  and a second editing surface, plus manual work to match the CV's theme/fonts. Reusing RenderCV
  means the letter is just a `cv:` document whose `sections` has one `TextEntry` (plain-string)
  entry — `compile_pdf`, the CodeMirror editor, the `<iframe>` preview, and append-only versioning
  are **all reused completely unchanged**; the letter automatically matches the CV's theme because
  both pass the same `rendercv_theme()` into `design.theme`. Confirmed by rendering a real letter
  through the actual Typst compiler and inspecting the PDF: the header (name/contact) is identical
  in style to the CV, and the "Cover Letter" section renders as a normal RenderCV section title —
  reads as a clean, professional single-column document, not as an awkward CV imitating a letter.
- **`_build_contact` (originally private to `build.py`) is imported directly by `letter.py`** rather
  than duplicated or made public — both the CV and the cover letter need the exact same verbatim
  contact-field mapping (same phone/website/social-network validation), and Python doesn't enforce
  the underscore-prefix privacy convention within a package. Similarly, the `good_resume.md` loader
  that used to live inline in `tailor.py` was extracted into `app/rendercv/rules.py`
  (`good_resume_rules()`) so `letter.py` doesn't duplicate the Docker-vs-repo-root path-resolution
  logic — `tailor.py` now imports it too.
- **`TailoredCoverLetter` is deliberately flat** (all scalars + one `list[str]`, no nested
  list-of-object fields) for the same reason `JobModel` is — this kept it under Anthropic's
  structured-output grammar-size limit in a single `llm.invoke()` call, confirmed against the real
  API (no 400, no Part-split needed). If a future revision adds nested per-paragraph structure
  (e.g. a `{tone, paragraph}` object instead of a bare string), re-run the grammar-size smoke test
  per the established `ProfileModel`/`JobModel`/`TailoredCV` precedent rather than assuming margin.
- **The tailoring prompt's paragraph count is a soft target, not a hard schema constraint** — since
  `body_paragraphs` is just `list[str]`, nothing stops the model from collapsing everything into a
  single paragraph on a given sampling (observed once in ad hoc smoke-testing, though a repeat run
  with the same inputs produced the intended 3–4 paragraph §12 structure — company-first, role
  understanding, JD-tied qualifications with real proof, closing). This is normal LLM sampling
  variance for free-form prose (unlike `TailoredCV`'s structured index-based fields, there's no
  deterministic fallback to enforce paragraph count) — not a bug to fix, just worth knowing if a
  generated letter ever reads as one dense block: regenerating typically produces the intended
  structure.
- **No `bold_keywords` setting on the cover-letter YAML**, unlike the CV — `build_cover_letter_yaml`
  intentionally omits `settings.bold_keywords` (which `build_rendercv_yaml` sets from the job's
  `keywords[]`) because auto-bolding scattered keywords inside prose paragraphs reads as keyword
  stuffing in a letter, whereas it's a legitimate scanning aid in bullet-point CV highlights.
- **The cover-letter date line is computed in Python (`datetime.now(timezone.utc)`), not requested
  from the LLM** — `TailoredCoverLetter` has no date field; letting the model state "today's date"
  would be an unnecessary hallucination surface (it doesn't reliably know the true current date)
  for a fact Python already has correctly. Formatted as `"{Month} {day}, {year}"` (e.g. "July 4,
  2026") via manual `strftime` component assembly rather than platform-specific format codes —
  `%-d` (no leading zero) works on Linux/Mac `strftime` but is not portable to Windows, and since
  the day number was needed without a leading zero, `f"{now:%B} {now.day}, {now:%Y}"` sidesteps the
  portability question entirely rather than relying on a flag that happens to work in the
  `python:3.13-slim` Docker image.

## Gotchas encountered during M7

- **`apscheduler` was already a declared backend dependency before M7 started** (pre-staged at
  skeleton time, `backend/pyproject.toml`), and `config.yaml`'s `app.tracking` block
  (`stale_after_days`/`auto_reject_after_days`) already existed too — but neither had any code
  reading/using them until M7. Same for `documents.is_finalized` and append-only versioning: both
  were built in M5 with a docstring explicitly anticipating "a finalized application (M7) can
  snapshot the exact document submitted." **When picking up a milestone, grep for fields/deps that
  look unused — they're often intentionally pre-staged, not dead code.**
- **The scheduler + startup backfill must be skipped under pytest.** `main.py`'s lifespan calls
  `backfill_applications(SessionLocal())` and starts the `BackgroundScheduler` directly — both bypass
  FastAPI's `get_db` dependency entirely (they construct their own session), so the test suite's
  `app.dependency_overrides[get_db]` override (which points at the in-memory test DB) has no effect
  on them. Without a guard, every test run using the `client` fixture would hit the **real on-disk**
  `app/data/hirable.db` — creating real `Application` rows for whatever `Job` rows exist there from
  manual dev testing, and spinning up/tearing down a background thread on every single test. Fixed
  with a `_under_pytest()` check (`"PYTEST_CURRENT_TEST" in os.environ`, a standard pytest-set env
  var) that skips both under test. **Any future lifespan code that talks to the DB via its own
  `SessionLocal()` (not `Depends(get_db)`) needs the same guard** — it's invisible to the existing
  `app.dependency_overrides` pattern.
- **`db.commit()`'s default `expire_on_commit=True` already reproduces the SQLite tz-naive-on-read
  gotcha within a single test — no cross-session trick needed.** Initially assumed a test would need
  to force a fresh query (e.g. `db.expire_all()`) to see a naive datetime, since the same Python
  object/session is reused across a whole test via the `db_session` fixture. Empirically confirmed
  otherwise: SQLAlchemy's default sessionmaker expires all attributes on every `commit()`, so the
  very next attribute access triggers a real SELECT and comes back tz-naive — meaning
  `apply_automation`'s `.replace(tzinfo=timezone.utc)` fix (same pattern as
  `auth/sessions.py`/`db/profile_history.py`) is exercised by the time-travel tests exactly as
  written, with a plain `application.last_activity_at = <backdated aware datetime>; db.commit()`.
- **Automation must not reset `last_activity_at` on its own writes, or the reject threshold would
  never fire.** `transition_stage(..., actor=...)` only updates `last_activity_at`/`auto_stale_at`
  when `actor != "automation"` — a Stale→Rejected transition triggered by the scheduler must not
  "touch" the application in a way that pushes the reject clock forward, since that clock is measured
  from the *original* inactivity, not from the automation's own intervention. Covered by
  `test_automation_does_not_reset_last_activity` in `test_applications.py`.
- **`apply_automation` checks the auto-reject threshold *before* the stale threshold**, so an
  application idle long enough to blow past both thresholds in one scheduler gap (e.g. the server was
  down for 40 days) goes straight to `Rejected` in a single pass, rather than landing on `Stale` and
  waiting for the *next* run to notice it's also past the reject threshold.
- **Applications are auto-created 1:1 with jobs — there is no manual "create application" step and
  no `/applications/{id}` detail page.** `job_id` carries a `unique=True` constraint enforcing the
  1:1. `api/jobs.py`'s `add_job` calls `get_or_create_application` right after committing the new
  job row; `backfill_applications` (idempotent — an outer-join-for-missing query, not a blind insert)
  covers jobs that existed before M7 shipped. Because of the 1:1, the frontend's `/applications`
  board/table and the job-detail page's `ApplicationStatusCard` are two views onto the *same*
  underlying row — there's no separate detail route, kanban cards and table rows link straight to
  `/jobs/{job_id}`.
- **The application-document snapshot stores only the `Document` row id, never a content or PDF
  copy** — consistent with M5's DB-only, no-PDF-persistence privacy decision. `finalize_documents`
  looks up the latest CV/cover-letter `Document` for the job (same `order_by(version.desc()).first()`
  pattern as `rendercv/service.py`'s `_next_version`), flips `is_finalized=True` on that exact row,
  and records an `ApplicationDocument(document_id=...)` — nothing new is written to the file store or
  compiled to PDF at submit time; the PDF is still produced on demand from that row's `source_text`,
  same as any other version. This is also what makes submit idempotent for free: calling it again
  while `submitted_at` is already set skips `finalize_documents` entirely (checked in
  `transition_stage`), so a second submit can't create a duplicate `ApplicationDocument` row.
- **`GET /api/applications` gained an optional `job_id` query param** (mirroring
  `GET /api/documents?job_id=...&type=...`) specifically because the job-detail page only has a
  `job_id` in hand, never an `application_id` — `frontend/lib/api.ts`'s `apiGetApplicationForJob`
  wraps this into "fetch the (at most one) application for this job." No new backend route was
  needed; the existing list endpoint's `user_id` scoping already covers it.
- **The kanban board only needed `@dnd-kit/core` + `@dnd-kit/utilities`, not `@dnd-kit/sortable`.**
  `@dnd-kit/sortable` is for reordering items *within* a list; this board only moves cards *between*
  stage columns (order within a column is irrelevant — applications aren't sorted against each other
  within the same stage), so plain `useDraggable`/`useDroppable`/`DndContext` is sufficient. Installed
  `@dnd-kit/sortable` initially per the original plan, then removed it after confirming it added
  nothing (`npm uninstall @dnd-kit/sortable`) — **don't install a satellite package on a library's
  name-brand recognition alone; check whether the specific interaction (cross-column vs. in-column
  reordering) actually needs it.** `PointerSensor` needs an `activationConstraint: { distance: 8 }`
  so a plain click on a card (e.g. its `<Link>` to the job) doesn't get swallowed as a zero-distance
  drag.
- **Stage is stored as a plain `String` column with an inline comment listing valid values**
  (`Application.stage`), not a SQLAlchemy `Enum` — matches the existing convention for
  `Document.type`/`ProfileVersion.source`. Validation happens at the API/internal boundary
  (`app/applications/stages.py`'s `STAGES` tuple + `validate_stage`), not the DB layer.

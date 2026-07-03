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
`SPEC.md`. Implementation is milestone-based (M0–M9); **M0–M4 are complete** (three-service
skeleton + one-command setup; full auth + session management + admin console + UI redesign;
resume upload → master profile; job ingest by URL/paste → shortlist; contextual agent panels
with profile-enrichment write tools — see SPEC.md §6.0 for the chat-tab → embedded-panel pivot).

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
| `backend/tests/` | pytest suite: auth lifecycle, isolation, admin cascade, 403 guards, WS auth, profile CRUD, job ingest/CRUD/isolation/needs_paste, internal API secret+context+isolation |
| `backend/app/llm/` | `client.py` (build LLMClient from config), `deps.py` (FastAPI `get_llm` dep), `schemas.py` (ProfileModel, JobModel) |
| `backend/app/parsing/` | `extract.py` (docling + LaTeX strip), `profile.py` (resume LLM structured extraction), `jobs.py` (trafilatura fetch + job LLM structured extraction) |
| `backend/app/files.py` | Per-user upload storage: `/app/data/uploads/{user_id}/{uuid}.{ext}` |
| `backend/app/api/profile.py` | `POST /resume`, `GET /`, `PUT /` — all scoped to `current_user` |
| `backend/app/api/jobs.py` | `POST /` (url/paste ingest + `needs_paste` signal), `GET /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` — all scoped to `current_user` |
| `backend/app/internal/` | Secret-gated `/internal/*` routes (M4): `context.py` (`system_prompt_fn` backend — builds the per-turn profile/job block from `conversation_id`'s mode), `profile.py` (`update-section`, `add-item`), `deps.py` (`verify_internal_secret`) |
| `frontend/app/(app)/profile/` | Split-screen: `AgentPanel` (conversationBase=`"profile"`) + resume dropzone / section-by-section profile editor; live-refreshes + highlights sections the agent just wrote |
| `frontend/app/(app)/jobs/` | Job shortlist list page (add by URL/paste, table) + `[id]/` split-screen detail/edit page (`AgentPanel` with conversationBase=`` `job:${id}` ``) + M5 artifact placeholder |
| `frontend/components/agent-panel.tsx` | Reusable chat panel (M4): WS connect, ordered text/tool_call/tool_result message parts (markdown-rendered via `react-markdown`), model picker, "new chat" generation-suffix button, one-click `starterPrompt` chip, localStorage transcript persistence keyed by `conversationId` |
| `frontend/components/ui/textarea.tsx` | Native textarea with base-nova Tailwind styling |
| `agent/bootstrap.py` | Builds `AgentService` with `extra_tools`/`system_prompt_fn`, embeds `good_resume.md`, secret middleware, /health |
| `agent/tools/` | `client.py` (shared internal-API `httpx.AsyncClient`), `profile.py` (the 3 write tools), `context.py` (`build_system_prompt_fn`) |
| `frontend/app/(app)/` | Authenticated route group: profile, jobs, admin (layout enforces session cookie) — no chat route (see CLAUDE.md's M4 notes) |
| `frontend/app/(auth)/` | Auth route group: login, signup (layout redirects if already authed) |
| `frontend/components/app-shell.tsx` | Sticky nav (Profile/Jobs/Admin) + theme toggle + user dropdown |
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
| `contact.headline` | `cv.headline` |
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
| M5 — CV generation + editor + PDF | Pending | TinyTeX install deferred to here |
| M6 — cover letter | Pending | |
| M7 — application tracking + automation | Pending | |
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

- **DocumentConverter is expensive — initialize once at startup.** docling's model initialization
  takes seconds and happens per-upload if done lazily. In `backend/app/main.py`, initialize
  `DocumentConverter()` once in the FastAPI lifespan (`app.state.docling_converter = ...`),
  inject via a FastAPI dependency (`app/parsing/deps.py`), and pass to extraction functions.
  This matches the pattern already used for `LLMClient` — first resume upload is slow (one-time
  model load), but subsequent uploads are fast.
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
- **`npm audit` reports 2 moderate vulnerabilities in Next's own bundled `postcss`
  (`node_modules/next/node_modules/postcss`) that predate all M4 frontend work** — confirmed via
  `git stash` + re-running `npm audit` on the pre-M4 tree. `npm audit fix --force` wants to
  downgrade `next` to `9.3.3` (a huge breaking change from Next 16), so this was deliberately left
  alone rather than "fixed" destructively. Don't assume a future `npm audit` finding here was
  introduced by whatever you're currently working on without checking history first.

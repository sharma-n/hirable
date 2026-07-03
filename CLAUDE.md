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
`SPEC.md`. Implementation is milestone-based (M0–M9); **M0–M3 are complete** (three-service
skeleton + one-command setup; full auth + session management + admin console + UI redesign;
resume upload → master profile; job ingest by URL/paste → shortlist).

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
  `.revoke(...)`. `tools.default_allowed` in `config.yaml` is the global fallback.
- **Tool injection (M4):** custom tools are registered via `AgentService` after app creation.
  The exact API for injecting tools into `create_app_from_yaml`'s served instance needs to be
  confirmed in M4 — ask the user rather than guessing.
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
| `backend/app/api/chat.py` | WS proxy: browser ↔ backend ↔ sidecar; injects user_id + secret |
| `backend/app/auth/` | `password.py` (argon2), `sessions.py` (token lifecycle), `dependencies.py` (FastAPI guards) |
| `backend/app/db/` | SQLAlchemy engine, Base, User + Session models, `create_all()` migration runner |
| `backend/app/schemas.py` | Pydantic request/response schemas (`SignupRequest`, `UserOut`, …) |
| `backend/tests/` | pytest suite: auth lifecycle, isolation, admin cascade, 403 guards, WS auth, profile CRUD, job ingest/CRUD/isolation/needs_paste |
| `backend/app/llm/` | `client.py` (build LLMClient from config), `deps.py` (FastAPI `get_llm` dep), `schemas.py` (ProfileModel, JobModel) |
| `backend/app/parsing/` | `extract.py` (docling + LaTeX strip), `profile.py` (resume LLM structured extraction), `jobs.py` (trafilatura fetch + job LLM structured extraction) |
| `backend/app/files.py` | Per-user upload storage: `/app/data/uploads/{user_id}/{uuid}.{ext}` |
| `backend/app/api/profile.py` | `POST /resume`, `GET /`, `PUT /` — all scoped to `current_user` |
| `backend/app/api/jobs.py` | `POST /` (url/paste ingest + `needs_paste` signal), `GET /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` — all scoped to `current_user` |
| `frontend/app/(app)/profile/` | Resume dropzone + section-by-section profile editor (upload, edit, re-upload) |
| `frontend/app/(app)/jobs/` | Job shortlist list page (add by URL/paste, table) + `[id]/` detail/edit page |
| `frontend/components/ui/textarea.tsx` | Native textarea with base-nova Tailwind styling |
| `agent/bootstrap.py` | `create_app_from_yaml` wrapper + secret middleware + /health |
| `frontend/app/(app)/` | Authenticated route group: chat, admin, profile (layout enforces session cookie) |
| `frontend/app/(auth)/` | Auth route group: login, signup (layout redirects if already authed) |
| `frontend/components/app-shell.tsx` | Sticky nav + theme toggle + user dropdown |
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
| M4 — agent tools + clarifying-question loop | Pending | Tool injection API TBD |
| M5 — CV generation + editor + PDF | Pending | TinyTeX install deferred to here |
| M6 — cover letter | Pending | |
| M7 — application tracking + automation | Pending | |
| M8 — analytics dashboard | Pending | |
| M9 — polish, hardening, docs | Pending | |

---

## Local dev (no Docker)

```bash
# Agent (port 8001 to avoid clash with backend)
cd agent && ANTHROPIC_API_KEY=... AGENT_INTERNAL_SECRET=dev-secret \
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
  `/chat` if it is present. This is the modern, non-deprecated pattern — it runs in the
  Node.js runtime (not the Edge runtime), has full access to the cookie jar, and does not
  require any matcher config.

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

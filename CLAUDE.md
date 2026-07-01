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

## What this is
A self-hosted, multi-user job-application assistant (resume parsing → master profile → tailored
CV/cover letter generation via an agentic chat → application tracking + analytics). Full spec in
`SPEC.md`. Implementation is milestone-based (M0–M9); **M0 is complete** (three-service skeleton,
one-command Docker setup, chat round-trip working).

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
| `backend/app/api/chat.py` | WS proxy: browser ↔ backend ↔ sidecar; injects user_id + secret |
| `backend/app/db/` | SQLAlchemy engine, Base, stub models, `create_all()` migration runner |
| `agent/bootstrap.py` | `create_app_from_yaml` wrapper + secret middleware + /health |
| `frontend/app/chat/page.tsx` | M0 placeholder chat UI |
| `frontend/lib/api.ts` | Typed WS client helper |

---

## Milestone status

| Milestone | Status | Notes |
|---|---|---|
| M0 — skeleton + chat round-trip | **Done** | Chat round-trip verified locally |
| M1 — auth, sessions, admin | **Done** | argon2, httpOnly cookie sessions, first-user admin, admin console, full UI redesign (Tailwind v4 + shadcn base-nova, dark mode, app shell) |
| M2 — resume upload → profile | Pending | |
| M3 — jobs shortlist | Pending | |
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

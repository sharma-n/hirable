# hirable

A self-hosted, multi-user web app that helps you write, tailor, and track job applications.

## Quickstart

1. **Clone & configure**
   ```bash
   git clone <repo>
   cd hirable
   cp .env.example .env
   # Edit .env — set AGENT_INTERNAL_SECRET and ANTHROPIC_API_KEY
   # Edit config.yaml to change the LLM model/endpoint (defaults to claude-haiku-4-5)
   ```

2. **Start all services**
   ```bash
   docker compose up --build
   ```

3. **Open the app**
   - Frontend: http://localhost:3000
   - Chat test page: http://localhost:3000/chat
   - Backend health: http://localhost:8000/health

## Configuration

Two files, two concerns:

- **`.env`** — secrets and infrastructure only: `AGENT_INTERNAL_SECRET`, `ANTHROPIC_API_KEY`
- **`config.yaml`** — everything LLM/agent: model, endpoint, message format, tracking thresholds

To switch provider, edit the `llm_kit.llm` block in `config.yaml`:

| Provider | message_format | base_url | extra |
|---|---|---|---|
| Anthropic (default) | `anthropic` | `https://api.anthropic.com` | `chat_completions_path: /v1/messages` |
| OpenAI | `openai` | `https://api.openai.com` | remove `chat_completions_path` |
| Ollama (local) | `openai` | `http://host.docker.internal:11434` | remove `chat_completions_path` |
| vLLM / Together | `openai` | provider endpoint | |

## Architecture

```
[ Next.js :3000 ] ──REST/WS──▶ [ FastAPI :8000 ] ──WS──▶ [ harness_kit (internal) ]
                                  system of record              chat brain
```

The agent sidecar has **no published port** — it is only reachable from the backend on the internal Docker network.

## Local development (without Docker)

Run each service in a separate terminal. Prerequisites: Python 3.13+, Node 22+, `uv`.

**1. Agent sidecar**
```bash
cd agent
uv sync
ANTHROPIC_API_KEY=sk-ant-... \
AGENT_INTERNAL_SECRET=dev-secret \
INTERNAL_BASE_URL=http://localhost:8000 \
uv run uvicorn bootstrap:create_app --factory --port 8001 --reload
```

**2. Backend**
```bash
cd backend
uv sync
ANTHROPIC_API_KEY=sk-ant-... \
AGENT_INTERNAL_SECRET=dev-secret \
AGENT_BASE_URL=http://localhost:8001 \
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`AGENT_BASE_URL` overrides the `http://agent:8000` default in `config.yaml` so the backend reaches your locally-running sidecar.

**3. Frontend**
```bash
cd frontend
npm install
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000/chat to test the chat round-trip.

---

See `SPEC.md` for the full implementation spec and milestones.

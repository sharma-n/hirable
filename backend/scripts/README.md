# Backend scripts

## `seed_demo_data.py`

Creates a demo account with realistic application data for showcasing the M8 analytics dashboard.

### Quick start

```bash
cd backend
uv run python scripts/seed_demo_data.py
```

This will:

1. Create `app/data/hirable.db` (fresh database with all tables)
2. Create a demo user account:
   - **Email:** `demo@hirable.dev`
   - **Password:** `DemoPass123!`
   - **Role:** admin
3. Populate the account with:
   - **Master profile:** Jordan Kim (Staff ML Engineer from `examples/mle_engineer.yaml`)
   - **28 jobs:** Realistic MLE-target postings from FAANG, startups, and AI labs
   - **25 submitted applications** with:
     - A realistic 6-stage funnel: Applied (25) → Screen (15, 60%) → Technical (10, 40%) → Onsite (6, 24%) → Offer (3, 12%) → Accepted (1, 4%)
     - Response rate: ~64% (excluding automation-caused ghosting)
     - Offer rate: 12%
     - CV version performance: 8 apps with v2 revisions show ~87.5% response rate vs. 52.9% for v1-only
     - Company-type/location breakdowns for analytics
   - **3 draft applications** (in-progress shortlist)

### Features

- **Idempotent:** Run the script multiple times to reset the demo account cleanly
- **No LLM calls required:** Uses deterministic RenderCV assembly; no `ANTHROPIC_API_KEY` needed
- **Real data:** Generates actual, compilable RenderCV YAML documents and RenderCV-compliant cover letters
- **Automation events:** Includes synthetic `Stale` and `Rejected` (automation) transitions so analytics correctly excludes ghosting from response-rate calculations

### Then start the app

```bash
# Terminal 1: Agent (port 8001 locally)
cd agent
ANTHROPIC_API_KEY=... AGENT_INTERNAL_SECRET=dev-secret \
  INTERNAL_BASE_URL=http://localhost:8000 \
  uv run uvicorn bootstrap:create_app --factory --port 8001 --reload

# Terminal 2: Backend (port 8000)
cd backend
ANTHROPIC_API_KEY=... AGENT_INTERNAL_SECRET=dev-secret \
  AGENT_BASE_URL=http://localhost:8001 \
  uv run uvicorn app.main:app --port 8000 --reload

# Terminal 3: Frontend (port 3000)
cd frontend
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 npm run dev
```

Then open http://localhost:3000/login and log in with the demo credentials. Visit `/analytics` to see the seeded funnel and CV-version performance metrics.

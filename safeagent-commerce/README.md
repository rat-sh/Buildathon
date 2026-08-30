# SafeAgent Commerce
### Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce

> **A Validator-gated multi-agent commerce system where LLMs can only propose — a deterministic gate decides everything before money moves.**

---

## 💡 Quick Note on Natural AI Chat
> **Add your OpenAI key (`OPENAI_API_KEY=sk-...`) in `.env` for natural ChatGPT-style conversational replies.**
> The system combines ChatGPT-like conversational tone with search over the local product catalog (seeded from `data/products.json`).
> Without an API key, the system uses clean, deterministic fallback replies.

---

## Architecture Overview

```
Human / AI Buyer
      │
      ▼
Shopping Agent ──→ Catalog (real DB, never invented products)
      │
      ▼
Suggestion Agent (opt-in only, explicit accept required)
      │
      ▼
┌─────────────────────────────────────┐
│      VALIDATOR AGENT  ★             │  ← Deterministic Python only
│  1. Product exists + active         │    No LLM inside this gate
│  2. Price ≤ catalog price           │
│  3. Stock available                 │
│  4. Within spending limits          │
│  5. Add-ons explicitly accepted     │
│  6. Idempotency key unique          │
└──────────┬──────────────────────────┘
           │ HMAC-signed PASS token only
           ▼
    Payment Agent ──→ Razorpay Orders API (Test Mode)
           │
           ▼
    verify-payment OR webhook (HMAC verified) → mark_order_captured
           │
           ▼
    Audit Log (append-only, structured JSON events)
```

---

## Safety Guarantees

- ❌ No LLM can create a Razorpay order or alter prices/stock.
- ❌ No payment without Validator HMAC-signed PASS token (15-minute TTL).
- ❌ No auto-added upsell items.
- ❌ No audit log modification (append-only).
- ✅ HMAC verified before any webhook or client-side capture.
- ✅ Single idempotent capture path — stock decrements exactly once.
- ✅ Max 2 payment retries — then stops.
- ✅ Hard spending limits defined in code constants.

---

## Database: Supabase Postgres

**Production and demo deployments use Supabase Postgres**, not SQLite.

### Setup

1. Create a project at [supabase.com](https://supabase.com).
2. Go to **Settings → Database → Connection string → URI**.
3. Copy the **Transaction pooler** URI (port **6543**) and convert to asyncpg format:

```bash
postgresql+asyncpg://postgres.[project-ref]:[YOUR-PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres
```

4. Copy env template and fill in values:

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL, Razorpay TEST keys, APP_SECRET_KEY, etc.
```

5. Start the app — `init_db()` creates tables and seeds `data/products.json` if the catalog is empty:

```bash
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Notes:**
- Use **Transaction pooler (6543)** for the FastAPI app with asyncpg.
- Use **Session mode (5432)** only for one-off DDL/migrations if needed.
- Never commit `.env` or database passwords to git.
- **SQLite** is used only by `pytest` (see `backend/tests/conftest.py`) — not for running the app.

### Docker

```bash
cp .env.example .env   # DATABASE_URL must point to Supabase
docker compose up --build
```

The container runs the app only; the database lives on Supabase.

---

## Quick Start

```bash
# 1. Set up environment (Supabase DATABASE_URL required)
cp .env.example .env

# 2. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Run backend
cd backend
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` → Chat UI  
Open `http://localhost:8000/admin/audit` → Audit log viewer (HTML; API requires `X-Admin-Key`)  
Open `http://localhost:8000/docs` → API documentation

---

## Running Tests

```bash
cd backend
pytest -v
```

Tests use in-memory SQLite automatically — no Supabase connection required for CI.

---

## Known Limitations (Buildathon Scope)

| Area | Status |
|------|--------|
| Dual capture paths / stock double-decrement | **Fixed** — `mark_order_captured()` is the single idempotent path for webhook + verify-payment |
| SQLite as default DB | **Fixed** — Supabase Postgres is the primary/documented deployment DB |
| MCP-style catalog API | REST endpoints only (no full MCP server) |
| Currency | INR / paisa only |
| Refunds / chargebacks | Out of scope |
| Admin auth | `X-Admin-Key` header (demo-appropriate) |
| AP2 / ACP / x402 wire compliance | Not claimed |

---

*Built for Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce*

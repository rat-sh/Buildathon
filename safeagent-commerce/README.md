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
3. Copy the **Session mode** URI (port 5432) or **Transaction pooler** (port 6543) and convert to asyncpg:

```bash
# Session mode (init_db / first run — project dzajfadmwhexrcloytdr example):
postgresql+asyncpg://postgres:[PASSWORD]@db.dzajfadmwhexrcloytdr.supabase.co:5432/postgres

# Transaction pooler (6543 — recommended under concurrent load):
postgresql+asyncpg://postgres.dzajfadmwhexrcloytdr:[PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres
```

Optional Supabase CLI:

```bash
supabase login
supabase init
supabase link --project-ref dzajfadmwhexrcloytdr
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

### Fixed in this codebase

**Dual capture paths / stock update.** Previously `app/api/webhooks.py` (on `payment.captured` / `order.paid`) and `app/api/payment_verify.py` could both mark an order CAPTURED and cart PAID independently, but only the webhook decremented stock. **Fixed:** both paths now call `services/order_fulfillment.mark_order_captured()` — idempotent, stock decrements exactly once whether verify-payment, webhook, or both run.

**SQLite as the deployment database.** The app previously defaulted to `sqlite+aiosqlite:///./safeagent.db`. **Fixed:** runtime requires `DATABASE_URL=postgresql+asyncpg://…` (Supabase Postgres). SQLite is used only by `pytest` via `tests/conftest.py`.

### Intentional scope boundaries (not bugs)

**“MCP-style” means REST, not MCP.** Catalog routes are HTTP handlers shaped like tool calls for `ai_buyer/demo_buyer.py` — there is no JSON-RPC transport and no Model Context Protocol server underneath.

**INR / paisa only.** Every amount is integer paisa; there is no multi-currency ledger.

**No refund, dispute, or chargeback flow.** Explicitly out of scope for a track about growth and checkout, not the full payments lifecycle.

**PASS token is in-process HMAC, not a distributed mandate service.** Genuinely unforgeable within this architecture (HMAC over fields + 15-minute TTL), but not a standalone signed-mandate microservice that another service could independently verify — related to, but different from, AP2-style mandates.

**Admin auth is a shared secret (`X-Admin-Key`), not SSO/OIDC.** Appropriate for a buildathon demo, not for a real merchant ops team at scale.

**Demo catalog is seeded from `data/products.json`.** ~20 static products, not a live merchant inventory feed.

**AP2 / ACP / x402 wire compliance.** Not claimed for this submission.

### Quick reference

| Area | Status |
|------|--------|
| Dual capture / stock | **Fixed** — `mark_order_captured()` |
| Primary DB | **Fixed** — Supabase Postgres via `DATABASE_URL` |
| MCP-style catalog | REST only (by design) |
| Currency | INR / paisa only |
| Refunds / chargebacks | Out of scope |
| PASS token | In-process HMAC + TTL |
| Admin auth | `X-Admin-Key` (demo) |
| Catalog source | `data/products.json` seed |

---

*Built for Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce*

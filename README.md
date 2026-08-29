# SafeAgent Commerce
### Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce

> **A Validator-gated multi-agent commerce system where LLMs can only propose — a deterministic gate decides everything before money moves.**

---

## 💡 Quick Note on Natural AI Chat
> **Add your OpenAI key (`OPENAI_API_KEY=sk-...`) in `.env` for natural ChatGPT-style conversational replies.**
> The system combines ChatGPT-like conversational tone with real-time Amazon/Flipkart product catalog discovery.
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
           │ PASS token only
           ▼
    Payment Agent ──→ Razorpay Orders API (Test Mode)
           │
           ▼
    Webhook (HMAC verified) → Order state update
           │
           ▼
    Audit Log (append-only, structured JSON events)
```

---

## Five Agents

| Agent | Role | Uses LLM? | Touches Razorpay? |
|---|---|---|---|
| **Shopping** | NL → catalog search, ranked results | ✅ Yes | ❌ Never |
| **Suggestion** | Affinity-based upsell (1-2 items, opt-in) | ✅ Yes | ❌ Never |
| **Catalog** | MCP-style tool API for AI buyers | ❌ Pure Python | ❌ Never |
| **Validator** | Deterministic safety gate — PASS or BLOCK | ❌ Must be code | ❌ Never |
| **Payment** | Creates Razorpay order, handles retries | ❌ Pure Python | ✅ Only one |

---

## Validator Reason Codes

| Code | Meaning |
|---|---|
| `PASS` | All checks passed — payment may proceed |
| `ITEM_NOT_FOUND` | Product ID does not exist in catalog |
| `ITEM_INACTIVE` | Product exists but is_active = False |
| `PRICE_MISMATCH` | Charged price > current catalog price |
| `STOCK_OUT` | Requested quantity > available stock |
| `TX_LIMIT_EXCEEDED` | Cart total > per-transaction limit |
| `DAILY_LIMIT_EXCEEDED` | Daily spend ceiling would be breached |
| `ADDON_NOT_ACCEPTED` | Add-on in cart not explicitly accepted |
| `DUPLICATE_IDEMPOTENCY_KEY` | This idempotency key was already used |
| `CART_ALREADY_PAID` | Cart already paid or has a captured order |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Database | SQLAlchemy 2.0 + SQLite (dev) / PostgreSQL (prod) |
| Validation | Pydantic v2 |
| Payments | Razorpay Python SDK (Test Mode) |
| LLM | OpenAI / Groq (function calling only) |
| Frontend | HTMX + Jinja2 + minimal CSS |
| Deploy | Docker Compose |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/rat-sh/Buildathon.git
cd Buildathon/safeagent-commerce

# 2. Set up environment
cp .env.example .env
# Edit .env — add Razorpay TEST keys and OpenAI key

# 3. Install dependencies
pip install -r requirements.txt

# 4. Seed the database
python scripts/seed_db.py

# 5. Run
cd backend
uvicorn app.main:app --reload --port 8000

# Or with Docker:
docker-compose up --build
```

Open `http://localhost:8000` → Chat UI
Open `http://localhost:8000/admin/audit` → Audit log viewer
Open `http://localhost:8000/docs` → API documentation

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

Key test coverage:
- All 9 Validator failure modes
- Payment idempotency (duplicate key rejection)
- Webhook HMAC signature verification
- Catalog tool schemas

---

## AI Buyer Demo (AI-to-AI Path)

```bash
# In a separate terminal, with the server running:
cd ai_buyer
python demo_buyer.py
```

The demo buyer script:
1. Calls Catalog tools to search products
2. Constructs a structured `PurchaseRequest`
3. Submits it through the same Validator gate
4. Completes payment with no human interaction
5. Prints the structured audit trail

---

## Safety Guarantees

- ❌ No LLM can create a Razorpay order
- ❌ No payment without Validator PASS token
- ❌ No auto-added upsell items
- ❌ No audit log modification (append-only)
- ✅ HMAC verified before any webhook state change (no debug bypass)
- ✅ Max 2 payment retries — then stops
- ✅ Hard spending limits defined in code constants (not DB)

---

## Project Structure

```
safeagent-commerce/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── core/             # config, database, security, limits
│   │   ├── models/           # SQLAlchemy: product, cart, order, audit
│   │   ├── schemas/          # Pydantic v2 contracts
│   │   ├── agents/           # shopping, suggestion, catalog, validator, payment
│   │   ├── services/         # razorpay_service, audit_service, inventory, llm
│   │   ├── api/              # chat, catalog, webhooks, admin
│   │   └── templates/        # Jinja2 + HTMX
│   └── tests/
├── ai_buyer/                 # External AI buyer demo
├── data/products.json        # 20 sample products
└── scripts/                  # seed_db.py, run_demo.sh
```

---

## Build Progress

- [x] Phase 1 — Foundation (project setup, DB models, config)
- [x] Phase 2 — Validator Core (safety gate + audit service + tests)
- [x] Phase 3 — Payment + Razorpay (orders, webhook, state machine)
- [x] Phase 4 — Remaining Agents (shopping, suggestion, catalog)
- [x] Phase 5 — API Routes (chat, catalog tools, admin)
- [x] Phase 6 — AI Buyer (demo script)
- [x] Phase 7 — Minimal UI (HTMX chat + audit page)

---

*Built for Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce*

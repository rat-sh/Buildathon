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

## Safety Guarantees

- ❌ No LLM can create a Razorpay order or alter prices/stock.
- ❌ No payment without Validator PASS token.
- ❌ No auto-added upsell items.
- ❌ No audit log modification (append-only).
- ✅ HMAC verified before any webhook state change.
- ✅ Max 2 payment retries — then stops.
- ✅ Hard spending limits defined in code constants.

---

## Quick Start

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env — add Razorpay TEST keys and OPENAI_API_KEY for natural ChatGPT-style replies

# 2. Run backend
cd backend
source ../venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` → Chat UI
Open `http://localhost:8000/admin/audit` → Audit log viewer
Open `http://localhost:8000/docs` → API documentation

---

## Running Tests

```bash
cd backend
pytest -v
```

*Built for Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce*

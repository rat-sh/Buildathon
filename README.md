# SafeAgent Commerce

### Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce

> **LLMs can talk and suggest. A deterministic Validator decides. Only then does money move.**

---

## For the business side (skip the tech, read this first)

**In one line:** this is a working online store — built for Razorpay's AI Buildathon — that lets both people and AI shopping assistants buy things, with a hard rule baked in that no purchase can ever go through unless it first passes an automatic safety check. Below is what that's actually worth to a business, no jargon.

If you run a store — or you're the person who'd have to explain to a boss why a payment went wrong — here's what this actually does for you.

**It lets AI shopping agents buy from you, safely.** More shopping is starting to happen through AI assistants — someone tells their AI "find me running shoes under ₹3,000" and the AI does the browsing and buying instead of a person clicking through a website. If a store can't be found and safely paid by those agents, it's invisible to a growing slice of customers. This makes a store agent-readable and agent-payable without anyone having to just trust the AI to get the money part right.

**It grows order value without annoying customers.** The suggestion engine offers one or two relevant add-ons — but it never adds them without the customer actually saying yes. No pre-checked boxes, no silent upsell quietly inflating the total. Customers keep coming back to stores that don't pull that trick.

**It stops the things that actually cost merchants money and trust:**
- No double-charging someone because they clicked "pay" twice or their connection dropped mid-checkout
- No selling something that's already out of stock
- No forged or tampered payment requests getting through
- No one — human or bot — quietly touching items in someone else's cart before they've checked out
- A full paper trail for every payment: what was allowed, what was blocked, and why — so a disputed charge or a misbehaving AI agent isn't a guessing game afterward

**It keeps spending on a leash, automatically.** Every purchase — whether it's a person or an AI agent buying — has a hard ceiling on how much it can spend per order and per day. That's not friction for a normal shopper; it's insurance against a bug, a bad actor, or a malfunctioning AI agent running up a bill nobody approved.

The short version: this is the plumbing that lets a store say yes to AI-driven shopping — which is coming whether a merchant is ready for it or not — without opening the door to the ways that usually goes wrong.

---

SafeAgent Commerce is a validator-gated multi-agent commerce system for conversational checkout and agent-transactable catalogs. Humans shop via chat; external AI buyers use REST catalog tools shaped like agent tool calls. Natural language is allowed only in the **proposal** layer. No language model can create a Razorpay order, change a price, or mutate stock. Every money-adjacent decision passes through a pure-Python Validator that issues an HMAC-signed PASS token or blocks with an explicit reason code. Every decision is written to an append-only audit log.

---

## 1. What this is

A **validator-gated** Track 01 commerce demo: chat and catalog tools may **propose**; only a **deterministic gate** may allow payment through Razorpay **test** mode. The product bet is simple: **growth** (conversation + AI buyers) without giving the model a direct wire to money.

---

## 2. The problem

Naive agentic checkout breaks in specific, predictable ways:

- Models invent products or prices that are not in the merchant catalog
- Clients or prompts try to pay without the merchant's actual rules applying
- Upsells land in the cart without explicit consent
- Double-submit, replay, and forged webhooks create double-charge risk
- When a payment is blocked or allowed, there's no structured record of *why*

Merchants need growth — conversation, AI buyers — without giving the model a direct path to money.

| Track 01 expectation | How this project meets it |
|----------------------|---------------------------|
| Conversational in-app checkout | Chat UI → cart → Validator → Razorpay test checkout |
| Agent-readable catalog | REST `/catalog/*` tools + `ai_buyer/demo_buyer.py` |
| Upsell / cross-sell | Suggestion agent; `explicitly_accepted` required |
| Explainable money actions | Audit events: decision, reason_code, evidence |
| Bounded money actions | Hard limits in `core/limits.py` (not DB fields) |
| Gated money actions | `PaymentAgent` requires verified `ValidatorPassToken` |

**Out of scope, on purpose:** campaign orchestrator, live Razorpay keys, full ERP/inventory SaaS, unrestricted autonomous purchasing.

---

## 3. Protocol alignment

Agent-to-agent commerce is being shaped by several parallel efforts: NPCI-style agentic payment patterns, **ACP**-style agent-merchant checkout APIs, **AP2**-style signed spending mandates, and **x402**-style machine-to-machine payment challenges. The shared need across all of them: an agent may *propose* a purchase, but must not invent a price, widen its own spend, or charge without a check the model itself does not control.

**What this repo does:** `ValidatorPassToken` is an in-process capability, HMAC-SHA256–signed over cart id, idempotency key, total paisa, session/buyer fields, and issue time (`backend/app/core/pass_token.py`). It's issued only after deterministic Validator checks, and `PaymentAgent` refuses to act on a missing or invalid signature. That matches the *idea* of a short-lived signed mandate: authority is explicit and checkable, not assumed.

**What this repo does not do:** implement AP2, ACP, NPCI UAP, or x402 as wire protocols. "MCP-style" catalog tools are REST handlers shaped for `ai_buyer/demo_buyer.py`, not a running Model Context Protocol server. The alignment here is architectural — the same shape of guarantee — not standards compliance.

---

## 4. Design principles

1. **Proposal is not execution** — Shopping, suggestion, and LLM output may only propose. Payment is a separate privilege.  
2. **Fail closed** — First Validator failure returns BLOCK; there is no best-effort charge.  
3. **Determinism at the money boundary** — Validator contains no LLM; checks are code plus live DB reads.  
4. **Limits as code constants** — An LLM cannot rewrite a constant; a DB limit row could be written by a bug; policy change needs review and deploy (`core/limits.py`). There is no `PUT /limits`.  
5. **Explicit upsell consent** — Suggestions start unaccepted; Validator enforces accept.  
6. **Append-only audit** — History explains decisions; it is not rewritten after the fact.  
7. **Defense in depth** — Signed PASS token, cart ownership, atomic cart lock, rate limits, webhook HMAC, admin key on audit.

---

## 5. System architecture and flows

This section is the map of **who may talk**, **who may decide**, and **who may move money**. Everything else in the README is detail on these paths.

### 5.1 Privilege layers

```text
┌─────────────────────────────────────────────────────────────┐
│  PROPOSAL LAYER (untrusted natural language / clients)      │
│  Shopping Agent · Suggestion Agent · Catalog tools · LLM    │
│  May: search catalog, suggest, build cart intent            │
│  Must not: call Razorpay, set limits, invent pay authority  │
└────────────────────────────┬────────────────────────────────┘
                             │ cart + checkout request
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  DECISION LAYER (deterministic, no LLM)                     │
│  Validator Agent + validator_checks                         │
│  Reads live DB · applies limits.py · reason codes           │
│  Issues HMAC-signed ValidatorPassToken  OR  BLOCK + audit   │
└────────────────────────────┬────────────────────────────────┘
                             │ PASS token only
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  EXECUTION LAYER (single payment privilege)                 │
│  PaymentAgent · razorpay_service (test / simulated)         │
│  Atomic cart LOCK · retries · Orders API                    │
└────────────────────────────┬────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
     Razorpay test checkout          Webhook (HMAC first)
              │                             │
              └──────────┬──────────────────┘
                         ▼
              Order / cart state · audit trail
              Capture + stock via mark_order_captured()
              (webhook and/or client verify-payment; once)
```
**Why three layers instead of one “smart agent”?** One component that both chats and pays maximizes convenience and blast radius together. With the split, shopping code never imports Razorpay. Prompt injection in chat has no path to the payment SDK, because the only code that can call it does not interpret natural language (agents/payment.py safety contract).

**5.2 End-to-end flow (both buyers, one gate)**
```text 
                    ┌──────────────┐     ┌──────────────────┐
                    │ Human chat   │     │ AI buyer script  │
                    │ (browser)    │     │ demo_buyer.py    │
                    └──────┬───────┘     └────────┬─────────┘
                           │                      │
                           │  session + cart      │  X-AI-Buyer-Key
                           │                      │
                           └──────────┬───────────┘
                                      ▼
                         Catalog search / cart build
                         (real Product rows only)
                                      │
                                      ▼
                            POST .../checkout
                                      │
                         ┌────────────┴────────────┐
                         │ assert cart ownership   │
                         │ Validator (ordered      │
                         │ checks, fail-closed)    │
                         └────────────┬────────────┘
                              FAIL │         │ PASS + sign token
                                   ▼         ▼
                              BLOCK +      PaymentAgent
                              audit        verify signature
                                   │         atomic LOCK cart
                                   │         Razorpay order
                                   │              │
                                   │              ▼
                                   │       client pays (test)
                                   │              │
                                   │              ▼
                                   │   webhook (HMAC first)   client verify-payment
                                   │    no → reject + audit         │
                                   │    yes │                       │
                                   │        └───────────┬───────────┘
                                   │                    ▼
                                   │       mark_order_captured()
                                   │       idempotent: order → CAPTURED
                                   │       once, stock −= qty once,
                                   │       no matter which path (or
                                   │       both) actually fires
                                   ▼                    │
                              append-only audit ◄───────┘
```
**5.3 Agents at a glance**
| Agent | Job | LLM? | Razorpay? |
|-------|-----|------|-----------|
| Shopping | Intent + search **Product** table; conversational reply tone | Yes (language/intent only) | Never |
| Suggestion | 1–2 affinity/budget-aware add-ons | Rules / optional NLP | Never |
| Catalog | list/search/limits/intent/checkout tools for machines | No | Never |
| Validator | Safety checklist; PASS token or BLOCK + reason | **No** | Never |
| Payment | Create order only with a verified PASS; max 2 retries | No | **Only this agent** |

**Why split agents instead of one "smart" agent that both chats and pays?** One agent doing both maximizes convenience and blast radius at the same time. With the privilege split, shopping/suggestion code never imports Razorpay at all — prompt injection in a chat message has no code path to the payment SDK, because the only code that can call it doesn't read natural language (`agents/payment.py`'s safety contract).

**Why no LLM inside the Validator?** Natural language is untrusted at the money boundary. Checks are code plus live DB reads, so a model cannot "argue" its way past a price or limit check the way it might argue past an instruction in a prompt.

**5.4 Flows that matter for a live demo**

| Flow | What to show | Why judges care |
|---|---|---|
| **Happy path under limit** | Chat → Cart → PASS → Test/Simulated Pay | Shows the growth path works end-to-end |
| **Over-limit / mismatch / inactive** | BLOCK + `reason_code` displayed in UI and audit log | Shows failures are handled gracefully |
| **Double checkout** | Two concurrent payments → One order | Demonstrates a real concurrency fix, not just a slide |
| **Upsell without accept** | Checkout remains blocked until the user accepts the upsell | Proves consent is enforced, not decorative |
| **AI buyer** | Run `demo_buyer.py` through the same gate | Demonstrates that the merchant is agent-transactable |
| **Audit** | `/admin/audit` showing rows for the above flows | Makes money actions explainable and auditable |
---

## 6. Legal money path

1. Cart is built from real catalog product IDs, with charged amounts stored on the line items.
2. Checkout sends `cart_id`, `session_id`, `idempotency_key`.
3. API asserts the **session owns the cart**, then runs the Validator.
4. **BLOCK** → reason_code + audit row; no Razorpay call is ever made.
5. **PASS** → build `ValidatorPassToken`, HMAC-sign it with `APP_SECRET_KEY`.
6. `PaymentAgent.execute_payment(token)`: rejects a bad type or bad signature; performs the atomic `OPEN → LOCKED` cart transition; enforces `MAX_PAYMENT_RETRIES`; creates the Razorpay order (or a simulated order if the configured keys are still placeholders).
7. Client completes Razorpay test checkout (or the simulated path).
8. Webhook: signature verified on the raw request body before any state change; on capture, `services/order_fulfillment.mark_order_captured()` runs — triggered by the webhook, by the client's `POST /api/verify-payment` call, or by both — and performs the order/cart status update and the stock decrement together, idempotently, exactly once no matter which path fires.
9. Audit rows are written for validation, payment attempts, webhook accept/reject, and cart mutations.

There is no alternate door to payment from the chat or catalog agents — this is the only path.

**Why HMAC-sign the PASS token instead of relying on `isinstance`?** A type check alone is not authenticity — it proves an object is shaped right, not that it was legitimately issued. A forged in-process object must not be able to unlock payment (`pass_token.py`).

**Why an atomic cart lock?** Without one, two concurrent checkout calls on the same open cart can both pass validation before either locks it, producing two orders for one cart. The fix is a single atomic `UPDATE carts SET status='LOCKED' WHERE status='OPEN'`, with the rowcount checked — exactly one caller wins (`test_concurrent_checkout_only_one_order`).

**Why idempotency keys?** A network retry or a double-click must not create two merchant orders for one purchase intent.

**Why funnel both capture triggers through one function instead of letting the webhook and `/api/verify-payment` each mutate state independently?** Two independent writers to the same order/stock state is exactly the dual-capture bug this project used to have (§7, §21). Centralizing the state transition in `mark_order_captured()` and making it idempotent means it doesn't matter which caller gets there first, or whether both do — order status and stock can only ever move once.

---

## 7. Challenges and fixes

Every row below is a real issue found and fixed on `main`, in the order it happened — not a curated highlight reel.

| Issue | Why it happened | Fix | Locked by |
|-------|------------------|-----|-----------|
| Local cart state drifted from the database | UI kept a client-only `cartItems` array after mutations, without re-reading from the backend | Replace local mutations with a backend DB sync | Cart API + UI refresh flow |
| Webhook HMAC could be bypassed in debug mode | A debug shortcut skipped signature verification | Remove the bypass; verify the raw body first, always | `test_webhook_invalid_hmac_rejected` |
| Checkout allowed on already-paid carts | Cart status wasn't enforced as a hard precondition | Block checkout on non-open carts | `test_validator_cart_already_paid_status`, `test_validator_cart_already_paid_captured_order` |
| Cart ID alone was enough to mutate another session's cart | ID was treated as a capability instead of an identifier | Session/buyer ownership check before every mutation (`cart_access.py`) | `test_cannot_remove_item_from_another_sessions_cart` |
| Audit API had no operator secret | No auth dependency on the router at all | Require `X-Admin-Key` on every route in the router | `api/admin.py` (router-level dependency) |
| Concurrent checkouts could double-order | Check-then-act on cart status, no atomicity | Atomic `OPEN → LOCKED` transition | `test_concurrent_checkout_only_one_order` |
| Stock never decremented after a sale | Nothing in the codebase wrote to `stock_quantity` after checkout | Decrement on the `payment.captured` webhook, clamped at 0 | `test_webhook_capture_decrements_stock` |
| PASS token was only `isinstance`-checked | Type check treated as if it were authenticity | HMAC-SHA256 sign at issuance, verify before use | `test_payment_agent_rejects_unsigned_pass_token`, `test_payment_agent_valid_pass_token` |
| No rate limits on checkout or cart mutation routes | Nothing stopped scripted spam | `slowapi` limits on those routes specifically | `core/rate_limit.py` |

---

## 8. Validator

Checks run in a fixed order; the first failure wins and the rest are never evaluated.

| # | Check | Failure code |
|---|-------|--------------|
| 1 | Idempotency key not already used on an order | `DUPLICATE_IDEMPOTENCY_KEY` |
| 2 | Product exists in the catalog | `ITEM_NOT_FOUND` |
| 3 | Product `is_active = True` | `ITEM_INACTIVE` |
| 4 | `charged_price_paisa ≤ product.price_paisa` | `PRICE_MISMATCH` |
| 5 | Quantity ≤ stock on hand | `STOCK_OUT` |
| 6 | Every add-on/suggestion `explicitly_accepted = True` | `ADDON_NOT_ACCEPTED` |
| 7 | Within per-transaction and daily ceilings | `TX_LIMIT_EXCEEDED` / `DAILY_LIMIT_EXCEEDED` |

All checks pass → `PASS` plus a signed token. Any single failure → `BLOCK` plus the reason code, written to the audit log.

**Why re-check price at validation time, not just at add-to-cart?** UI state and LLM output are both untrusted. Charge amounts on cart lines are compared against the *current* catalog row at the moment of checkout, so a hallucinated or client-tampered price cannot clear payment even if it made it into the cart earlier.

**Why do limits live in `limits.py` as constants, not as database rows?** Straight from the file's own reasoning: an LLM agent cannot hallucinate or manipulate a Python constant. A database value could, in principle, be modified by a rogue write. A code constant requires a code review and a deployment to change — the safest boundary available for spending controls this project could build in the time it had.

### Limits (integer paisa only)

| Limit | Human | AI buyer |
|-------|-------|----------|
| Per transaction | ₹5,000 (500,000 paisa) | ₹2,000 (200,000 paisa) |
| Daily ceiling | ₹10,000 | ₹5,000 |
| Max payment retries | 2 | 2 |
| Max items per cart (`MAX_CART_ITEMS`) | 10 | 10 |
| Max suggestions per session (`MAX_SUGGESTIONS_PER_SESSION`) | 2 | 2 |

Chat **budget** (what the user mentions in conversation) only steers search and suggestions — it is never the enforcement mechanism. The table above is the hard checkout gate. Product copy should describe it as "order safety cap," not "your wallet is ₹5,000."

**Why tighter limits for AI buyers?** A human clicking "buy" has looked at the item and the price. An AI buyer transacting end-to-end has not been looked at by anyone at the moment of purchase — the lower ceiling is the blast-radius control for exactly the failure mode this track is about.

### ValidatorPassToken

Issued only on a full PASS. Its fields — cart id, totals, session/buyer identifiers, issue timestamp — are signed with HMAC-SHA256 using `APP_SECRET_KEY`. `PaymentAgent` verifies that signature before it will create a Razorpay order, so a forged or hand-built object cannot impersonate a legitimate PASS result. The token never leaves the process in the current architecture, but the signature makes that safety property hold structurally rather than by accident of deployment shape — see §21 for what that means if this ever becomes a multi-service system.

---

## 9. Payment and Razorpay

- **Single call site:** only `PaymentAgent`, through `razorpay_service.py`, ever talks to the Razorpay SDK — and only in test mode.
- **Placeholder keys:** an `.env` still carrying `REPLACE_ME`-style Razorpay values routes to a simulated order path, which still runs behind the full Validator gate — this is what lets the project demo without live Razorpay credentials (a real `DATABASE_URL` is still required; see §17).
- **Concurrency:** the atomic cart lock (§6) prevents double-checkout races.
- **Retries:** hard stop after `MAX_PAYMENT_RETRIES` — a payment agent that retries forever against a flaky gateway becomes its own way to hammer the API or bleed a wallet.
- **Webhooks:** HMAC verified on the raw body first; an invalid signature produces a BLOCK audit row (`INVALID_HMAC_SIGNATURE`) and zero order mutation.
- **Capture and stock:** handled by the shared `services/order_fulfillment.mark_order_captured()` function, called from the webhook capture path and/or the client-side `POST /api/verify-payment` flow. Capture is idempotent, so whichever path fires first — or both — the order moves to `CAPTURED` and stock decrements exactly once. This was previously a dual-writer bug (§7); it's fixed, and §21's remaining scope boundaries are unrelated to it.

**Why raw-body HMAC before parsing?** Verifying after parsing would let a client alter fields post-signature-check; rejecting before any parsing or mutation closes that gap entirely.

---

## 10. Human checkout

1. Browser is issued a `session_id`.
2. Message → Shopping agent queries the real DB catalog (the LLM may parse intent and write a natural reply, never invent a product).
3. Product cards shown are always real rows, never invented SKUs.
4. Add / remove / accept-suggestion all require the calling session to **own** the cart.
5. An optional budget mentioned in chat biases search and suggestions only.
6. Checkout → the same Validator → Payment path as everything else.

**Why must the session own the cart?** `cart_id` is not itself a capability — it's just an identifier. Without an ownership check, anyone who can guess or enumerate a cart ID could mutate someone else's cart. `cart_access.py` closes that gap.

**Why explicit accept on suggestions, and not auto-add?** A silent upsell changes the total without consent — the Validator fails closed with `ADDON_NOT_ACCEPTED` on anything not explicitly accepted.

**LLM allowlist:** intent parsing and reply tone. **LLM denylist:** prices, stock, Razorpay calls, PASS tokens, limits. If `OPENAI_API_KEY` isn't set, the Shopping/Suggestion agents fall back to deterministic, non-conversational replies — the underlying catalog search and suggestion logic is plain SQL, so the demo still works, just with flatter language.

---

## 11. AI buyer path

`ai_buyer/demo_buyer.py` is an external client: it authenticates with `X-AI-Buyer-Key`, calls the same catalog tools, and checks out through the **identical** Validator and Payment stack a human uses — there's no second, weaker payment pipeline for machines. When a request is flagged `is_ai_buyer`, the tighter AI-buyer limits from §8 apply automatically.

**Why one gate for both humans and machines?** A second path, even a well-intentioned one, is a second thing that can drift out of sync with the safety rules over time. One gate means one place to audit and one place to fix.

---

## 12. Audit log

Append-only events capture actor, action, decision (`PASS` / `BLOCK` / `INFO`), reason_code, evidence, and timestamp. The admin HTTP API requires `X-Admin-Key`. The UI color-codes decisions (PASS green, BLOCK red, INFO neutral), and an optional analysis endpoint answers aggregate questions — blocked counts, reason-code breakdowns — from real audit rows, never invented statistics.

**Why append-only?** Explainability fails if the thing meant to explain a decision can itself be rewritten after the fact — including by a bug, not just by malice.

**Why an admin key on the audit API at all, even in a demo?** Decision evidence — buyer IDs, session IDs, amounts — is sensitive regardless of whether the deployment is a demo or production; a shared secret is the minimum viable gate, not the ideal one.

**What this is not:** a full bank SIEM, packet capture, or a legal-retention product. It's a hackathon-scoped, structured decision trail tied directly to the payment gate — sized to what this track needed, not to what a compliance team would eventually require.

---

## 13. Security controls

| Control | Mechanism |
|---------|-----------|
| No LLM payments | Only `PaymentAgent` uses the Razorpay SDK |
| Gate | Validator + HMAC-signed PASS token |
| Cart authorization | Session must own the cart |
| Double checkout | Atomic `OPEN → LOCKED` |
| Replay | Unique idempotency keys |
| Webhook forgery | HMAC verified on raw body, before parsing |
| Admin audit access | `X-Admin-Key` header |
| Abuse / spam | Rate limits on checkout and cart-mutation routes |
| Price integrity | Charged amount checked ≤ catalog price at validation time |
| Upsell consent | `explicitly_accepted` enforced by the Validator |
| Money math | Integer paisa throughout, never floats |

**Why rate limits on top of everything else?** Money-adjacent routes with no throttling are trivial to hammer — rate limits reduce that surface without changing any Validator rule; they're a blast-radius control, not a correctness control.

**Honest residual risk:** the in-process signed token is not a separate payment microservice behind mutual TLS — it's a single-process trust boundary made structurally sound rather than a distributed one. That's a deliberate buildathon tradeoff: a clear, demoable, testable gate with real hardening, not full bank-grade service isolation. See §21 for what changes if this becomes multi-service.

---

## 14. Data model

- **Product** — source of truth for `price_paisa`, `stock_quantity`, `is_active`.
- **Cart / CartItem** — charged price at time of add, suggestion flag, `explicitly_accepted` flag, cart status (`OPEN` / `LOCKED` / `PAID`).
- **Order** — Razorpay linkage, status, unique `idempotency_key`.
- **AuditEvent** — actor, action, decision, reason_code, evidence, timestamps.

Seeded from `data/products.json` when the product table is empty at startup.

**Why the catalog is the single source of truth for price and stock, never the cart or the LLM's output?** Pay-time checks read the product row directly, so nothing the model said earlier in the conversation can clear payment on its own — only what's actually in the database right now.

**Why integer paisa on the models themselves, not just in the Validator's math?** Same reasoning as §8 — no floating-point rounding anywhere a stored charge amount could drift from what was actually authorized.

---

## 15. API surface

- **Human:** `POST /chat/message`, add-to-cart, add-suggestion, accept-addon, remove-item, checkout, cart read (for UI sync).
- **Catalog (AI buyer):** products, limits, intent, checkout — all behind `X-AI-Buyer-Key`.
- **Admin:** audit list/summary, behind `X-Admin-Key`.
- **Webhooks:** the Razorpay webhook receiver.
- **Meta:** health check, `/docs` (OpenAPI, dev only), HTML `/` and `/admin/audit`.

The runtime path list at `/docs` is the authoritative source — this section is a map, not a spec.

---

## 16. Repository layout

```text
safeagent-commerce/
├── ai_buyer/
│   ├── demo_buyer.py
│   └── README.md
├── backend/
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py
│   │   ├── agents/       # shopping, suggestion, catalog, validator, validator_checks, payment
│   │   ├── api/          # chat_*, cart, catalog, webhooks, admin, payment_verify, views, health
│   │   ├── core/         # config, database, limits, security, pass_token, rate_limit, cart_access
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── static/       # css/, js/chat/{api,cart,checkout,main,messages,utils}.js, audit.js
│   │   └── templates/    # base, chat, admin/…
│   └── tests/            # test_validator, test_payment, test_stock, test_cart_*, test_catalog, test_audit_*
├── data/
│   └── products.json
├── scripts/
│   ├── seed_db.py
│   └── run_demo.sh
├── docker-compose.yml
├── pyproject.toml        # requires-python >= 3.12
├── requirements.txt
├── .env.example
└── README.md
```

---

## 17. Configuration

Copy `.env.example` to `.env`. **Never commit `.env`.**

| Variable | Role |
|----------|------|
| `DATABASE_URL` | Required `postgresql+asyncpg://…` (Supabase Postgres) — `config.py` rejects a bare SQLite URL for the running app; SQLite is used only inside the `pytest` suite, via `tests/conftest.py` |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Razorpay **test** keys only — `config.py` actively rejects any key that isn't `rzp_test_*` |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook HMAC secret |
| `OPENAI_API_KEY` / `LLM_MODEL` | Optional — enables conversational replies; without it, deterministic fallback replies are used |
| `APP_SECRET_KEY` | PASS-token HMAC signing key |
| `AI_BUYER_API_KEY` | Catalog tool auth, checked against the `X-AI-Buyer-Key` header |
| `ADMIN_API_KEY` | Audit API auth, checked against the `X-Admin-Key` header |

Supabase Postgres is the runtime database, not an optional upgrade — `config.py` actively rejects a SQLite `DATABASE_URL` for the running app (see §21). `.env.example` ships a Supabase-shaped `DATABASE_URL` template with a `REPLACE_ME`-style password placeholder, not a working default, so real Supabase credentials must be filled in before `uvicorn` will boot. SQLite only appears inside the `pytest` suite, via `tests/conftest.py`, so the test suite itself has no external database dependency.

---

## 18. Run

**Python:** 3.12+ (`requires-python = ">=3.12"` in `pyproject.toml`).

```bash
cd safeagent-commerce
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# RAZORPAY test keys, and APP_SECRET_KEY; OPENAI_API_KEY is optional

cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` (chat), `http://localhost:8000/admin/audit` (audit log — needs `X-Admin-Key`), `http://localhost:8000/docs` (OpenAPI, dev only).

**Run tests**

```bash
cd safeagent-commerce/backend
source ../venv/bin/activate
pytest tests/ -v
```

Run `pytest tests/ -v` and check the pass count against §19's breakdown of what each file proves — the suite runs entirely against the in-memory SQLite fixture in `tests/conftest.py`, so it needs no Supabase connection.

**AI buyer demo**

```bash
cd safeagent-commerce
source venv/bin/activate
python ai_buyer/demo_buyer.py
```

**One-command demo (both paths + audit pointer)**

```bash
cd safeagent-commerce
./scripts/run_demo.sh both   # or: human | ai
```

**Docker**

```bash
cd safeagent-commerce
docker compose up --build
```

---

## 19. Testing

```bash
cd backend && pytest tests/ -v
```

Grouped by what each file actually proves (run `pytest tests/ -v` for the current pass count):

| File | What it proves |
|------|-----------------|
| `test_validator.py` | Every gate outcome: PASS, `ITEM_NOT_FOUND`, `ITEM_INACTIVE`, `PRICE_MISMATCH`, `STOCK_OUT`, `TX_LIMIT_EXCEEDED`, `DAILY_LIMIT_EXCEEDED`, `ADDON_NOT_ACCEPTED`, `DUPLICATE_IDEMPOTENCY_KEY`, both already-paid-cart variants |
| `test_payment.py` | Valid signed PASS accepted; missing/unsigned token rejected; max retries enforced; invalid/simulated webhook HMAC rejected; exactly one winner in a concurrent double-checkout |
| `test_cart_security.py` | A session cannot remove items from another session's cart (ownership) |
| `test_stock.py` | Stock decrements exactly once via `mark_order_captured()` — covers the webhook capture path, the `/api/verify-payment` path, and both firing on the same order without a double-decrement |
| `test_cart_budget.py` | Budget is parsed and resolved from a chat message; items can be removed from an open cart |
| `test_catalog.py` | Shopping search, suggestion generation, and catalog tool handlers all stay grounded in real DB products |
| `test_audit_analysis.py` | Summary stats, blocked counts, reason-code counts, and threat summary are computed from real audit rows |

**Not covered:** load/performance testing. (The dual-capture race between the webhook and `/api/verify-payment` is fixed and covered by `test_stock.py`, not an open gap — see §21.)

---

## 20. Demo script

`scripts/run_demo.sh` is the actual runner this section describes — it checks the server is up, then walks both paths:

**AI buyer path** (`./scripts/run_demo.sh ai`): runs `ai_buyer/demo_buyer.py` end to end — catalog discovery, an intent call, and a checkout through the real Validator/Payment stack, printed to the terminal.

**Human path** (`./scripts/run_demo.sh human`): prints the browser URL and a suggested first message — e.g. *"Show me running shoes under ₹3000"* — then a prompt to accept a suggestion and confirm, so a live demo can be driven straight from the terminal's own instructions instead of an improvised walkthrough.

**Both** (`./scripts/run_demo.sh both`, the default): runs the AI path first, then prints the human-path instructions, then points to the audit log at `/admin/audit` and the raw `GET /admin/audit/events` endpoint so the last step of any demo is showing the decision trail for what just happened — this is the moment to show a blocked attempt (an inactive product, a price mismatch, or an over-limit cart) alongside a successful one, since Track 01 explicitly asks to see one failure handled gracefully next to the audit trail that explains it.

---

## 21. Known limitations

### Fixed in this codebase (do not treat as open bugs)

**Dual capture / stock.**  
Earlier, `webhooks.py` (on `payment.captured` / `order.paid`) and `payment_verify.py` could both mark an order `CAPTURED` and cart `PAID`, but only the webhook decremented stock.  
**Now fixed:** both paths call `services/order_fulfillment.mark_order_captured()`. Capture is **idempotent** (atomic transition to `CAPTURED`); stock decrements **exactly once** whether verify-payment runs, the webhook runs, or both. Covered by `test_stock.py` (webhook, verify, and dual-order tests).

**Primary database.**  
The app no longer defaults to SQLite for runtime.  
**Now:** `DATABASE_URL` must be `postgresql+asyncpg://…` (Supabase Postgres). Config rejects a bare SQLite URL for the running app. SQLite is used **only** in `pytest` via `tests/conftest.py`. See `.env.example` and the Supabase setup notes in this README.

### Intentional scope boundaries (not defects)

- **“MCP-style” means REST, not MCP** — Catalog routes are HTTP tool-shaped handlers for `ai_buyer/demo_buyer.py`, not a Model Context Protocol server.
- **INR / paisa only** — Integer paisa throughout; no multi-currency ledger.
- **No refund, dispute, or chargeback flows** — Out of scope for Track 01 growth/checkout, not a full payments lifecycle product.
- **PASS token is in-process HMAC (+ TTL)** — Unforgeable inside this process architecture; not a standalone mandate service another microservice verifies independently (related in *shape* to AP2, not AP2 wire compliance).
- **Admin auth is `X-Admin-Key`** — Shared secret suitable for a buildathon demo, not SSO/OIDC for production ops.
- **Demo catalog** — Seeded from `data/products.json` (~20 products), not a live merchant feed.
- **No AP2 / ACP / x402 wire-protocol claim** — Architectural alignment only (§3).

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

## 22. FAQ

**Why not let the Validator run *inside* the LLM's own function-calling loop, as just another tool it can call?** Because the safety property depends on the Validator being un-skippable, not just available. As a tool the model *chooses* to call, a manipulated model could simply not call it, or call it and ignore a BLOCK result. As a plain function call sitting in the request handler's own control flow, there is no code path to checkout that bypasses it — that's a static guarantee, not a behavioral one.

**Why not use a second LLM as the checker, "LLM proposes, LLM reviews"?** Two models agreeing isn't proof of correctness — it's correlated failure. If the first model was successfully prompt-injected into proposing a bad cart, there's no strong reason a second model resists the same manipulation differently. A deterministic function has no equivalent failure mode: it either reads the database correctly or it doesn't, and that's testable exhaustively (§19).

**What happens if the LLM is completely unavailable — no API key, or the provider is down?** Checkout is entirely unaffected, because the Validator, Payment, and Catalog agents never call an LLM at all. The Shopping and Suggestion agents fall back to deterministic replies built on plain SQL underneath — search and suggestions keep working, just with flatter, non-conversational language (§10).

**Why paisa integers instead of a `Decimal` rupee type?** Both avoid float rounding error; paisa-as-integer was chosen specifically because Razorpay's own API is paisa-denominated, so there's no unit-conversion boundary between how this system thinks about money and how the payment gateway does — one less place for an off-by-a-conversion bug to live.

**Why does the daily ceiling check use `buyer_id` OR `session_id`, and what happens if a request has neither?** Checked directly against the schemas: it can't happen through the current API surface. `AICheckoutRequest.buyer_id` is a required field, and human checkout always generates a `session_id` server-side if the client didn't send one. If both were ever absent, the underlying query would silently sum spend across the entire platform for the day rather than one buyer's — which is why it's worth a defensive guard (raise rather than silently proceed) even though nothing in the code can currently trigger it.

---

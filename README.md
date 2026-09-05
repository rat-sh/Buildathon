# SafeAgent Commerce

### Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce

> **LLMs can talk and suggest. A deterministic Validator decides. Only then does money move.**

---

## Executive Summary & Buildathon Review Scorecard

| Dimension | Score | Rating & Assessment Highlights |
|-----------|-------|--------------------------------|
| **Financial Safety** | ★★★★★ | **Production-grade.** 7-check deterministic validator gate + HMAC pass tokens. Zero LLM in payment path. |
| **Architecture** | ★★★★☆ | Multi-agent privilege separation (Shopping, Suggestion, Catalog, Validator, Payment). |
| **System Flow** | ★★★★☆ | Idempotent capture, atomic cart locking, full end-to-end audit trace. |
| **Presentation** | ★★★★☆ | Demo-ready with dark theme, trust badges, live status indicators & audit trail. |
| **AI Chat Quality** | ★★★★☆ | Genuinely conversational search & budget guidance with LLM; deterministic fallback. |
| **UI/UX & Browse** | ★★★☆☆ | Dark theme chat + cart sidebar; focus on conversational shopping interface. |
| **Real-World Usefulness**| ★★☆☆☆ | Killer AI assistant concept for shoppers; needs multi-tenant onboarding for retail shop owners. |

---

## For the business side (skip the tech, read this first)

**In one line:** this is a working online store — built for Razorpay's AI Buildathon — that lets both people and AI shopping assistants buy things, with a hard rule baked in that no purchase can ever go through unless it first passes an automatic safety check. Below is what that's actually worth to a business, no jargon. You can think of your own website like amazon, flipkart, etc, there you chat with the assistant and it helps you shop, then finally you make the payment. I notice many assistant makes mistake like chatting in robotics way, where it doesn't understand human language properly and due to this its unable to understand user need. And because of this it makes mistakes like adding wrong item in cart, or wrong suggestion that makes customer frustated.

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

This section maps **who may talk**, **who may decide**, and **who may move money**. 

### 5.1 Privilege layers & architecture graph

```mermaid
graph TD
    A["Human / AI Buyer"] --> B["Shopping Agent<br/>(catalog search + LLM intent)"]
    B --> C["Suggestion Agent<br/>(opt-in upsells)"]
    C --> D["Validator Agent<br/>(7 deterministic checks)"]
    D -->|BLOCK| E["Reject — zero money moves"]
    D -->|"PASS + HMAC token"| F["Payment Agent<br/>(Razorpay Orders API)"]
    F --> G["Razorpay Checkout"]
    G --> H["Webhook / Verify<br/>(HMAC-verified capture)"]
    H --> I["Audit Log<br/>(append-only)"]
```

**Why three layers instead of one "smart agent"?** One component that both chats and pays maximizes convenience and blast radius together. With the split, shopping code never imports Razorpay. Prompt injection in chat has no path to the payment SDK, because the only code that can call it does not interpret natural language (`agents/payment.py` safety contract).

### 5.2 End-to-end transaction sequence flow

```mermaid
sequenceDiagram
    participant U as Customer / AI Buyer
    participant C as Chat UI / Agent Client
    participant S as Shopping Agent
    participant LLM as OpenAI LLM (optional)
    participant SG as Suggestion Agent
    participant V as Validator Agent
    participant P as Payment Agent
    participant R as Razorpay
    participant A as Audit Log

    U->>C: "Show me running shoes under ₹4000"
    C->>S: POST /chat/message
    S->>LLM: Parse intent (query, category, max_price)
    LLM-->>S: {query: "running shoes", max_price_paisa: 400000}
    S->>S: Query DB (active, in stock, price ≤ 400000)
    S-->>C: Products + AI conversational reply
    
    U->>C: "Add to cart" (clicks button)
    C->>C: POST /chat/add-to-cart
    Note over C: Cart created, product added<br/>charged_price = catalog_price
    
    C->>SG: Suggestions for cart
    SG-->>C: "Running socks (₹599)" — is_suggestion=true, accepted=false
    U->>C: "Add suggestion" + "Accept add-on"
    
    U->>C: "Checkout" (clicks button)
    C->>V: POST /chat/checkout
    
    Note over V: 7 DETERMINISTIC CHECKS<br/>1. Product exists ✓<br/>2. Product active ✓<br/>3. Price ≤ catalog ✓<br/>4. Stock available ✓<br/>5. TX limit ✓<br/>6. Daily ceiling ✓<br/>7. Add-ons accepted ✓<br/>8. Idempotency unique ✓
    
    V-->>P: HMAC-signed PASS token
    P->>R: Create Razorpay Order
    R-->>P: order_id
    P-->>C: Checkout data
    
    C->>R: Open Razorpay Checkout Modal
    U->>R: Pay (test card)
    R->>C: Payment success callback
    C->>C: POST /api/verify-payment (HMAC check)
    Note over C: mark_order_captured() — idempotent<br/>Stock decremented exactly once
    
    A->>A: All events logged (append-only)
```

### 5.3 Agents at a glance

| Agent | Job | LLM? | Razorpay? |
|-------|-----|------|-----------|
| **Shopping** | Intent + search **Product** table; conversational reply tone | Yes (language/intent only) | Never |
| **Suggestion** | 1–2 affinity/budget-aware add-ons | Rules / optional NLP | Never |
| **Catalog** | list/search/limits/intent/checkout tools for machines | No | Never |
| **Validator** | Safety checklist; PASS token or BLOCK + reason | **No** | Never |
| **Payment** | Create order only with a verified PASS; max 2 retries | No | **Only this agent** |

**Why split agents instead of one "smart" agent that both chats and pays?** One agent doing both maximizes convenience and blast radius at the same time. With the privilege split, shopping/suggestion code never imports Razorpay at all — prompt injection in a chat message has no code path to the payment SDK, because the only code that can call it doesn't read natural language (`agents/payment.py`'s safety contract).

**Why no LLM inside the Validator?** Natural language is untrusted at the money boundary. Checks are code plus live DB reads, so a model cannot "argue" its way past a price or limit check the way it might argue past an instruction in a prompt.

### 5.4 Flows that matter for a live demo

| Flow | What to show | Why judges care |
|---|---|---|
| **Happy path under limit** | Chat → Cart → PASS → Test/Simulated Pay | Shows the growth path works end-to-end |
| **Over-limit / mismatch / inactive** | BLOCK + `reason_code` displayed in UI and audit log | Shows failures are handled gracefully |
| **Double checkout** | Two concurrent payments → One order | Demonstrates a real concurrency fix, not just a slide |
| **Upsell without accept** | Checkout remains blocked until the user accepts the upsell | Proves consent is enforced, not decorative |
| **AI buyer** | Run `demo_buyer.py` through the same gate | Demonstrates that the merchant is agent-transactable |
| **Audit** | `/admin/audit` showing rows for the above flows | Makes money actions explainable and auditable |

---

## 6. Architectural Challenges & System Design Solutions

Rather than treating issues as simple bug fixes, SafeAgent Commerce solves 6 core **System Architecture Problems** at the design layer:

### 1. Keeping the LLM strictly advisory, not authoritative
- **PROBLEM:** Function-calling models don't have a hard boundary between "suggesting an action" and "taking an action" — the model happily emits a tool call for checkout if permitted.
- **SOLUTION:** We architected the Shopping and Suggestion agents so their only output is a proposed cart (`product_ids` + quantities). The Validator never trusts anything the LLM computed; it always re-fetches price, stock, and active status directly from the live PostgreSQL database.

### 2. Price/stock race conditions between catalog read and cart submission
- **PROBLEM:** Product data can change between the moment the Shopping Agent surfaces a result and the moment the cart is submitted. A naive "price ≤ what the LLM said" check is unsafe.
- **SOLUTION:** The Validator treats conversational context and transactional truth as two separate data paths and always validates against the current catalog state at checkout time.

### 3. Idempotency under retries and concurrent requests
- **PROBLEM:** Payment Agent retries (network failures, Razorpay timeouts) or double-clicks could otherwise create multiple orders.
- **SOLUTION:** We enforce a unique idempotency key at the database constraint level and an atomic cart status transition (`OPEN` → `LOCKED`). Duplicate or racing requests are rejected with `DUPLICATE_IDEMPOTENCY_KEY` or lose the lock, rather than relying on the caller to behave correctly.

### 4. Webhook trust boundary
- **PROBLEM:** Early on it is tempting to add a debug bypass for local webhook testing, which would create a code path where an unsigned webhook could flip order state.
- **SOLUTION:** We deliberately kept HMAC verification mandatory even in development. This made local testing slower (signed payloads had to be replayed), but guaranteed that path never existed.

### 5. Add-on consent enforcement
- **PROBLEM:** The Suggestion Agent can propose upsells conversationally, but inferring consent from free-text chat history is exactly the kind of natural-language ambiguity that shouldn't gate a financial transaction.
- **SOLUTION:** The Validator rejects any cart containing an add-on that was not explicitly accepted via a structured field (`explicitly_accepted = True`). Consent is never inferred from chat text.

### 6. Dual capture / stock-decrement race
- **PROBLEM:** Both the Razorpay webhook and the client-side verify-payment endpoint could independently mark an order as captured, risking a double stock decrement.
- **SOLUTION:** We centralized the state transition into a single idempotent `mark_order_captured()` function so that stock is decremented exactly once, regardless of which path (or both) fires.

### Summary of Engineering Hardening

| System Design Challenge | Architectural Cause | Engineering Solution | Verified By |
|-------------------------|---------------------|----------------------|-------------|
| **Local cart state drift** | UI kept client-only array after mutations | Replaced local UI mutations with backend DB sync | Cart API + UI refresh flow |
| **Webhook HMAC bypass risk** | Debug shortcut skipped signature check | Removed bypass; enforce raw body HMAC check always | `test_webhook_invalid_hmac_rejected` |
| **Checkout on paid carts** | Cart status unvalidated before checkout | Added check #0 `check_cart_checkout_eligible` | `test_validator_cart_already_paid_*` |
| **Cart hijacking via ID** | Cart ID treated as capability | Enforced session/buyer ownership check on mutations | `test_cannot_remove_item_from_another_sessions_cart` |
| **Unauthenticated audit API** | Missing auth dependency on router | Required `X-Admin-Key` header on all audit endpoints | `api/admin.py` |
| **Concurrent double-checkout** | Non-atomic check-then-act on cart status | Implemented atomic DB status update `OPEN → LOCKED` | `test_concurrent_checkout_only_one_order` |
| **Unsigned PASS token** | Token checked only for class type | Signed with HMAC-SHA256; verified before execution | `test_payment_agent_rejects_unsigned_pass_token` |

---

## 7. Legal money path

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

**Why funnel both capture triggers through one function?** Centralizing the state transition in `mark_order_captured()` and making it idempotent means it doesn't matter which caller gets there first, or whether both do — order status and stock can only ever move once.

---

## 8. Validator — the core safety gate

Checks run in a fixed order; the first failure wins and the rest are never evaluated.

| # | Check Function | Failure Reason Code | What It Prevents |
|---|----------------|---------------------|------------------|
| 0 | `check_cart_checkout_eligible` | `CART_ALREADY_PAID` | Double-payment of already-paid carts |
| 1 | `check_idempotency` | `DUPLICATE_IDEMPOTENCY_KEY` | Replay attacks / duplicate charges |
| 2 | `check_item_exists` | `ITEM_NOT_FOUND` | LLM-hallucinated product IDs |
| 3 | `check_item_active` | `ITEM_INACTIVE` | Ordering discontinued inventory |
| 4 | `check_price_integrity` | `PRICE_MISMATCH` | **Critical** — LLM or client price tampering |
| 5 | `check_stock` | `STOCK_OUT` | Overselling out-of-stock items |
| 6 | `check_addon_accepted` | `ADDON_NOT_ACCEPTED` | **Critical** — unaccepted/auto-added upsells |
| 7 | `check_tx_limit` & `check_daily_ceiling` | `TX_LIMIT_EXCEEDED` / `DAILY_LIMIT_EXCEEDED` | Runaway agent spending |

All checks pass → `PASS` plus a signed token. Any single failure → `BLOCK` plus the reason code, written to the audit log.

**Why re-check price at validation time, not just at add-to-cart?** UI state and LLM output are both untrusted. Charge amounts on cart lines are compared against the *current* catalog row at the moment of checkout, so a hallucinated or client-tampered price cannot clear payment even if it made it into the cart earlier.

**Why do limits live in `limits.py` as constants, not as database rows?** Straight from the file's own reasoning: an LLM agent cannot hallucinate or manipulate a Python constant. A database value could, in principle, be modified by a rogue write. A code constant requires a code review and a deployment to change.

### Limits (integer paisa only)

| Limit Parameter | Human Shopper | AI Shopping Agent |
|-----------------|---------------|-------------------|
| Per-Transaction Cap | ₹10,000 | ₹5,000 |
| Daily Spending Ceiling | ₹20,000 | ₹10,000 |
| Max Payment Retries | 2 | 2 |
| Max Items per Cart (`MAX_CART_ITEMS`) | 10 | 10 |
| Max Suggestions per Session (`MAX_SUGGESTIONS_PER_SESSION`) | 2 | 2 |

Chat **budget** (what the user mentions in conversation) only steers search and suggestions — it is never the enforcement mechanism. The table above is the hard checkout gate.

**Why tighter limits for AI buyers?** A human clicking "buy" has looked at the item and the price. An AI buyer transacting end-to-end has not been looked at by anyone at the moment of purchase — the lower ceiling is the blast-radius control.

### ValidatorPassToken

Issued only on a full PASS. Its fields — cart id, totals, session/buyer identifiers, issue timestamp — are signed with HMAC-SHA256 using `APP_SECRET_KEY`. `PaymentAgent` verifies that signature before it will create a Razorpay order, so a forged or hand-built object cannot impersonate a legitimate PASS result.

---

## 9. Payment and Razorpay

- **Single call site:** only `PaymentAgent`, through `razorpay_service.py`, ever talks to the Razorpay SDK — and only in test mode.
- **Placeholder keys:** an `.env` still carrying `REPLACE_ME`-style Razorpay values routes to a simulated order path, which still runs behind the full Validator gate.
- **Concurrency:** the atomic cart lock (§7) prevents double-checkout races.
- **Retries:** hard stop after `MAX_PAYMENT_RETRIES` — a payment agent that retries forever against a flaky gateway becomes its own vector for spam or drain.
- **Webhooks:** HMAC verified on the raw body first; an invalid signature produces a BLOCK audit row (`INVALID_HMAC_SIGNATURE`) and zero order mutation.
- **Capture and stock:** handled by `services/order_fulfillment.mark_order_captured()`, called from the webhook capture path and/or the client-side `POST /api/verify-payment` flow.

---

## 10. Real-World Retail & Small Shop Owner Use Case

### The Sari Shop Scenario: Rajesh from Varanasi

Suppose **Rajesh owns a sari shop in Varanasi** and wants an online store for both human customers and AI shopping assistants:

| Retailer Need | SafeAgent Commerce Capabilities | Strategic Alignment & Roadmap |
|---------------|---------------------------------|-------------------------------|
| **AI Shopping Assistant** | ✅ **Active** | Customers chat queries ("Show silk sarees under ₹5,000 for a wedding") & receive budget-aware guidance. |
| **Opt-in Upselling** | ✅ **Active** | Suggests matching items (e.g., matching blouse piece) with explicit consent before checkout. |
| **Financial Safety** | ✅ **Active** | Prevents system glitches or price tampering from undercharging; caps daily order totals. |
| **Audit Trail** | ✅ **Active** | Every order, block, and state change is logged in an unalterable audit trail. |
| **Product Photo Management** | ⚠️ SVG Placeholders | Real retail needs image uploads per product (requires multi-media catalog expansion). |
| **Multi-Tenant Onboarding** | ⚠️ Single-tenant DB | Currently configured as a single store; multi-merchant accounts require tenant IDs. |
| **Cash on Delivery (COD)** | ⚠️ Online Gateway Only | Built for digital payments via Razorpay (test mode); COD would require offline validation rules. |

### E-Commerce Benchmark Comparison (Amazon/Flipkart vs SafeAgent Commerce)

| Feature Area | Amazon / Flipkart | SafeAgent Commerce | Strategic Position |
|--------------|-------------------|-------------------|--------------------|
| **Chat Assistance** | Basic support bot | ✅ **Core Strengths** — Full conversational discovery & checkout | **Ahead** |
| **Trust Indicators** | Security badges | ✅ **Live Badges** — "Validator-gated checkout", "Opt-in upsells", audit logs | **Strong** |
| **Payment Gateway** | Multi-method | ✅ **Razorpay Checkout Integration** (Cards, UPI, Netbanking in test mode) | **Strong** |
| **Product Visuals** | Rich Photo Galleries | ⚠️ SVG Placeholders | Benchmark Gap |
| **Product Browsing** | Grid/Filters/Categories | ⚠️ Chat-first interface (Conversational discovery focus) | Specialized Focus |
| **User Identity** | User Accounts / SSO | ⚠️ Session-based identity (`session_id`) | Lightweight |

---

## 11. Human checkout & AI Chat Quality

1. Browser is issued a `session_id`.
2. Message → Shopping agent queries the real DB catalog (the LLM may parse intent and write a natural reply, never invent a product).
3. Product cards shown are always real rows, never invented SKUs.
4. Add / remove / accept-suggestion all require the calling session to **own** the cart.
5. An optional budget mentioned in chat biases search and suggestions only.
6. Checkout → the same Validator → Payment path as everything else.

### AI Chat Capabilities (OpenAI vs Fallback)

| AI Feature | With OpenAI API Key (`OPENAI_API_KEY`) | Without API Key (Fallback) |
|------------|----------------------------------------|----------------------------|
| **Intent Extraction** | Natural Language via GPT Function Calling | Regex pattern matching (`running_shoes`, `nutrition`, price tags) |
| **Tone & Assistance** | Warm, ChatGPT-style guidance matching catalog DB | Structured template responses with exact DB matches |
| **Budget Awareness** | Honest about price gaps ("No shoes under ₹3k; closest is ₹5.9k") | Direct price filtering on SQL query |
| **Safety Isolation** | **Zero control over money/orders** — LLM output is strictly text | **Zero control over money/orders** |

**LLM allowlist:** intent parsing and reply tone.  
**LLM denylist:** prices, stock, Razorpay calls, PASS tokens, limits.

---

## 12. AI buyer path

`ai_buyer/demo_buyer.py` is an external client: it authenticates with `X-AI-Buyer-Key`, calls the same catalog tools, and checks out through the **identical** Validator and Payment stack a human uses — there's no second, weaker payment pipeline for machines. When a request is flagged `is_ai_buyer`, the tighter AI-buyer limits apply automatically.

**Why one gate for both humans and machines?** A second path, even a well-intentioned one, is a second thing that can drift out of sync with the safety rules over time. One gate means one place to audit and one place to fix.

---

## 13. Audit log

Append-only events capture actor, action, decision (`PASS` / `BLOCK` / `INFO`), reason_code, evidence, and timestamp. The admin HTTP API requires `X-Admin-Key`. The UI color-codes decisions (PASS green, BLOCK red, INFO neutral), and an optional analysis endpoint answers aggregate questions — blocked counts, reason-code breakdowns — from real audit rows.

**Why append-only?** Explainability fails if the thing meant to explain a decision can itself be rewritten after the fact — including by a bug, not just by malice.

---

## 14. Security controls

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
| Key validation | `config.py` actively rejects non-test keys (`rzp_test_*` only) |

**Honest residual risk:** the in-process signed token is not a separate payment microservice behind mutual TLS — it's a single-process trust boundary made structurally sound rather than a distributed one.

**Why rate limits on top of everything else:** Money-adjacent routes with no throttling are trivial to hammer — rate limits reduce that surface without changing any Validator rule; they're a blast-radius control, not a correctness control.

---

## 15. Data model

- **Product** — source of truth for `price_paisa`, `stock_quantity`, `is_active`.
- **Cart / CartItem** — charged price at time of add, suggestion flag, `explicitly_accepted` flag, cart status (`OPEN` / `LOCKED` / `PAID`).
- **Order** — Razorpay linkage, status, unique `idempotency_key`.
- **AuditEvent** — actor, action, decision, reason_code, evidence, timestamps.

Seeded from `data/products.json` when the product table is empty at startup.

---

## 16. API surface

| Path | Target Client | Function |
|------|---------------|----------|
| `POST /chat/message` | Human Browser | Natural chat search & conversational reply |
| `POST /chat/add-to-cart` | Human Browser | Add item to active session cart |
| `POST /chat/add-suggestion` | Human Browser | Present unaccepted add-on recommendation |
| `POST /chat/accept-addon` | Human Browser | Explicitly register customer upsell consent |
| `POST /chat/remove-item` | Human Browser | Remove item from cart |
| `POST /chat/checkout` | Human Browser | Initiate Validator verification & Payment execution |
| `GET /chat/cart/{id}` | Human Browser | Cart state sync |
| `GET /catalog/products` | AI Agent Client | Machine-readable product search (`X-AI-Buyer-Key`) |
| `GET /catalog/limits` | AI Agent Client | Query active spending caps & transaction limits |
| `POST /catalog/checkout` | AI Agent Client | Machine-to-Machine checkout execution |
| `GET /admin/audit/events` | Operations / Admin | Query security & validation event logs (`X-Admin-Key`) |
| `GET /admin/audit/summary` | Operations / Admin | Aggregate stats and reason-code analytics |
| `POST /webhooks/razorpay` | Razorpay Gateway | Webhook payment capture handler |
| `/docs` | Developer | OpenAPI documentation (dev mode only) |

---

## 17. Repository layout

```text
safeagent-commerce/
├── ai_buyer/
│   ├── demo_buyer.py          # External AI buyer client
│   └── README.md
├── backend/
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py            # FastAPI entry point + lifespan
│   │   ├── agents/            # shopping, suggestion, catalog, validator, validator_checks, payment
│   │   ├── api/               # chat_*, cart, catalog, webhooks, admin, payment_verify, views, health
│   │   ├── core/              # config, database, limits, security, pass_token, rate_limit, cart_access
│   │   ├── models/            # product, cart, order, audit
      ├── schemas/
│   │   ├── services/          # llm_service, razorpay_service, audit_service, order_fulfillment
│   │   ├── static/            # css/, js/chat/{api,cart,checkout,main,messages,utils}.js, audit.js
│   │   └── templates/         # base, chat, admin/audit.html
│   └── tests/                 # 7 test files — validator, payment, stock, cart, catalog, audit
├── data/
│   └── products.json          # Seed catalog (~70 products)
├── scripts/
│   ├── seed_db.py
│   └── run_demo.sh            # One-command demo runner
├── docker-compose.yml
├── pyproject.toml             # requires-python >= 3.12
├── requirements.txt
├── .env.example
└── README.md
```

---

## 18. Configuration

Copy `.env.example` to `.env`. **Never commit `.env`.**

| Variable | Role | Required? |
|----------|------|-----------|
| `DATABASE_URL` | `postgresql+asyncpg://…` (Supabase Postgres) | **Yes** — rejects SQLite at runtime |
| `RAZORPAY_KEY_ID` | Razorpay **test** key (`rzp_test_*`) | Yes — rejects non-test keys |
| `RAZORPAY_KEY_SECRET` | Razorpay test secret | Yes |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook HMAC secret | Yes |
| `APP_SECRET_KEY` | PASS token HMAC signing key | Yes |
| `AI_BUYER_API_KEY` | Catalog tool auth (`X-AI-Buyer-Key`) | Yes |
| `ADMIN_API_KEY` | Audit API auth (`X-Admin-Key`) | Yes |
| `OPENAI_API_KEY` | Conversational AI replies | Optional — fallback without key |
| `LLM_MODEL` | OpenAI model name | Optional (default: `gpt-4o-mini`) |

Supabase Postgres is the runtime database. `.env.example` ships a Supabase-shaped `DATABASE_URL` template with a password placeholder. SQLite is used only inside `pytest` via `tests/conftest.py`.

```bash
# Transaction pooler:
postgresql+asyncpg://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres

# Session mode:
postgresql+asyncpg://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres
```

---

## 19. Run

**Python:** 3.12+ (`requires-python = ">=3.12"` in `pyproject.toml`).

```bash
cd safeagent-commerce
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` (chat), `http://localhost:8000/admin/audit` (audit log — needs `X-Admin-Key`), `http://localhost:8000/docs` (OpenAPI).

### AI buyer demo

```bash
python ai_buyer/demo_buyer.py
```

### One-command demo

```bash
./scripts/run_demo.sh both   # or: human | ai
```

### Docker

```bash
docker compose up --build
```

---

## 20. Testing

Run the test suite locally using pytest:

```bash
cd backend && pytest tests/ -v
```

| File | What it proves |
|------|-----------------|
| `test_validator.py` | All 8 validator gate outcomes (PASS + 7 BLOCK reason codes) |
| `test_payment.py` | Valid signed PASS accepted; unsigned token rejected; max retries; atomic cart locking |
| `test_cart_security.py` | Session cannot remove items from another session's cart |
| `test_stock.py` | Stock decrements exactly once via `mark_order_captured()` (webhook & verify paths) |
| `test_cart_budget.py` | Budget parsed from chat; items can be removed from open cart |
| `test_catalog.py` | Search, suggestions, catalog tool handlers stay grounded in DB products |
| `test_audit_analysis.py` | Summary stats, blocked counts, reason-code counts from real audit rows |

Tests use in-memory SQLite (`tests/conftest.py`) — no Supabase connection needed for CI.

---

## 21. Demo script

`scripts/run_demo.sh` walks both execution paths:

- **AI buyer path** (`./scripts/run_demo.sh ai`): runs `ai_buyer/demo_buyer.py` end to end — catalog discovery, intent call, checkout through Validator/Payment stack.
- **Human path** (`./scripts/run_demo.sh human`): prints browser URL and suggested first message (*"Show me running shoes under ₹3000"*).
- **Both** (`./scripts/run_demo.sh both`, default): runs AI path, prints human instructions, points to audit log viewer at `/admin/audit`.

---

## 22. Known Limitations & Architectural Gaps

### Fixed System Vulnerabilities (Resolved in Codebase)

| System Fault | Root Cause | Engineering Resolution |
|--------------|------------|------------------------|
| **Dual capture / stock double-decrement** | Webhook and verify-payment mutated stock independently | **Fixed** — both paths funnel through idempotent `mark_order_captured()`; stock decrements exactly once. |
| **SQLite runtime vulnerability** | Bare SQLite allowed fallback without Postgres ACID guarantees | **Fixed** — `config.py` enforces Supabase Postgres via `DATABASE_URL`; SQLite restricted strictly to `pytest`. |
| **Webhook HMAC debug bypass** | Debug flag permitted unverified webhook payloads | **Fixed** — bypass removed; mandatory raw-body HMAC signature check on all webhook invocations. |

### Evaluation Gaps & Platform Limitations (From Systematic Review)

| Dimension | Specific Gap / Architectural Limitation | Impact & Recommended Production Fix |
|-----------|------------------------------------------|-------------------------------------|
| **Architecture** | **Global hard-coded spending limits** | `limits.py` caps transactions at ₹10,000 globally. High-value retail (e.g., Banarasi silk sarees at ₹25,000) would be blocked. *Fix: Implement per-merchant configurable spending policy schema.* |
| **Architecture** | **Single-tenant catalog & DB schema** | No merchant entity or store separation; single global catalog. *Fix: Add multi-tenant `merchant_id` partitioning across products, orders, and audit trails.* |
| **System Flow** | **No stale cart recovery timeout** | If a user opens Razorpay modal (`status='LOCKED'`) and closes the browser, the cart remains locked indefinitely. *Fix: Background worker TTL job to auto-revert stale `LOCKED` carts back to `OPEN` after 15 mins.* |
| **System Flow** | **Stateless error recovery UI** | When the Validator blocks checkout, the UI displays a text warning without actionable recovery steps. *Fix: Interactive guidance (e.g., "Remove item X to get under transaction ceiling").* |
| **UI / UX** | **Missing product image uploads** | Products display SVG placeholder icons instead of high-res photos. *Fix: Multi-media image storage bucket integration (Supabase Storage / S3).* |
| **UI / UX** | **Non-responsive mobile layout** | Cart sidebar is optimized for desktop and does not collapse to a mobile bottom-drawer. *Fix: Responsive CSS drawer breakpoint.* |
| **UI / UX** | **Catalog discovery UI** | Commerce relies strictly on chat; no visual grid browsing, category trees, or faceted search. *Fix: Hybrid storefront with grid catalog + AI chat drawer.* |
| **AI Chat** | **Stateless multi-turn conversation** | Each chat message is parsed independently without multi-turn conversation memory. *Fix: Session-backed message history window passed to LLM intent parser.* |
| **Identity** | **Session-only buyer tracking** | Identity relies on transient `session_id`; no buyer registration, order history, or saved addresses. *Fix: User authentication & persistent buyer profiles.* |

### Intentional Scope Boundaries

| Scope Boundary | Rationale & Architectural Reality |
|----------------|-----------------------------------|
| **"MCP-style" Catalog** | REST HTTP tool-shaped endpoints for `demo_buyer.py` (not a full Model Context Protocol server). |
| **Currency Ledger** | Integer paisa INR currency math throughout; no multi-currency conversion layer. |
| **Payment Lifecycle** | Out-of-scope for Track 01 checkout demo: refunds, dispute handling, and chargeback workflows. |
| **PASS Capability Token** | In-process HMAC-SHA256 token with 15-min TTL; not a distributed microservice signed mandate protocol. |
| **Admin Authorization** | Shared secret `X-Admin-Key` header authentication; suitable for buildathon demo. |
| **Seed Catalog** | Catalog populated from static `data/products.json` file. |
| **Wire Protocol Compliance** | Architectural alignment with AP2 / ACP / x402 principles, not wire-level protocol conformance. |

---

## 23. FAQ

**Q: Why not let the Validator run *inside* the LLM's own function-calling loop?**  
*A: Because safety requires the Validator to be un-skippable, not just available. As a tool the model chooses to call, a manipulated model could simply not call it, or call it and ignore a BLOCK result. As a plain function call sitting in the request handler's control flow, there is no code path to checkout that bypasses it — a static guarantee.*

**Q: Why not use a second LLM as the checker ("LLM proposes, LLM reviews")?**  
*A: Two models agreeing isn't proof of correctness — it's correlated failure. If the first model was successfully prompt-injected, there's no strong reason a second model resists the same manipulation. A deterministic function either reads the database correctly or it doesn't, and that's testable exhaustively.*

**Q: What happens if the LLM is completely unavailable — no API key, or provider is down?**  
*A: Checkout is entirely unaffected. The Validator, Payment, and Catalog agents never call an LLM. The Shopping and Suggestion agents fall back to deterministic replies built on plain SQL — search and suggestions keep working, just with flatter language.*

**Q: Why paisa integers instead of a `Decimal` rupee type?**  
*A: Both avoid float rounding error. Paisa-as-integer was chosen specifically because Razorpay's own API is paisa-denominated, so there's no unit-conversion boundary between how this system thinks about money and how the payment gateway does.*

**Q: Why does the daily ceiling check use `buyer_id` OR `session_id`?**  
*A: `AICheckoutRequest.buyer_id` is required, and human checkout always generates a `session_id` server-side. If both were ever absent, the query would sum spend across the entire platform — raising an error rather than silently proceeding protects against unexpected caller bugs.*

**Q: Why funnel both capture triggers through one function?**  
*A: Two independent writers to the same order/stock state is exactly the dual-capture bug this project resolved. `mark_order_captured()` is idempotent — order status and stock can only ever move once.*

---

*Built for Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce*

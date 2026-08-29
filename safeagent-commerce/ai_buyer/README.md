# SafeAgent Commerce — AI Buyer Client Demo

This directory contains `demo_buyer.py`, an autonomous external AI buyer client demonstrating machine-to-machine commerce using the merchant's Catalog MCP-style tools.

---

## How to Run

1. Ensure the backend server is running:
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

2. Run the demo script in a separate terminal:
   ```bash
   cd ai_buyer
   python demo_buyer.py
   ```

---

## What the Demo Shows

1. **Limits Inspection**: Calls `GET /catalog/limits` to fetch allowed per-transaction and daily ceilings.
2. **Catalog Discovery**: Calls `GET /catalog/products` to discover active, in-stock products.
3. **Purchase Intent Creation**: Calls `POST /catalog/intent` to create a machine purchase intent with an idempotency key.
4. **Validator Safety Gate (PASS Flow)**: Submits to `POST /catalog/checkout`, passing Validator check and creating a Razorpay order.
5. **Validator Safety Gate (BLOCK Flow)**: Intentionally attempts an over-limit transaction — proving the Validator Agent **BLOCKS** the purchase before money touches Razorpay.

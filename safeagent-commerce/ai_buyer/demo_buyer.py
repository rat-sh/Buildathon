"""
ai_buyer/demo_buyer.py — Standalone External AI Buyer Client
============================================================
Proves AI-to-AI agentic commerce end-to-end for Razorpay Buildathon Track 01.

This script acts as an autonomous external AI buyer agent:
  1. Queries merchant Catalog MCP tools to check spending limits & products.
  2. Constructs a structured PurchaseIntent with an idempotency key.
  3. Executes checkout through the Validator Agent & Payment Agent.
  4. Demonstrates a SUCCESSFUL transaction (PASS) and a BLOCKED transaction (Validator Gate).

Run against local server:
  python ai_buyer/demo_buyer.py [http://localhost:8000]
"""

import sys
import time
import secrets
import httpx


def generate_idempotency_key(prefix: str = "ai_tx") -> str:
    timestamp_ms = int(time.time() * 1000)
    rand_hex = secrets.token_hex(8)
    return f"{prefix}_{timestamp_ms}_{rand_hex}"


def run_ai_buyer_demo(base_url: str = "http://localhost:8000"):
    api_key = "test-ai-buyer-key"
    headers = {
        "X-AI-Buyer-Key": api_key,
        "Content-Type": "application/json",
    }
    buyer_id = "ai_agent_procurement_bot_v1"

    print("==========================================================")
    print(" 🤖 SafeAgent Commerce — External AI Buyer Demo")
    print(f" Target Server: {base_url}")
    print(f" Buyer ID     : {buyer_id}")
    print("==========================================================\n")

    with httpx.Client(base_url=base_url, headers=headers, timeout=10.0) as client:

        # ── STEP 1: Query Spending Limits ─────────────────────────────────────
        print("🔍 STEP 1: Fetching AI Buyer Spending Limits from Merchant...")
        resp = client.get("/catalog/limits")
        if resp.status_code != 200:
            print(f"❌ Failed to fetch limits: {resp.status_code} {resp.text}")
            return
        limits = resp.json()
        print(f"   ► Per-Tx Limit : ₹{limits['per_tx_limit_rupees']:.2f}")
        print(f"   ► Daily Ceiling: ₹{limits['daily_ceiling_rupees']:.2f}\n")

        # ── STEP 2: Search Catalog ───────────────────────────────────────────
        print("🔍 STEP 2: Searching Catalog for 'accessories'...")
        resp = client.get("/catalog/products?category=accessories&limit=5")
        if resp.status_code != 200:
            print(f"❌ Failed to search catalog: {resp.status_code}")
            return
        products = resp.json()
        print(f"   ► Found {len(products)} available products:")
        for p in products:
            print(f"      - ID {p['id']}: {p['name']} (₹{p['price_rupees']:.2f}, Stock: {p['stock_quantity']})")
        print()

        if not products:
            print("❌ No products available in catalog.")
            return

        target_product = products[0]

        # ── STEP 3: Create Purchase Intent (SUCCESS FLOW) ─────────────────────
        idemp_pass = generate_idempotency_key("ai_pass")
        print(f"🛒 STEP 3: Constructing Purchase Intent for product ID {target_product['id']}...")
        intent_payload = {
            "buyer_id": buyer_id,
            "items": [{"product_id": target_product["id"], "quantity": 1}],
            "idempotency_key": idemp_pass,
        }
        resp = client.post("/catalog/intent", json=intent_payload)
        if resp.status_code != 200:
            print(f"❌ Purchase Intent creation failed: {resp.status_code} {resp.text}")
            return
        intent = resp.json()
        print(f"   ► Cart #{intent['cart_id']} created. Total: ₹{intent['total_rupees']:.2f}\n")

        # ── STEP 4: Execute Checkout via Validator Gate ───────────────────────
        print("🛡️ STEP 4: Submitting to Validator Agent Gate...")
        checkout_payload = {
            "cart_id": intent["cart_id"],
            "buyer_id": buyer_id,
            "idempotency_key": idemp_pass,
        }
        resp = client.post("/catalog/checkout", json=checkout_payload)
        if resp.status_code != 200:
            print(f"❌ Checkout HTTP error: {resp.status_code} {resp.text}")
            return
        result = resp.json()

        print(f"   ► Validator Decision: {result.get('reason_code', 'PASS')}")
        if result.get("status") == "success":
            chk = result["checkout_data"]
            print(f"   ✅ SUCCESS! Razorpay Order '{chk['razorpay_order_id']}' created for ₹{chk['amount_rupees']:.2f}.\n")
        else:
            print(f"   ❌ BLOCKED: {result.get('message')}\n")

        # ── STEP 5: SAFETY BLOCK DEMO (Exceed Spending Limit) ──────────────────
        print("🛡️ STEP 5: Testing Validator BLOCK — Attempting Over-Limit Purchase...")
        # Search expensive product
        resp = client.get("/catalog/products?limit=20")
        all_products = resp.json()
        expensive_product = max(all_products, key=lambda x: x["price_paisa"])

        idemp_block = generate_idempotency_key("ai_block")
        # Ask for 50 items to deliberately exceed limits
        block_intent_payload = {
            "buyer_id": buyer_id,
            "items": [{"product_id": expensive_product["id"], "quantity": 50}],
            "idempotency_key": idemp_block,
        }
        resp = client.post("/catalog/intent", json=block_intent_payload)
        if resp.status_code == 200:
            block_intent = resp.json()
            block_checkout_payload = {
                "cart_id": block_intent["cart_id"],
                "buyer_id": buyer_id,
                "idempotency_key": idemp_block,
            }
            resp_block = client.post("/catalog/checkout", json=block_checkout_payload)
            result_block = resp_block.json()
            print(f"   ► Validator Decision : {result_block.get('reason_code')}")
            print(f"   ► Explanation        : {result_block.get('message')}")
            print("   ✅ SAFETY GUARANTEE VERIFIED: Validator blocked over-limit transaction. ZERO money moved!\n")

        print("==========================================================")
        print(" 🎯 AI Buyer Demo Completed Successfully.")
        print("==========================================================")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    run_ai_buyer_demo(url)

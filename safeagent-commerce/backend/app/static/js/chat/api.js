/**
 * chat/api.js — Backend API Calls
 * =================================
 * All fetch() calls to backend endpoints in one place.
 * No DOM access. No rendering. Returns raw response data.
 *
 * Cart contract: every mutation returns data with cart_id.
 * Callers must call fetchCart() after mutations to keep UI in sync with DB.
 */

async function apiSendMessage(message, sessionId, cartId, budgetRupees) {
    const body = { message, session_id: sessionId, cart_id: cartId };
    if (budgetRupees != null) body.budget_rupees = budgetRupees;
    const res = await fetch("/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

async function fetchCart(cartId) {
    const res = await fetch(`/chat/cart/${cartId}`);
    if (!res.ok) return null;
    return res.json();
}

async function apiAddToCart(productId, sessionId, cartId) {
    const res = await fetch("/chat/add-to-cart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, quantity: 1, session_id: sessionId, cart_id: cartId })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

async function apiRemoveCartItem(itemId, cartId, sessionId) {
    const res = await fetch("/chat/remove-item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cart_id: cartId, item_id: itemId, session_id: sessionId })
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Remove failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

async function apiAddSuggestion(productId, sessionId, cartId) {
    const res = await fetch("/chat/add-suggestion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, quantity: 1, session_id: sessionId, cart_id: cartId })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

async function apiAcceptAddon(itemId, cartId, sessionId) {
    const res = await fetch("/chat/accept-addon", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cart_id: cartId, item_id: itemId, session_id: sessionId })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

async function apiCheckout(cartId, sessionId) {
    const res = await fetch("/chat/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cart_id: cartId, session_id: sessionId })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

async function apiVerifyPayment(razorpay_order_id, razorpay_payment_id, razorpay_signature, sessionId) {
    /**
     * Send the three Razorpay tokens to backend for HMAC-SHA256 verification.
     * KEY_SECRET is never sent here — it lives only on the server.
     */
    const res = await fetch("/api/verify-payment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
            session_id: sessionId,
        })
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Verification failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

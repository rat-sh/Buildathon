/**
 * chat/api.js — Backend API Calls
 * =================================
 * All fetch() calls to backend endpoints in one place.
 * No DOM access. No rendering. Returns raw response data.
 *
 * Cart contract: every mutation returns data with cart_id.
 * Callers must call fetchCart() after mutations to keep UI in sync with DB.
 */

async function apiSendMessage(message, sessionId, cartId) {
    const res = await fetch("/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId, cart_id: cartId })
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

/**
 * chat/main.js — State + Event Wiring
 * =====================================
 * Shared mutable state and top-level event handlers.
 * Glues api.js + messages.js + cart.js + checkout.js together.
 *
 * Load order in HTML (all deferred):
 *   utils.js → api.js → messages.js → cart.js → checkout.js → main.js
 */

// ── Shared state (read by all modules) ───────────────────────────────────────
const sessionId   = document.getElementById("chat-root").dataset.sessionId;
let activeCartId  = null;
let cartItems     = [];
let checkoutState = "idle";
let userBudgetRupees = (() => {
    const stored = sessionStorage.getItem("budget_" + sessionId);
    return stored ? parseFloat(stored) : null;
})();

// ── Input wiring ──────────────────────────────────────────────────────────────
const chatInput = document.getElementById("chat-input");
const sendBtn   = document.getElementById("send-btn");
chatInput.addEventListener("input", () => { sendBtn.disabled = !chatInput.value.trim(); });

// ── Send message ──────────────────────────────────────────────────────────────
async function handleSend(e) {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    await sendUserMessage(text);
}

async function sendUserMessage(text) {
    appendUserMessage(text);
    chatInput.value = "";
    sendBtn.disabled = true;

    const typingId = appendTypingIndicator();
    scrollToBottom();

    try {
        const data = await apiSendMessage(text, sessionId, activeCartId, userBudgetRupees);
        removeMessageElement(typingId);

        if (data.budget_rupees != null) {
            userBudgetRupees = data.budget_rupees;
            sessionStorage.setItem("budget_" + sessionId, String(userBudgetRupees));
        }

        if (data.cart_id) {
            activeCartId = data.cart_id;
            if (data.cart_summary?.items) {
                cartItems = data.cart_summary.items;
                if (data.cart_summary.status === "paid") checkoutState = "paid";
                updateCartStatusBadge(data.cart_summary.status);
                renderCart();
                updateValidatorBox();
            } else {
                await fetchCartFromBackend();
            }
        }
        appendAIMessage(data);
    } catch (err) {
        removeMessageElement(typingId);
        appendSystemError("Couldn't reach the assistant. Please try again.");
    }
}

function sendQuickPrompt(text) {
    chatInput.value = text;
    sendBtn.disabled = false;
    sendUserMessage(text);
}

// ── Cart mutation handlers ────────────────────────────────────────────────────
async function addToCart(productId, name, priceRupees) {
    try {
        const data = await apiAddToCart(productId, sessionId, activeCartId);
        activeCartId = data.cart_id;
        const btn = document.getElementById("add-btn-" + productId);
        if (btn) {
            btn.disabled = true;
            btn.innerText = "Added";
            btn.style.background = "var(--color-secondary)";
            btn.style.color = "var(--color-muted-foreground)";
        }
        await fetchCartFromBackend();
    } catch (err) {
        alert("Error adding to cart: " + err.message);
    }
}

async function addSuggestionToCart(productId, name, priceRupees, cardElemId) {
    try {
        const data = await apiAddSuggestion(productId, sessionId, activeCartId);
        activeCartId = data.cart_id;
        const card = document.getElementById(cardElemId);
        if (card) {
            card.innerHTML = `<div class="text-xs font-medium py-1 text-amber-800">✨ Added (Requires opt-in accept)</div>`;
        }
        await fetchCartFromBackend();
    } catch (err) {
        alert("Error adding suggestion: " + err.message);
    }
}

async function acceptAddonItem(itemId) {
    try {
        await apiAcceptAddon(itemId, activeCartId, sessionId);
        await fetchCartFromBackend();
    } catch (err) {
        alert("Error accepting add-on: " + err.message);
    }
}

async function removeCartItem(itemId) {
    if (!activeCartId || cartStatus !== "open") return;
    try {
        await apiRemoveCartItem(itemId, activeCartId, sessionId);
        checkoutState = "idle";
        await fetchCartFromBackend();
        // Re-enable add buttons for removed products
        document.querySelectorAll("[id^='add-btn-']").forEach(btn => {
            btn.disabled = false;
            btn.innerText = "+ Add to cart";
            btn.style.background = "";
            btn.style.color = "white";
        });
    } catch (err) {
        alert("Could not remove item: " + err.message);
    }
}

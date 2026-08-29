/**
 * chat.js — Shopping Chat UI Logic
 * ==================================
 * Manages chat messages, product cards, and cart sidebar.
 *
 * Cart contract:
 *   cartItems is a READ-ONLY render cache populated from GET /chat/cart/{id}.
 *   Never mutate it directly — always call fetchCartFromBackend() after API mutations.
 */

// ── State ─────────────────────────────────────────────────────────────────────
const sessionId = document.getElementById("chat-root").dataset.sessionId;
let activeCartId = null;
let cartItems = [];
let checkoutState = "idle"; // "idle" | "validating" | "approved" | "blocked"

// ── DOM refs ──────────────────────────────────────────────────────────────────
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const messagesContainer = document.getElementById("messages-container");

chatInput.addEventListener("input", () => {
    sendBtn.disabled = !chatInput.value.trim();
});

// ── Utils ─────────────────────────────────────────────────────────────────────
function formatINR(price) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency", currency: "INR", maximumFractionDigits: 0
    }).format(price);
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeJs(str) {
    if (!str) return "";
    return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

// ── Cart sync ─────────────────────────────────────────────────────────────────
async function fetchCartFromBackend() {
    if (!activeCartId) return;
    try {
        const res = await fetch(`/chat/cart/${activeCartId}`);
        if (!res.ok) return;
        const data = await res.json();
        cartItems = data.items || [];
        renderCart();
    } catch (_) {
        // Silent — cart shows stale state rather than crash
    }
}

// ── Chat send ─────────────────────────────────────────────────────────────────
async function handleSend(e) {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    appendUserMessage(text);
    chatInput.value = "";
    sendBtn.disabled = true;

    const typingId = appendTypingIndicator();
    scrollToBottom();

    try {
        const res = await fetch("/chat/message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, session_id: sessionId, cart_id: activeCartId })
        });
        const data = await res.json();
        removeMessageElement(typingId);

        if (data.cart_id) {
            activeCartId = data.cart_id;
            if (data.cart_summary?.items) {
                cartItems = data.cart_summary.items;
                renderCart();
            } else {
                await fetchCartFromBackend();
            }
        }
        appendAIMessage(data);
    } catch (err) {
        removeMessageElement(typingId);
        appendSystemError("Failed to connect to AI Assistant service.");
    }
}

// ── Cart mutations ────────────────────────────────────────────────────────────
async function addToCart(productId, name, priceRupees) {
    try {
        const res = await fetch("/chat/add-to-cart", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ product_id: productId, quantity: 1, session_id: sessionId, cart_id: activeCartId })
        });
        const data = await res.json();
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
        const res = await fetch("/chat/add-suggestion", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ product_id: productId, quantity: 1, session_id: sessionId, cart_id: activeCartId })
        });
        const data = await res.json();
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
        await fetch("/chat/accept-addon", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cart_id: activeCartId, item_id: itemId, session_id: sessionId })
        });
        await fetchCartFromBackend();
    } catch (err) {
        alert("Error accepting add-on: " + err.message);
    }
}

// ── Checkout ──────────────────────────────────────────────────────────────────
async function handleCheckout() {
    if (!activeCartId || cartItems.length === 0) return;
    checkoutState = "validating";
    updateValidatorBox();

    try {
        const res = await fetch("/chat/checkout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cart_id: activeCartId, session_id: sessionId })
        });
        const data = await res.json();
        checkoutState = data.is_blocked ? "blocked" : "approved";
        updateValidatorBox(data.reply, data.is_blocked ? data.block_reason_code : "PASS", data.checkout_data);
        await fetchCartFromBackend();
    } catch (err) {
        checkoutState = "blocked";
        updateValidatorBox("Server error: " + err.message, "SERVER_ERROR");
    }
}

// ── Render: cart sidebar ──────────────────────────────────────────────────────
function renderCart() {
    const emptyState = document.getElementById("cart-empty-state");
    const list = document.getElementById("cart-items-list");
    const countEl = document.getElementById("cart-item-count");
    const totalRow = document.getElementById("cart-total-row");
    const totalAmount = document.getElementById("cart-total-amount");
    const checkoutBtn = document.getElementById("checkout-btn");

    if (cartItems.length === 0) {
        emptyState.classList.remove("hidden");
        list.classList.add("hidden");
        totalRow.classList.add("hidden");
        countEl.textContent = "No items yet";
        checkoutBtn.disabled = true;
        checkoutState = "idle";
        updateValidatorBox();
        return;
    }

    emptyState.classList.add("hidden");
    list.classList.remove("hidden");
    totalRow.classList.remove("hidden");

    let total = 0;
    list.innerHTML = cartItems.map(item => {
        total += item.price_rupees * (item.quantity || 1);
        const badge = item.is_suggestion
            ? (item.explicitly_accepted
                ? `<span class="text-[10px] bg-green-50 text-green-700 border border-green-200 px-1.5 py-0.5 rounded font-medium">Opt-in Accepted</span>`
                : `<button onclick="acceptAddonItem(${item.item_id})" class="text-[10px] bg-amber-50 text-amber-800 border border-amber-300 px-1.5 py-0.5 rounded font-semibold hover:bg-amber-100 transition-colors">Accept Addon</button>`)
            : "";
        return `
            <li class="flex items-start gap-3 py-3 border-b last:border-0" style="borderColor: var(--color-border);">
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium truncate" style="color: var(--color-foreground);">${escapeHtml(item.name)}</p>
                    <div class="flex items-center gap-2 mt-0.5">
                        <span class="text-sm font-semibold" style="color: var(--color-primary);">${formatINR(item.price_rupees)}</span>
                        ${badge}
                    </div>
                </div>
            </li>`;
    }).join("");

    countEl.textContent = `${cartItems.length} item${cartItems.length > 1 ? "s" : ""}`;
    totalAmount.textContent = formatINR(total);
    checkoutBtn.disabled = checkoutState === "validating";
}

// ── Render: validator status box ──────────────────────────────────────────────
function updateValidatorBox(customMessage, reasonCode, checkoutData) {
    const box = document.getElementById("validator-status-box");
    const btn = document.getElementById("checkout-btn");

    if (checkoutState === "idle") {
        box.classList.add("hidden");
        btn.textContent = "Checkout";
        btn.style.background = "var(--color-primary)";
        btn.onclick = handleCheckout;
        return;
    }

    box.classList.remove("hidden");

    const configs = {
        validating: {
            bg: "var(--color-secondary)", border: "var(--color-border)",
            html: `<div class="flex items-center gap-2 text-slate-600 font-medium">
                <svg class="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" opacity="0.2"/>
                    <path d="M21 12a9 9 0 00-9-9"/>
                </svg><span>Validator checking...</span></div>
                <p class="text-slate-500">Verifying price, stock, and spending limit</p>`,
            btnText: "Validating...", btnDisabled: true
        },
        approved: {
            bg: "var(--color-success-bg)", border: "var(--color-success-border)",
            html: `<div class="flex items-center gap-2 text-emerald-800 font-semibold">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <polyline points="20 6 9 17 4 12"/>
                </svg><span>Validator Approved (PASS)</span></div>
                <p class="text-emerald-700">${escapeHtml(customMessage || "Price confirmed · Stock available · Within limit")}</p>`,
            btnText: "Pay Now (Razorpay Test Mode)", btnDisabled: false
        },
        blocked: {
            bg: "var(--color-danger-bg)", border: "var(--color-danger-border)",
            html: `<div class="flex items-center gap-2 text-red-800 font-semibold">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg><span>Payment Blocked (${reasonCode || "REJECTED"})</span></div>
                <p class="text-red-700">${escapeHtml(customMessage)}</p>`,
            btnText: "Retry Checkout", btnDisabled: false
        }
    };

    const cfg = configs[checkoutState];
    if (!cfg) return;
    box.style.background = cfg.bg;
    box.style.borderColor = cfg.border;
    box.innerHTML = cfg.html;
    btn.disabled = cfg.btnDisabled;
    btn.textContent = cfg.btnText;

    if (checkoutState === "approved") {
        btn.style.background = "var(--color-accent)";
        btn.onclick = () => alert(`💳 Razorpay Order Created!\nOrder ID: ${checkoutData?.razorpay_order_id}\nAmount: ₹${checkoutData?.amount_rupees}\nTest Mode.`);
    } else if (checkoutState === "blocked") {
        btn.style.background = "var(--color-primary)";
        btn.onclick = handleCheckout;
    }
}

// ── Render: message helpers ───────────────────────────────────────────────────
function appendUserMessage(text) {
    const div = document.createElement("div");
    div.className = "message-enter flex justify-end";
    div.innerHTML = `<div class="max-w-md px-4 py-3 rounded-2xl rounded-tr-sm text-sm leading-relaxed shadow-sm"
         style="background: var(--color-primary); color: var(--color-primary-foreground);">${escapeHtml(text)}</div>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function appendTypingIndicator() {
    const id = "typing-" + Date.now();
    const div = document.createElement("div");
    div.id = id;
    div.className = "message-enter flex gap-3 max-w-2xl";
    div.innerHTML = `
        <div class="shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5"
             style="background: var(--color-secondary); border: 1px solid var(--color-border);">
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
                <path d="M7 1L12 4v3c0 3-2 5-5 6C4 13 2 11 2 7V4L7 1z" fill="var(--color-primary)" fill-opacity="0.85"/>
            </svg>
        </div>
        <div class="flex items-center gap-1.5 py-3">
            <span class="w-2 h-2 rounded-full bg-slate-400 animate-bounce"></span>
            <span class="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:0.2s]"></span>
            <span class="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:0.4s]"></span>
        </div>`;
    messagesContainer.appendChild(div);
    return id;
}

function removeMessageElement(id) {
    document.getElementById(id)?.remove();
}

function appendSystemError(text) {
    const div = document.createElement("div");
    div.className = "message-enter flex justify-center";
    div.innerHTML = `<div class="text-xs text-red-600 bg-red-50 border border-red-200 px-3 py-1.5 rounded-lg">${escapeHtml(text)}</div>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function appendAIMessage(data) {
    const div = document.createElement("div");
    div.className = "message-enter flex gap-3 max-w-2xl";

    const aiIcon = `
        <div class="shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5"
             style="background: var(--color-secondary); border: 1px solid var(--color-border);">
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
                <path d="M7 1L12 4v3c0 3-2 5-5 6C4 13 2 11 2 7V4L7 1z" fill="var(--color-primary)" fill-opacity="0.85"/>
            </svg>
        </div>`;

    let body = `<div class="text-sm leading-relaxed" style="color: var(--color-foreground);">${escapeHtml(data.reply)}</div>`;

    if (data.products?.length > 0) {
        const cards = data.products.map(p => {
            const inCart = cartItems.some(i => i.product_id === p.id);
            return `
                <div class="product-card rounded-xl border p-4 flex flex-col gap-3"
                     style="background: var(--color-card); borderColor: var(--color-border);">
                    <span class="self-start text-[11px] font-medium px-2 py-0.5 rounded-full"
                          style="background: var(--color-secondary); color: var(--color-primary);">
                        In Stock (${p.stock_quantity})
                    </span>
                    <div>
                        <p class="text-sm font-semibold" style="color: var(--color-foreground);">${escapeHtml(p.name)}</p>
                        <p class="text-xs mt-1 leading-relaxed line-clamp-2" style="color: var(--color-muted-foreground);">${escapeHtml(p.description || p.category)}</p>
                    </div>
                    <div class="flex items-center justify-between mt-auto pt-2">
                        <span class="text-sm font-bold" style="color: var(--color-foreground);">${formatINR(p.price_rupees)}</span>
                        <button id="add-btn-${p.id}" onclick="addToCart(${p.id}, '${escapeJs(p.name)}', ${p.price_rupees})"
                                ${inCart ? "disabled" : ""}
                                class="text-xs font-medium px-3 py-1.5 rounded-lg transition-all disabled:opacity-60"
                                style="background: ${inCart ? "var(--color-secondary)" : "var(--color-primary)"}; color: ${inCart ? "var(--color-muted-foreground)" : "white"};">
                            ${inCart ? "Added" : "Add to cart"}
                        </button>
                    </div>
                </div>`;
        }).join("");
        body += `<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">${cards}</div>`;
    }

    if (data.suggestions?.length > 0) {
        data.suggestions.forEach(s => {
            const sugId = "sug-" + Date.now() + "-" + s.product_id;
            body += `
                <div id="${sugId}" class="rounded-xl p-4 border transition-all" style="background: #fffbeb; borderColor: #fde68a;">
                    <p class="text-[11px] font-medium mb-1 tracking-wider uppercase" style="color: #92400e;">SUGGESTED ADD-ON</p>
                    <p class="text-sm font-semibold" style="color: var(--color-foreground);">${escapeHtml(s.name)}</p>
                    <p class="text-xs mt-0.5" style="color: var(--color-muted-foreground);">${escapeHtml(s.rationale)}</p>
                    <p class="text-sm font-semibold mt-2" style="color: var(--color-foreground);">${formatINR(s.price_rupees)}</p>
                    <div class="flex gap-2 mt-3">
                        <button onclick="addSuggestionToCart(${s.product_id}, '${escapeJs(s.name)}', ${s.price_rupees}, '${sugId}')"
                                class="flex-1 py-2 rounded-lg text-xs font-medium shadow-sm"
                                style="background: var(--color-primary); color: white;">Add to cart</button>
                        <button onclick="document.getElementById('${sugId}').remove()"
                                class="flex-1 py-2 rounded-lg text-xs font-medium border bg-white"
                                style="color: var(--color-muted-foreground); borderColor: var(--color-border);">Skip</button>
                    </div>
                </div>`;
        });
    }

    div.innerHTML = `${aiIcon}<div class="flex-1 space-y-4">${body}</div>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

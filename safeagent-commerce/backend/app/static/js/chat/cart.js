/**
 * chat/cart.js — Cart Sidebar + Validator Box Rendering
 * ======================================================
 * Renders the cart sidebar from the shared `cartItems` state.
 * fetchCartFromBackend() is the ONLY way cartItems gets populated —
 * it calls GET /chat/cart/{id} after every mutation.
 *
 * updateValidatorBox() renders the checkout status UI.
 */

async function fetchCartFromBackend() {
    if (!activeCartId) return;
    try {
        const data = await fetchCart(activeCartId);
        if (!data) return;
        cartItems = data.items || [];
        if (data.status === "paid") {
            checkoutState = "paid";
        }
        renderCart();
        updateValidatorBox();
    } catch (_) {
        // Silent — cart shows stale state rather than crash
    }
}

function renderCart() {
    const emptyState = document.getElementById("cart-empty-state");
    const list       = document.getElementById("cart-items-list");
    const countEl    = document.getElementById("cart-item-count");
    const totalRow   = document.getElementById("cart-total-row");
    const totalEl    = document.getElementById("cart-total-amount");
    const btn        = document.getElementById("checkout-btn");

    if (cartItems.length === 0) {
        emptyState.classList.remove("hidden");
        list.classList.add("hidden");
        totalRow.classList.add("hidden");
        countEl.textContent = "No items yet";
        btn.disabled = true;
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
    totalEl.textContent = formatINR(total);
    btn.disabled = checkoutState === "validating" || checkoutState === "paid";
}

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
        },
        paid: {
            bg: "var(--color-success-bg)", border: "var(--color-success-border)",
            html: `<div class="flex items-center gap-2 text-emerald-800 font-semibold">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <polyline points="20 6 9 17 4 12"/>
                </svg><span>Order Complete</span></div>
                <p class="text-emerald-700">Payment captured. Add new items to start another order.</p>`,
            btnText: "Paid", btnDisabled: true
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
        btn.onclick = () => openRazorpayModal(checkoutData);
    } else if (checkoutState === "blocked") {
        btn.style.background = "var(--color-primary)";
        btn.onclick = handleCheckout;
    }
}

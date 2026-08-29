/**
 * chat/cart.js — Cart Sidebar + Validator Box Rendering
 */

let cartStatus = "open";

function updateCartStatusBadge(status) {
    cartStatus = status || "open";
    const badge = document.getElementById("cart-status-badge");
    if (!badge) return;

    if (!activeCartId || cartItems.length === 0) {
        badge.classList.add("hidden");
        return;
    }

    badge.classList.remove("hidden", "open", "locked", "paid", "failed");
    badge.classList.add(cartStatus);

    const labels = {
        open: "● Open",
        locked: "● Awaiting payment",
        paid: "✓ Paid",
        failed: "✗ Failed",
        abandoned: "○ Abandoned",
    };
    badge.textContent = labels[cartStatus] || status;
}

async function fetchCartFromBackend() {
    if (!activeCartId) return;
    try {
        const data = await fetchCart(activeCartId);
        if (!data) return;
        cartItems = data.items || [];
        if (data.status === "paid") {
            checkoutState = "paid";
        } else if (data.status === "locked" && checkoutState === "idle") {
            checkoutState = "idle";
        }
        updateCartStatusBadge(data.status);
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
        updateCartStatusBadge(null);
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
                ? `<span class="text-[10px] bg-green-50 text-green-700 border border-green-200 px-1.5 py-0.5 rounded-full font-medium">✓ Accepted</span>`
                : `<button onclick="acceptAddonItem(${item.item_id})" class="text-[10px] bg-amber-50 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full font-semibold hover:bg-amber-100 transition-colors">Accept add-on</button>`)
            : "";
        const removeBtn = cartStatus === "open" && checkoutState !== "paid"
            ? `<button onclick="removeCartItem(${item.item_id})" class="text-[10px] text-red-600 hover:text-red-800 font-medium px-1.5 py-0.5 rounded hover:bg-red-50 transition-colors" title="Remove from cart">Remove</button>`
            : "";
        return `
            <li class="cart-item-card">
                <div class="cart-item-icon">🛍️</div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium truncate" style="color: var(--color-foreground);">${escapeHtml(item.name)}</p>
                    <div class="flex items-center gap-2 mt-1 flex-wrap">
                        <span class="text-sm font-bold" style="color: var(--color-primary);">${formatINR(item.price_rupees)}</span>
                        ${badge}
                        ${removeBtn}
                    </div>
                </div>
            </li>`;
    }).join("");

    countEl.textContent = `${cartItems.length} item${cartItems.length > 1 ? "s" : ""} · ${formatINR(total)}`;
    totalEl.textContent = formatINR(total);
    btn.disabled = checkoutState === "validating" || checkoutState === "paid";
    btn.classList.toggle("pay-now", checkoutState === "approved");
}

function updateValidatorBox(customMessage, reasonCode, checkoutData) {
    const box = document.getElementById("validator-status-box");
    const btn = document.getElementById("checkout-btn");

    if (checkoutState === "idle") {
        box.classList.add("hidden");
        btn.textContent = "Proceed to Checkout";
        btn.classList.remove("pay-now");
        btn.onclick = handleCheckout;
        return;
    }

    box.classList.remove("hidden");

    const configs = {
        validating: {
            bg: "var(--color-secondary)", border: "var(--color-border)",
            html: `<div class="flex items-center gap-2 text-slate-600 font-semibold">
                <svg class="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" opacity="0.2"/>
                    <path d="M21 12a9 9 0 00-9-9"/>
                </svg><span>Safety Validator checking…</span></div>
                <p class="text-slate-500 mt-1">Verifying price · stock · spending limits · add-on consent</p>`,
            btnText: "Validating…", btnDisabled: true
        },
        approved: {
            bg: "var(--color-success-bg)", border: "var(--color-success-border)",
            html: `<div class="flex items-center gap-2 text-emerald-800 font-semibold">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <polyline points="20 6 9 17 4 12"/>
                </svg><span>Approved — safe to pay</span></div>
                <p class="text-emerald-700 mt-1">${escapeHtml(customMessage || "All safety checks passed. Ready for Razorpay checkout.")}</p>`,
            btnText: "Pay with Razorpay", btnDisabled: false
        },
        blocked: {
            bg: "var(--color-danger-bg)", border: "var(--color-danger-border)",
            html: `<div class="flex items-center gap-2 text-red-800 font-semibold">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg><span>Blocked — ${reasonCode || "REJECTED"}</span></div>
                <p class="text-red-700 mt-1">${escapeHtml(customMessage || "Payment cannot proceed.")}</p>`,
            btnText: "Try Again", btnDisabled: false
        },
        paid: {
            bg: "var(--color-success-bg)", border: "var(--color-success-border)",
            html: `<div class="flex items-center gap-2 text-emerald-800 font-semibold">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <polyline points="20 6 9 17 4 12"/>
                </svg><span>Order complete!</span></div>
                <p class="text-emerald-700 mt-1">Payment captured successfully. Search for more items to start a new order.</p>`,
            btnText: "✓ Paid", btnDisabled: true
        }
    };

    const cfg = configs[checkoutState];
    if (!cfg) return;
    box.style.background = cfg.bg;
    box.style.borderColor = cfg.border;
    box.innerHTML = cfg.html;
    btn.disabled = cfg.btnDisabled;
    btn.textContent = cfg.btnText;
    btn.classList.toggle("pay-now", checkoutState === "approved");

    if (checkoutState === "approved") {
        btn.onclick = () => openRazorpayModal(checkoutData);
    } else if (checkoutState === "blocked") {
        btn.onclick = handleCheckout;
    }
}

/**
 * chat/messages.js — Message Stream Rendering
 */

const AI_ICON_HTML = `
    <div class="shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-0.5 nav-brand-icon">
        <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
            <path d="M7 1L12 4v3c0 3-2 5-5 6C4 13 2 11 2 7V4L7 1z" fill="white" fill-opacity="0.95"/>
        </svg>
    </div>`;

const QUICK_SUGGESTIONS = [
    { label: "Running shoes", query: "running shoes" },
    { label: "Protein bars",  query: "protein bars"  },
    { label: "Socks",         query: "running socks" },
    { label: "Water bottle",  query: "water bottle"  },
    { label: "Recovery gear", query: "foam roller"   },
];

function productIcon() {
    return `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="1.5" stroke-linecap="round">
        <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/>
        <line x1="3" y1="6" x2="21" y2="6"/>
        <path d="M16 10a4 4 0 01-8 0"/>
    </svg>`;
}

function scrollToBottom() {
    const c = document.getElementById("messages-container");
    c.scrollTop = c.scrollHeight;
}

function appendUserMessage(text) {
    const c = document.getElementById("messages-container");
    const div = document.createElement("div");
    div.className = "message-enter flex justify-end";
    div.innerHTML = `<div class="max-w-md px-4 py-3 rounded-2xl rounded-tr-md text-sm leading-relaxed user-bubble">${escapeHtml(text)}</div>`;
    c.appendChild(div);
    scrollToBottom();
}

function appendTypingIndicator() {
    const c = document.getElementById("messages-container");
    const id = "typing-" + Date.now();
    const div = document.createElement("div");
    div.id = id;
    div.className = "message-enter flex gap-3 max-w-2xl";
    div.innerHTML = `${AI_ICON_HTML}
        <div class="ai-bubble rounded-2xl rounded-tl-md px-4 py-3 flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-blue-400 animate-bounce"></span>
            <span class="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:0.15s]"></span>
            <span class="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:0.3s]"></span>
        </div>`;
    c.appendChild(div);
    return id;
}

function removeMessageElement(id) {
    document.getElementById(id)?.remove();
}

function appendSystemError(text) {
    const c = document.getElementById("messages-container");
    const div = document.createElement("div");
    div.className = "message-enter flex justify-center px-4";
    div.innerHTML = `<div class="text-xs text-red-700 bg-red-50 border border-red-200 px-4 py-2 rounded-xl max-w-md text-center leading-relaxed">${escapeHtml(text)}</div>`;
    c.appendChild(div);
    scrollToBottom();
}

function appendSystemInfo(text) {
    const c = document.getElementById("messages-container");
    const div = document.createElement("div");
    div.className = "message-enter flex justify-center px-4";
    div.innerHTML = `<div class="text-xs text-blue-700 bg-blue-50 border border-blue-200 px-4 py-2 rounded-xl max-w-md text-center leading-relaxed">${escapeHtml(text)}</div>`;
    c.appendChild(div);
    scrollToBottom();
}

function buildNoResultsCard(searchQuery) {
    const chips = QUICK_SUGGESTIONS.map(s =>
        `<button class="suggestion-chip" onclick="sendQuickPrompt('${escapeJs(s.query)}')">${escapeHtml(s.label)}</button>`
    ).join("");
    const queryHint = searchQuery ? `for <em>"${escapeHtml(searchQuery)}"</em>` : "";
    return `
        <div class="no-results-card mt-2">
            <div class="no-results-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round">
                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    <line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
                </svg>
            </div>
            <p class="text-sm font-semibold" style="color: var(--color-foreground);">No products found ${queryHint}</p>
            <p class="text-xs mt-1 leading-relaxed" style="color: var(--color-muted-foreground);">
                Nothing matched that search in our catalog. Try one of these:
            </p>
            <div class="flex flex-wrap gap-2 justify-center mt-3">${chips}</div>
        </div>`;
}

function buildProductCard(p) {
    const inCart = cartItems.some(i => i.product_id === p.id);
    return `
        <div class="product-card rounded-xl p-4 flex flex-col gap-3" style="background: var(--color-card);">
            <div class="product-card-thumb">${productIcon()}</div>
            <div>
                <span class="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
                      style="background: var(--color-success-bg); color: var(--color-success);">
                    ${p.stock_quantity} in stock
                </span>
                <p class="text-sm font-semibold mt-2" style="color: var(--color-foreground);">${escapeHtml(p.name)}</p>
                <p class="text-xs mt-1 leading-relaxed line-clamp-2" style="color: var(--color-muted-foreground);">
                    ${escapeHtml(p.description || p.category || "")}
                </p>
            </div>
            <div class="flex items-center justify-between mt-auto pt-1">
                <span class="text-base font-bold" style="color: var(--color-foreground);">${formatINR(p.price_rupees)}</span>
                <button id="add-btn-${p.id}"
                        onclick="addToCart(${p.id}, '${escapeJs(p.name)}', ${p.price_rupees})"
                        ${inCart ? "disabled" : ""}
                        class="text-xs font-semibold px-4 py-2 rounded-xl transition-all disabled:opacity-60 checkout-btn"
                        style="color: ${inCart ? "var(--color-muted-foreground)" : "white"}; ${inCart ? "background: var(--color-secondary); box-shadow: none;" : ""}">
                    ${inCart ? "Added" : "+ Add to cart"}
                </button>
            </div>
        </div>`;
}

function buildSuggestionCard(s) {
    const sugId = "sug-" + Date.now() + "-" + s.product_id;
    return `
        <div id="${sugId}" class="suggestion-card p-4 transition-all">
            <p class="text-[11px] font-bold tracking-wide uppercase mb-2" style="color: #92400e;">Suggested for you</p>
            <p class="text-sm font-semibold" style="color: var(--color-foreground);">${escapeHtml(s.name)}</p>
            <p class="text-xs mt-1 leading-relaxed" style="color: var(--color-muted-foreground);">${escapeHtml(s.rationale)}</p>
            <p class="text-sm font-bold mt-2" style="color: var(--color-foreground);">${formatINR(s.price_rupees)}</p>
            <p class="text-[10px] mt-1" style="color: #92400e;">Requires your explicit approval before checkout</p>
            <div class="flex gap-2 mt-3">
                <button onclick="addSuggestionToCart(${s.product_id}, '${escapeJs(s.name)}', ${s.price_rupees}, '${sugId}')"
                        class="flex-1 py-2.5 rounded-xl text-xs font-semibold checkout-btn" style="color: white;">
                    Add to cart
                </button>
                <button onclick="document.getElementById('${sugId}').remove()"
                        class="flex-1 py-2.5 rounded-xl text-xs font-medium border bg-white hover:bg-slate-50 transition-colors"
                        style="color: var(--color-muted-foreground); borderColor: var(--color-border);">
                    No thanks
                </button>
            </div>
        </div>`;
}

function appendAIMessage(data) {
    const c = document.getElementById("messages-container");
    const div = document.createElement("div");
    div.className = "message-enter flex gap-3 max-w-full";

    let body = `<div class="ai-bubble rounded-2xl rounded-tl-md px-4 py-3.5 text-sm leading-relaxed" style="color: var(--color-foreground);">${escapeHtml(data.reply)}</div>`;

    if (data.products?.length > 0) {
        const cards = data.products.map(buildProductCard).join("");
        body += `<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 mt-3">${cards}</div>`;
    } else if (data._searched) {
        body += buildNoResultsCard(data._query);
    }

    if (data.suggestions?.length > 0) {
        body += `<div class="space-y-3 mt-3">${data.suggestions.map(buildSuggestionCard).join("")}</div>`;
    }

    div.innerHTML = `${AI_ICON_HTML}<div class="flex-1 space-y-1 min-w-0">${body}</div>`;
    c.appendChild(div);
    scrollToBottom();
}

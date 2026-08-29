/**
 * chat/messages.js — Message Stream Rendering
 * =============================================
 * Renders user messages, AI replies, product cards,
 * suggestion cards, typing indicator, and system errors.
 * Reads from shared `cartItems` state to mark in-cart products.
 *
 * All functions append to #messages-container.
 */

const AI_ICON_HTML = `
    <div class="shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5"
         style="background: var(--color-secondary); border: 1px solid var(--color-border);">
        <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
            <path d="M7 1L12 4v3c0 3-2 5-5 6C4 13 2 11 2 7V4L7 1z"
                  fill="var(--color-primary)" fill-opacity="0.85"/>
        </svg>
    </div>`;

function scrollToBottom() {
    const c = document.getElementById("messages-container");
    c.scrollTop = c.scrollHeight;
}

function appendUserMessage(text) {
    const c = document.getElementById("messages-container");
    const div = document.createElement("div");
    div.className = "message-enter flex justify-end";
    div.innerHTML = `<div class="max-w-md px-4 py-3 rounded-2xl rounded-tr-sm text-sm leading-relaxed shadow-sm"
         style="background: var(--color-primary); color: var(--color-primary-foreground);"
    >${escapeHtml(text)}</div>`;
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
        <div class="flex items-center gap-1.5 py-3">
            <span class="w-2 h-2 rounded-full bg-slate-400 animate-bounce"></span>
            <span class="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:0.2s]"></span>
            <span class="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:0.4s]"></span>
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
    div.className = "message-enter flex justify-center";
    div.innerHTML = `<div class="text-xs text-red-600 bg-red-50 border border-red-200 px-3 py-1.5 rounded-lg"
    >${escapeHtml(text)}</div>`;
    c.appendChild(div);
    scrollToBottom();
}

function buildProductCard(p) {
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
                <p class="text-xs mt-1 leading-relaxed line-clamp-2" style="color: var(--color-muted-foreground);">
                    ${escapeHtml(p.description || p.category)}
                </p>
            </div>
            <div class="flex items-center justify-between mt-auto pt-2">
                <span class="text-sm font-bold" style="color: var(--color-foreground);">${formatINR(p.price_rupees)}</span>
                <button id="add-btn-${p.id}"
                        onclick="addToCart(${p.id}, '${escapeJs(p.name)}', ${p.price_rupees})"
                        ${inCart ? "disabled" : ""}
                        class="text-xs font-medium px-3 py-1.5 rounded-lg transition-all disabled:opacity-60"
                        style="background: ${inCart ? "var(--color-secondary)" : "var(--color-primary)"}; color: ${inCart ? "var(--color-muted-foreground)" : "white"};">
                    ${inCart ? "Added" : "Add to cart"}
                </button>
            </div>
        </div>`;
}

function buildSuggestionCard(s) {
    const sugId = "sug-" + Date.now() + "-" + s.product_id;
    return `
        <div id="${sugId}" class="rounded-xl p-4 border transition-all"
             style="background: #fffbeb; borderColor: #fde68a;">
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
}

function appendAIMessage(data) {
    const c = document.getElementById("messages-container");
    const div = document.createElement("div");
    div.className = "message-enter flex gap-3 max-w-2xl";

    let body = `<div class="text-sm leading-relaxed" style="color: var(--color-foreground);">${escapeHtml(data.reply)}</div>`;

    if (data.products?.length > 0) {
        const cards = data.products.map(buildProductCard).join("");
        body += `<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">${cards}</div>`;
    }
    if (data.suggestions?.length > 0) {
        body += data.suggestions.map(buildSuggestionCard).join("");
    }

    div.innerHTML = `${AI_ICON_HTML}<div class="flex-1 space-y-4">${body}</div>`;
    c.appendChild(div);
    scrollToBottom();
}

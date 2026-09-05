/**
 * audit.js — SOC Ops Console: Live Feed Polling, Data Mode Switcher, Hash Chain Verification
 */

let currentIsMock = window.INITIAL_IS_MOCK || false;
let activeFilter = "all";
let pollIntervalId = null;

function filterAudit(type) {
    activeFilter = type;
    document.querySelectorAll(".ops-row[data-decision]").forEach(row => {
        const dec = row.getAttribute("data-decision");
        row.classList.toggle("hidden-row", type !== "all" && dec !== type);
    });

    document.querySelectorAll(".ops-filter-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.filter === type);
    });
}

function toggleEvidence(id) {
    const detail = document.getElementById("detail-" + id);
    const chevron = document.getElementById("chev-" + id);
    if (!detail) return;
    const open = detail.classList.toggle("hidden");
    if (chevron) chevron.textContent = open ? "▸" : "▾";
}

function switchDataMode(isMock) {
    currentIsMock = isMock;
    document.getElementById("mode-live")?.classList.toggle("active", !isMock);
    document.getElementById("mode-mock")?.classList.toggle("active", isMock);
    document.getElementById("seed-mock-btn")?.classList.toggle("hidden", !isMock);
    fetchLiveAuditEvents();
}

async function verifyHashChain() {
    const badge = document.getElementById("soc-chain-badge");
    if (badge) badge.textContent = "⏳ VERIFYING SHA-256...";
    try {
        const headers = {};
        if (window.ADMIN_API_KEY) headers["X-Admin-Key"] = window.ADMIN_API_KEY;
        const res = await fetch("/admin/audit/verify-chain", { headers });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        if (badge) {
            badge.textContent = "✓ HASH-CHAIN VERIFIED";
            badge.className = "px-2 py-0.5 rounded text-[10px] font-bold mono bg-emerald-900/60 text-emerald-300 border border-emerald-500/40";
        }
        alert(`SOC Audit Trail Integrity Result:\n\n• Status: ${data.status}\n• Events Checked: ${data.total_events_checked}\n• Compliance: ${data.compliance}\n• Root Chain Hash: ${data.root_chain_hash}`);
    } catch (err) {
        if (badge) {
            badge.textContent = "⚠ INTEGRITY ERROR";
            badge.className = "px-2 py-0.5 rounded text-[10px] font-bold mono bg-red-900/60 text-red-300 border border-red-500/40";
        }
        alert("Hash chain verification failed: " + err.message);
    }
}

async function seedMockIncident() {
    try {
        const headers = { "Content-Type": "application/json" };
        if (window.ADMIN_API_KEY) headers["X-Admin-Key"] = window.ADMIN_API_KEY;
        const res = await fetch("/admin/audit/seed-mock-incident", {
            method: "POST",
            headers: headers,
        });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        fetchLiveAuditEvents();
    } catch (err) {
        alert("Could not seed mock incident: " + err.message);
    }
}

async function fetchLiveAuditEvents() {
    try {
        const headers = {};
        if (window.ADMIN_API_KEY) headers["X-Admin-Key"] = window.ADMIN_API_KEY;
        const url = `/admin/audit/events?is_mock=${currentIsMock}&limit=100`;
        const res = await fetch(url, { headers });
        if (!res.ok) return;
        const data = await res.json();
        renderAuditEvents(data.events || []);
    } catch (err) {
        console.warn("Failed to poll live audit events", err);
    }
}

function renderAuditEvents(events) {
    const tbody = document.getElementById("audit-tbody");
    if (!tbody) return;

    const rowCountLabel = document.getElementById("row-count-label");
    if (rowCountLabel) rowCountLabel.textContent = `${events.length} rows · auto-updating`;

    if (events.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="10" class="text-center py-8 text-slate-500 text-xs">
                    No ${currentIsMock ? 'mock demo security' : 'live production'} audit events found. ${currentIsMock ? 'Click "+ Seed Demo Threat Incident" to populate mock events.' : 'Shopping chat and live payment operations will log real events here automatically.'}
                </td>
            </tr>`;
        return;
    }

    let passCount = 0, blockCount = 0, infoCount = 0;

    const rowsHtml = events.map(e => {
        const dec = e.decision || "INFO";
        if (dec === "PASS") passCount++;
        else if (dec === "BLOCK") blockCount++;
        else infoCount++;

        const isHidden = activeFilter !== "all" && dec !== activeFilter;

        let threatBadgeClass = "low";
        let threatText = "LOW";
        if (e.threat_level === "CRITICAL") { threatBadgeClass = "critical"; threatText = "CRITICAL"; }
        else if (e.threat_level === "HIGH") { threatBadgeClass = "high"; threatText = "HIGH"; }
        else if (e.threat_level === "MEDIUM") { threatBadgeClass = "medium"; threatText = "MED"; }

        let badgeClass = "info";
        if (dec === "PASS") badgeClass = "pass";
        else if (dec === "BLOCK") badgeClass = "block";
        else if (dec === "ERROR") badgeClass = "error";

        const evStr = e.evidence ? JSON.stringify(e.evidence, null, 2) : "{}";
        const dateStr = new Date(e.created_at).toISOString().replace("T", " ").substring(0, 19) + " UTC";
        const sessBuyer = e.buyer_id || e.session_id || "—";
        const targetStr = `${e.target_type || "—"}:${e.target_id || "—"}`;

        return `
            <tr class="ops-row ${isHidden ? 'hidden-row' : ''}" data-decision="${dec}" onclick="toggleEvidence(${e.id})">
                <td class="mono" style="color: var(--ops-dim); width: 1rem;" id="chev-${e.id}">▸</td>
                <td class="mono" style="white-space: nowrap; color: var(--ops-muted);">${dateStr}</td>
                <td><span class="threat-badge ${threatBadgeClass}">${threatText}</span></td>
                <td class="mono">${e.id}</td>
                <td class="mono">${escapeHtml(e.actor)}</td>
                <td>
                    <span class="mono" style="color: var(--ops-dim);">${escapeHtml(e.action)}</span>
                    <span style="color: var(--ops-muted);"> — </span>
                    <span class="truncate" style="max-width: 260px; display: inline-block; vertical-align: bottom;">${escapeHtml(e.message || "—")}</span>
                </td>
                <td><span class="badge ${badgeClass}">${dec}</span></td>
                <td><span class="reason-code">${escapeHtml(e.reason_code || "—")}</span></td>
                <td class="mono truncate" title="${escapeHtml(targetStr)}">${escapeHtml(targetStr)}</td>
                <td class="mono truncate" title="${escapeHtml(sessBuyer)}">${escapeHtml(sessBuyer)}</td>
            </tr>
            <tr class="ops-detail-row hidden" id="detail-${e.id}">
                <td colspan="10">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <div class="text-[10px] uppercase mb-1" style="color: var(--ops-dim);">Evidence JSON Snapshot</div>
                            <pre class="evidence-json">${escapeHtml(evStr)}</pre>
                        </div>
                        <div class="space-y-2 text-[11px]">
                            <div><span style="color: var(--ops-dim);">Action:</span> <span class="mono">${escapeHtml(e.action)}</span></div>
                            <div><span style="color: var(--ops-dim);">Session:</span> <span class="mono">${escapeHtml(e.session_id || "—")}</span></div>
                            <div><span style="color: var(--ops-dim);">Buyer:</span> <span class="mono">${escapeHtml(e.buyer_id || "—")}</span></div>
                            <div><span style="color: var(--ops-dim);">Target:</span> <span class="mono">${escapeHtml(e.target_type || "—")} / ${escapeHtml(e.target_id || "—")}</span></div>
                            <div><span style="color: var(--ops-dim);">Data Type:</span> <span class="mono">${e.is_mock ? 'MOCK / DEMO INCIDENT' : 'LIVE REAL PROD EVENT'}</span></div>
                        </div>
                    </div>
                </td>
            </tr>`;
    }).join("");

    tbody.innerHTML = rowsHtml;

    // Update stats counters
    const totalEl = document.getElementById("stat-total");
    const passEl = document.getElementById("stat-pass");
    const blockEl = document.getElementById("stat-block");
    const infoEl = document.getElementById("stat-info");
    if (totalEl) totalEl.textContent = events.length;
    if (passEl) passEl.textContent = passCount;
    if (blockEl) blockEl.textContent = blockCount;
    if (infoEl) infoEl.textContent = infoCount;
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function runAnalysis(question) {
    const resultEl = document.getElementById("analysis-result");
    const inputEl = document.getElementById("analysis-input");
    const q = (question || inputEl?.value || "").trim();
    if (!q) return;

    if (inputEl) inputEl.value = q;
    resultEl.textContent = "Querying audit_events…";

    try {
        const headers = { "Content-Type": "application/json" };
        if (window.ADMIN_API_KEY) {
            headers["X-Admin-Key"] = window.ADMIN_API_KEY;
        }
        const res = await fetch("/admin/audit/analyze", {
            method: "POST",
            headers: headers,
            body: JSON.stringify({ question: q }),
        });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        resultEl.textContent = data.answer;
    } catch (err) {
        resultEl.textContent = "Analysis failed: " + err.message;
    }
}

function setQuickQuery(q) {
    const inputEl = document.getElementById("analysis-input");
    if (inputEl) inputEl.value = q;
    runAnalysis(q);
}

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("analysis-form");
    if (form) {
        form.addEventListener("submit", e => {
            e.preventDefault();
            runAnalysis();
        });
    }

    // Start live SOC feed auto-polling every 4 seconds
    pollIntervalId = setInterval(fetchLiveAuditEvents, 4000);
});

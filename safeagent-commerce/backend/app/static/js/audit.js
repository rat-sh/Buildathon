/**
 * audit.js — Ops console: filters, row expand, log analysis panel
 */

function filterAudit(type) {
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
});

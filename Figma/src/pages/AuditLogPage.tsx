import { useState } from "react";

type DecisionStatus = "allowed" | "blocked";

interface AuditRecord {
  id: string;
  status: DecisionStatus;
  reason: string;
  code: string;
  amount: number;
  items: string[];
  timestamp: string;
  user: string;
}

const AUDIT_RECORDS: AuditRecord[] = [
  {
    id: "TXN-8841",
    status: "allowed",
    reason: "All checks passed. Price verified, stock confirmed, order within spending limit.",
    code: "VALIDATOR_PASS_ALL",
    amount: 74999,
    items: ["Dell XPS 15"],
    timestamp: "2026-08-29 · 14:32:07 IST",
    user: "rohan.sharma@acme.com",
  },
  {
    id: "TXN-8840",
    status: "blocked",
    reason: "Cart total exceeds user's monthly spending limit of ₹80,000 by ₹3,499.",
    code: "LIMIT_EXCEEDED",
    amount: 83499,
    items: ["ASUS ProArt Studiobook", "USB-C Docking Station"],
    timestamp: "2026-08-29 · 14:28:44 IST",
    user: "rohan.sharma@acme.com",
  },
  {
    id: "TXN-8837",
    status: "allowed",
    reason: "Order approved. Price matches catalogue, 3 units in stock.",
    code: "VALIDATOR_PASS_ALL",
    amount: 23496,
    items: ["Logitech MX Master 3S", "Desk Organiser Set", "USB Hub 7-Port"],
    timestamp: "2026-08-29 · 11:04:15 IST",
    user: "priya.menon@acme.com",
  },
  {
    id: "TXN-8831",
    status: "blocked",
    reason: "Product price in cart does not match current catalogue price. Possible stale session.",
    code: "PRICE_MISMATCH",
    amount: 54000,
    items: ["Sony WH-1000XM5"],
    timestamp: "2026-08-28 · 17:52:30 IST",
    user: "arjun.v@acme.com",
  },
  {
    id: "TXN-8829",
    status: "blocked",
    reason: "Requested item is out of stock. Payment blocked to prevent failed fulfilment.",
    code: "STOCK_UNAVAILABLE",
    amount: 12999,
    items: ["Keychron K2 Pro Keyboard"],
    timestamp: "2026-08-28 · 15:19:08 IST",
    user: "deepa.krishnan@acme.com",
  },
  {
    id: "TXN-8822",
    status: "allowed",
    reason: "All items in stock. Price verified. Order within approved limit.",
    code: "VALIDATOR_PASS_ALL",
    amount: 4999,
    items: ["USB-C Docking Station"],
    timestamp: "2026-08-28 · 10:43:55 IST",
    user: "rahul.jain@acme.com",
  },
  {
    id: "TXN-8815",
    status: "blocked",
    reason: "Order flagged for manual review. AI recommended a product outside approved category.",
    code: "CATEGORY_POLICY_VIOLATION",
    amount: 129000,
    items: ["MacBook Pro M3 Max"],
    timestamp: "2026-08-27 · 09:11:22 IST",
    user: "neha.gupta@acme.com",
  },
];

const formatPrice = (p: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(p);

type Filter = "all" | "allowed" | "blocked";

export default function AuditLogPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = AUDIT_RECORDS.filter((r) => filter === "all" || r.status === filter);
  const allowedCount = AUDIT_RECORDS.filter((r) => r.status === "allowed").length;
  const blockedCount = AUDIT_RECORDS.filter((r) => r.status === "blocked").length;

  return (
    <div className="h-full scroll-container">
      <div className="max-w-4xl mx-auto px-8 py-8">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--color-foreground)" }}>
            Safety Audit Log
          </h1>
          <p className="text-sm mt-1.5" style={{ color: "var(--color-muted-foreground)" }}>
            Every payment decision is recorded and explainable — nothing happens without a trace.
          </p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-4 mb-7">
          <StatCard label="Total decisions" value={AUDIT_RECORDS.length.toString()} />
          <StatCard
            label="Approved"
            value={allowedCount.toString()}
            color="var(--color-success)"
            bg="var(--color-success-bg)"
            border="var(--color-success-border)"
          />
          <StatCard
            label="Blocked"
            value={blockedCount.toString()}
            color="var(--color-danger)"
            bg="var(--color-danger-bg)"
            border="var(--color-danger-border)"
          />
        </div>

        {/* Filter tabs */}
        <div
          className="flex items-center gap-1 p-1 rounded-xl mb-6 w-fit"
          style={{ background: "var(--color-secondary)", border: "1px solid var(--color-border)" }}
        >
          {(["all", "allowed", "blocked"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="px-4 py-1.5 rounded-lg text-xs font-medium capitalize transition-all"
              style={{
                background: filter === f ? "var(--color-card)" : "transparent",
                color: filter === f ? "var(--color-foreground)" : "var(--color-muted-foreground)",
                boxShadow: filter === f ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
              }}
            >
              {f === "all" ? "All decisions" : f === "allowed" ? "Approved" : "Blocked"}
            </button>
          ))}
        </div>

        {/* Records */}
        <div className="space-y-3">
          {filtered.map((record) => (
            <AuditRow
              key={record.id}
              record={record}
              isExpanded={expanded === record.id}
              onToggle={() => setExpanded(expanded === record.id ? null : record.id)}
            />
          ))}
        </div>

        {/* Footer note */}
        <div
          className="mt-8 rounded-xl px-5 py-4 flex items-start gap-3"
          style={{
            background: "var(--color-secondary)",
            border: "1px solid var(--color-border)",
          }}
        >
          <svg className="shrink-0 mt-0.5" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-muted-foreground)" strokeWidth="2" strokeLinecap="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <div>
            <p className="text-xs font-medium" style={{ color: "var(--color-foreground)" }}>
              Tamper-evident log
            </p>
            <p className="text-xs mt-0.5 leading-relaxed" style={{ color: "var(--color-muted-foreground)" }}>
              These records are written by the Validator, not the AI. The AI cannot modify or delete entries. Each
              record is cryptographically signed and stored immutably.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
  bg,
  border,
}: {
  label: string;
  value: string;
  color?: string;
  bg?: string;
  border?: string;
}) {
  return (
    <div
      className="rounded-xl px-5 py-4 border"
      style={{
        background: bg || "var(--color-card)",
        borderColor: border || "var(--color-border)",
      }}
    >
      <p className="text-xs" style={{ color: "var(--color-muted-foreground)" }}>
        {label}
      </p>
      <p className="text-2xl font-semibold mt-1" style={{ color: color || "var(--color-foreground)" }}>
        {value}
      </p>
    </div>
  );
}

function AuditRow({
  record,
  isExpanded,
  onToggle,
}: {
  record: AuditRecord;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const isAllowed = record.status === "allowed";

  return (
    <div
      className="rounded-xl border overflow-hidden transition-all"
      style={{
        background: "var(--color-card)",
        borderColor: isExpanded ? (isAllowed ? "#86efac" : "#fca5a5") : "var(--color-border)",
      }}
    >
      <button
        onClick={onToggle}
        className="w-full text-left px-5 py-4 flex items-start gap-4 hover:bg-slate-50 transition-colors"
      >
        {/* Status indicator */}
        <div className="shrink-0 mt-0.5">
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full"
            style={{
              background: isAllowed ? "var(--color-success-bg)" : "var(--color-danger-bg)",
              border: `1px solid ${isAllowed ? "var(--color-success-border)" : "var(--color-danger-border)"}`,
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full shrink-0"
              style={{ background: isAllowed ? "#16a34a" : "#dc2626" }}
            />
            <span
              className="text-xs font-semibold"
              style={{ color: isAllowed ? "var(--color-success)" : "var(--color-danger)" }}
            >
              {isAllowed ? "Allowed" : "Blocked"}
            </span>
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm font-medium" style={{ color: "var(--color-foreground)" }}>
              {record.reason}
            </p>
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-sm font-semibold" style={{ color: "var(--color-foreground)" }}>
                {formatPrice(record.amount)}
              </span>
              <svg
                className="transition-transform"
                style={{ transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)" }}
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--color-muted-foreground)"
                strokeWidth="2.5"
                strokeLinecap="round"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </div>
          </div>
          <div className="flex items-center gap-3 mt-1.5">
            <span
              className="mono text-xs px-1.5 py-0.5 rounded"
              style={{
                background: "var(--color-secondary)",
                color: "var(--color-muted-foreground)",
              }}
            >
              {record.code}
            </span>
            <span className="text-xs" style={{ color: "var(--color-muted-foreground)" }}>
              {record.timestamp}
            </span>
          </div>
        </div>
      </button>

      {/* Expanded detail */}
      {isExpanded && (
        <div
          className="px-5 pb-5 pt-1 border-t"
          style={{ borderColor: "var(--color-border)" }}
        >
          <div className="grid grid-cols-2 gap-6 mt-3 text-xs">
            <div className="space-y-3">
              <DetailRow label="Transaction ID" value={record.id} mono />
              <DetailRow label="User" value={record.user} />
              <DetailRow label="Validator code" value={record.code} mono />
            </div>
            <div className="space-y-3">
              <div>
                <p className="font-medium mb-1.5" style={{ color: "var(--color-muted-foreground)" }}>
                  Items reviewed
                </p>
                <ul className="space-y-1">
                  {record.items.map((item) => (
                    <li key={item} className="flex items-center gap-2" style={{ color: "var(--color-foreground)" }}>
                      <span
                        className="w-1 h-1 rounded-full shrink-0"
                        style={{ background: "var(--color-muted-foreground)" }}
                      />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <DetailRow label="Order total" value={formatPrice(record.amount)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="font-medium mb-0.5" style={{ color: "var(--color-muted-foreground)" }}>
        {label}
      </p>
      <p className={mono ? "mono" : ""} style={{ color: "var(--color-foreground)" }}>
        {value}
      </p>
    </div>
  );
}

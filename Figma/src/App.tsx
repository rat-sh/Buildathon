import { useState } from "react";
import ChatPage from "./pages/ChatPage";
import AuditLogPage from "./pages/AuditLogPage";

type Page = "chat" | "audit";

export default function App() {
  const [activePage, setActivePage] = useState<Page>("chat");

  return (
    <div className="h-full flex flex-col" style={{ background: "var(--color-background)" }}>
      {/* Global top nav */}
      <header
        className="shrink-0 border-b"
        style={{ background: "var(--color-card)", borderColor: "var(--color-border)" }}
      >
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Logo mark */}
            <div
              className="w-7 h-7 rounded flex items-center justify-center"
              style={{ background: "var(--color-primary)" }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path
                  d="M7 1L12 4v3c0 3-2 5-5 6C4 13 2 11 2 7V4L7 1z"
                  fill="white"
                  fillOpacity="0.9"
                />
              </svg>
            </div>
            <span className="font-semibold text-sm tracking-tight" style={{ color: "var(--color-foreground)" }}>
              SafeAgent Commerce
            </span>
          </div>

          <nav className="flex items-center gap-1">
            <button
              onClick={() => setActivePage("chat")}
              className="px-4 py-1.5 rounded text-sm font-medium transition-all"
              style={{
                background: activePage === "chat" ? "var(--color-secondary)" : "transparent",
                color: activePage === "chat" ? "var(--color-primary)" : "var(--color-muted-foreground)",
              }}
            >
              Shopping
            </button>
            <button
              onClick={() => setActivePage("audit")}
              className="px-4 py-1.5 rounded text-sm font-medium transition-all"
              style={{
                background: activePage === "audit" ? "var(--color-secondary)" : "transparent",
                color: activePage === "audit" ? "var(--color-primary)" : "var(--color-muted-foreground)",
              }}
            >
              Audit Log
            </button>
          </nav>

          <div className="flex items-center gap-2">
            <div
              className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium mono"
              style={{
                background: "var(--color-success-bg)",
                color: "var(--color-success)",
                border: "1px solid var(--color-success-border)",
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"></span>
              Validator active
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 min-h-0">
        {activePage === "chat" ? <ChatPage /> : <AuditLogPage />}
      </main>
    </div>
  );
}

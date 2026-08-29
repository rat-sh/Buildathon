#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# SafeAgent Commerce — Demo Runner
# Runs the full end-to-end demo for judges
# Usage: ./scripts/run_demo.sh [human|ai|both]
# ─────────────────────────────────────────────────────────────────────────────
set -e

DEMO_MODE=${1:-both}
BASE_URL="http://localhost:8000"

echo "══════════════════════════════════════════════"
echo "  SafeAgent Commerce — Demo Runner"
echo "  Mode: $DEMO_MODE"
echo "══════════════════════════════════════════════"

# Check server is running
if ! curl -sf "$BASE_URL/health" > /dev/null; then
  echo "❌ Server not running at $BASE_URL"
  echo "   Start it with: cd backend && uvicorn app.main:app --reload"
  exit 1
fi

echo "✅ Server is running"

if [[ "$DEMO_MODE" == "ai" || "$DEMO_MODE" == "both" ]]; then
  echo ""
  echo "── AI Buyer Demo ───────────────────────────"
  cd ai_buyer
  python demo_buyer.py
  cd ..
fi

if [[ "$DEMO_MODE" == "human" || "$DEMO_MODE" == "both" ]]; then
  echo ""
  echo "── Human Path ──────────────────────────────"
  echo "  Open your browser: $BASE_URL"
  echo "  Try: 'Show me running shoes under ₹3000'"
  echo "  Then accept a suggestion and say 'confirm'"
fi

echo ""
echo "── Audit Log ───────────────────────────────"
echo "  View at: $BASE_URL/admin/audit"
echo "  Or query API: GET $BASE_URL/admin/audit/events"
echo "════════════════════════════════════════════"

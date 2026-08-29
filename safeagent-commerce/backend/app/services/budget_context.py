"""Budget parsing helpers — user-stated budget vs platform safety limits."""

import re
from typing import Optional


def parse_budget_from_message(message: str) -> Optional[float]:
    """Extract a rupee budget from natural language, e.g. 'budget is 3000'."""
    msg = message.lower().strip()
    patterns = [
        r"budget\s*(?:is|of|around|about|roughly)?\s*₹?\s*([\d,]+)",
        r"(?:spend|spending)\s*(?:up to|around|about)?\s*₹?\s*([\d,]+)",
        r"₹?\s*([\d,]+)\s*(?:budget|max|maximum)",
        r"(?:under|below|less than|max)\s*₹?\s*([\d,]+)",
    ]
    for pat in patterns:
        match = re.search(pat, msg)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def resolve_budget_rupees(stated: Optional[float], message: str) -> Optional[float]:
    """Prefer freshly parsed budget from message; fall back to session-stated budget."""
    parsed = parse_budget_from_message(message)
    if parsed is not None:
        return parsed
    return stated

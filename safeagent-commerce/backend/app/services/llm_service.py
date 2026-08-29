"""
services/llm_service.py — LLM Service Wrapper (OpenAI Function Calling)
========================================================================
Design Principles:
  - LLMs are used ONLY for natural language intent understanding & ranking.
  - LLMs CANNOT execute orders or touch money.
  - Returns structured query parameters (category, query, max_price_paisa, attributes).
  - Includes pure Python fallback parser if OPENAI_API_KEY is not set or API call fails.
"""

import json
from typing import Any, Dict, Optional

import structlog
from app.core.config import settings

logger = structlog.get_logger(__name__)


class LLMService:
    """
    Thin wrapper for OpenAI API function calling.
    Falls back gracefully to keyword matching if LLM key is absent.
    """

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.LLM_MODEL
        self.client = None

        if self.api_key and not self.api_key.startswith("sk-REPLACE_ME"):
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=self.api_key)
            except Exception as e:
                logger.warning("Failed to initialize OpenAI client", error=str(e))

    async def parse_shopping_intent(self, user_prompt: str) -> Dict[str, Any]:
        """
        Parse user natural language prompt into catalog search parameters.

        Returns dict:
          {
            "query": str,
            "category": Optional[str],
            "max_price_paisa": Optional[int],
            "min_price_paisa": Optional[int]
          }
        """
        if not self.client:
            return self._fallback_parse_intent(user_prompt)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_catalog",
                    "description": "Search product catalog based on user criteria",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Keywords like running shoes, socks, bottle"},
                            "category": {"type": "string", "description": "running_shoes, walking_shoes, accessories, nutrition, apparel, equipment, electronics"},
                            "max_price_rupees": {"type": "number", "description": "Maximum price in Indian Rupees"},
                            "min_price_rupees": {"type": "number", "description": "Minimum price in Indian Rupees"},
                        },
                        "required": ["query"],
                    },
                },
            }
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a shopping search intent parser for an e-commerce catalog. Extract search parameters."},
                    {"role": "user", "content": user_prompt},
                ],
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "search_catalog"}},
            )

            tool_calls = response.choices[0].message.tool_calls
            if tool_calls:
                args = json.loads(tool_calls[0].function.arguments)
                max_paisa = int(args["max_price_rupees"] * 100) if args.get("max_price_rupees") else None
                min_paisa = int(args["min_price_rupees"] * 100) if args.get("min_price_rupees") else None
                return {
                    "query": args.get("query", user_prompt),
                    "category": args.get("category"),
                    "max_price_paisa": max_paisa,
                    "min_price_paisa": min_paisa,
                }

        except Exception as e:
            logger.warning("LLM API call failed, falling back to rule parser", error=str(e))

        return self._fallback_parse_intent(user_prompt)

    def _fallback_parse_intent(self, prompt: str) -> Dict[str, Any]:
        """Pure Python fallback parser for offline / test environments."""
        prompt_lower = prompt.lower()
        category = None
        max_price_paisa = None

        if "shoe" in prompt_lower or "sneaker" in prompt_lower or "running" in prompt_lower:
            category = "running_shoes"
        elif "sock" in prompt_lower:
            category = "accessories"
        elif "bottle" in prompt_lower:
            category = "accessories"
        elif "protein" in prompt_lower or "bar" in prompt_lower:
            category = "nutrition"

        # Basic regex-like price extraction ("under 4000", "under ₹4000", "below 3000")
        import re
        price_match = re.search(r'(?:under|below|less than|max|₹|\$)\s*(\d+)', prompt_lower)
        if price_match:
            try:
                rupees = float(price_match.group(1))
                if rupees > 0:
                    max_price_paisa = int(rupees * 100)
            except ValueError:
                pass

        return {
            "query": prompt,
            "category": category,
            "max_price_paisa": max_price_paisa,
            "min_price_paisa": None,
        }

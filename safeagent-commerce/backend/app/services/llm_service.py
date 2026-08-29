"""
services/llm_service.py — LLM Service Wrapper (OpenAI & Fallback)
===================================================================
Design Principles:
  - LLMs are used ONLY for natural language intent understanding & conversation.
  - LLMs CANNOT execute orders or touch money.
  - Returns structured query parameters (category, query, max_price_paisa).
  - Generates warm, natural ChatGPT-style conversational replies for shoppers.
"""

import json
import re
from typing import Any, Dict, Optional, List

import structlog
from app.core.config import settings

logger = structlog.get_logger(__name__)


class LLMService:
    """
    Wrapper for OpenAI API.
    Provides intent parsing and natural conversational responses.
    Falls back gracefully if LLM key is absent or API call fails.
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

    async def generate_conversational_reply(
        self,
        user_message: str,
        products: List[Dict[str, Any]],
    ) -> str:
        """
        Generate a warm, natural ChatGPT-style reply combining conversational guidance
        with real product catalog context.
        """
        msg_lower = user_message.lower().strip()

        # Handle simple greetings without calling LLM (fast & clean)
        if msg_lower in ["hi", "hello", "hey", "hi there", "greetings", "good morning", "good evening"]:
            return "Hello! How can I help you today? Let me know if you're looking for running shoes, fitness gear, or anything else from our catalog."

        if not self.client:
            return self._fallback_reply(user_message, products)

        prod_summaries = []
        for p in products[:5]:
            name = p.get("name", "Product")
            price = p.get("price_rupees", 0)
            desc = p.get("description") or p.get("category") or ""
            prod_summaries.append(f"- {name} (₹{price:,.0f}): {desc}")

        catalog_ctx = "\n".join(prod_summaries) if prod_summaries else "No matching products in catalog."

        system_prompt = (
            "You are a warm, calm, helpful AI Shopping Assistant for SafeAgent Commerce. "
            "You speak with the reassuring, steady tone of a good ChatGPT shopping advisor. "
            "Never use robotic fixed sentences like 'I found X matching items in our catalog for you!'.\n\n"
            "Guidelines:\n"
            "1. Reply warmly and naturally to the user's prompt.\n"
            "2. If products are found, introduce them naturally and explain briefly why they fit the user's request.\n"
            "3. If no products are found or the user asks a general question, answer helpfully and suggest items to search for.\n"
            "4. Keep responses concise (2 to 4 sentences), polite, and natural. Never invent prices or fake items.\n\n"
            f"Matching Catalog Products:\n{catalog_ctx}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
                max_tokens=200,
            )
            reply = response.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception as e:
            logger.warning("LLM reply generation failed, using fallback", error=str(e))

        return self._fallback_reply(user_message, products)

    def _fallback_reply(self, user_message: str, products: List[Dict[str, Any]]) -> str:
        """Clean fallback reply when OpenAI key is absent."""
        if not products:
            return "I couldn't find exact matches in our catalog for that request. Feel free to search for running shoes, socks, protein, or insoles!"
        if len(products) == 1:
            return f"I found a great option in our catalog for you: {products[0].get('name', 'Product')}."
        return f"Here are {len(products)} relevant items from our catalog that match your search:"

    async def parse_shopping_intent(self, user_prompt: str) -> Dict[str, Any]:
        """Parse natural language user prompt into search parameters."""
        if not self.client:
            return self._fallback_parse_intent(user_prompt)

        tools = [{
            "type": "function",
            "function": {
                "name": "search_catalog",
                "description": "Search product catalog based on user criteria",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Keywords like running shoes, socks, bottle"},
                        "category": {"type": "string"},
                        "max_price_rupees": {"type": "number"},
                        "min_price_rupees": {"type": "number"},
                    },
                    "required": ["query"],
                },
            },
        }]

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Extract search parameters from user shopping request."},
                    {"role": "user", "content": user_prompt},
                ],
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "search_catalog"}},
            )
            tool_calls = response.choices[0].message.tool_calls
            if tool_calls:
                args = json.loads(tool_calls[0].function.arguments)
                max_p = int(args["max_price_rupees"] * 100) if args.get("max_price_rupees") else None
                min_p = int(args["min_price_rupees"] * 100) if args.get("min_price_rupees") else None
                return {
                    "query": args.get("query", user_prompt),
                    "category": args.get("category"),
                    "max_price_paisa": max_p,
                    "min_price_paisa": min_p,
                }
        except Exception as e:
            logger.warning("LLM intent parsing failed, using rule fallback", error=str(e))

        return self._fallback_parse_intent(user_prompt)

    def _fallback_parse_intent(self, prompt: str) -> Dict[str, Any]:
        """Pure Python fallback intent parser."""
        prompt_lower = prompt.lower()
        category = None
        max_price_paisa = None

        if any(w in prompt_lower for w in ["shoe", "sneaker", "running", "walk"]):
            category = "running_shoes"
        elif "sock" in prompt_lower or "bottle" in prompt_lower:
            category = "accessories"
        elif "protein" in prompt_lower or "bar" in prompt_lower:
            category = "nutrition"

        price_match = re.search(r'(?:under|below|less than|max|₹|\$)\s*(\d+)', prompt_lower)
        if price_match:
            try:
                max_price_paisa = int(float(price_match.group(1)) * 100)
            except ValueError:
                pass

        return {
            "query": prompt,
            "category": category,
            "max_price_paisa": max_price_paisa,
            "min_price_paisa": None,
        }

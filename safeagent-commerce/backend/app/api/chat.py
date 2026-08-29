"""
api/chat.py — Chat Router Aggregator
======================================
Thin module that assembles all /chat sub-routers.
Each endpoint lives in its own focused file:

  chat_message.py   — POST /chat/message    (search + reply)
  chat_mutations.py — POST /chat/add-to-cart, /add-suggestion, /accept-addon
  chat_checkout.py  — POST /chat/checkout   (validator gate + payment)
  cart.py           — GET  /chat/cart/{id}  (DB state read)
"""

from fastapi import APIRouter

from app.api import chat_checkout, chat_message, chat_mutations

router = APIRouter(tags=["chat"])

router.include_router(chat_message.router)
router.include_router(chat_mutations.router)
router.include_router(chat_checkout.router)

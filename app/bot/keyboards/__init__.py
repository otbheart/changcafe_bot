# app/bot/keyboards/__init__.py
"""Инициализация клавиатур."""

from .client import get_main_menu, get_order_confirmation_kb
from .operator import get_operator_menu

__all__ = ["get_main_menu", "get_order_confirmation_kb", "get_operator_menu"]

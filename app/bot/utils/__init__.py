# app/bot/utils/__init__.py
"""Инициализация утилит."""

from .phone import format_phone, validate_phone
from .text import escape_html, truncate

__all__ = [
    "format_phone",
    "validate_phone",
    "escape_html",
    "truncate",
]

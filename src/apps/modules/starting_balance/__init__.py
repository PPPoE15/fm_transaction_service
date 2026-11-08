"""Публичный API стартового остатка для отчётов."""

from .infrastructure.orm import StartingBalance as StartingBalanceORM

__all__ = ["StartingBalanceORM"]

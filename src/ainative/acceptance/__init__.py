"""Deterministic Stage acceptance and the confirmation gate."""

from .confirmation import confirmation_gate
from .evaluator import StageAcceptance, StageAcceptanceEvaluator

__all__ = ["StageAcceptance", "StageAcceptanceEvaluator", "confirmation_gate"]

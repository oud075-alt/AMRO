"""Empirical validation gate for calibrated metrics."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationResult:
    valid: bool
    sample_count: int
    reason: str


def validate_empirical(sample_count: int, min_samples: int = 30) -> ValidationResult:
    if sample_count < min_samples:
        return ValidationResult(False, sample_count, "insufficient_samples_for_calibration")
    return ValidationResult(True, sample_count, "ok")

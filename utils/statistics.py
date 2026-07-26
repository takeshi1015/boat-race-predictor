"""Formatting/statistics utilities for CLI output."""


def confidence_stars(confidence: float) -> str:
    stars = max(1, min(5, int(round(confidence * 5))))
    return "★" * stars + "☆" * (5 - stars)


def purchase_label(confidence: float, threshold: float = 0.7) -> str:
    return "購入可能" if confidence >= threshold else "参考情報"

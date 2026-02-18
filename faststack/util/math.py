def clamp(lower: float, value: float, upper: float) -> float:
    """Clamp a value between a minimum and maximum value."""
    return max(lower, min(value, upper))

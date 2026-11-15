"""Backoff helper with an injected first-attempt offset bug."""


def backoff(attempt: int, cap: int = 32) -> int:
    if attempt < 0:
        raise ValueError("attempt must be nonnegative")
    return min(cap, 2 ** (attempt + 1))

import pytest
from backoff import backoff


def test_first_delay() -> None:
    assert backoff(0) == 1
    assert backoff(1) == 2


def test_cap() -> None:
    assert backoff(20, cap=30) == 30


def test_invalid_attempt() -> None:
    with pytest.raises(ValueError):
        backoff(-1)

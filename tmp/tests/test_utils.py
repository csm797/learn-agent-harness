"""Tests for tmp.utils."""

from tmp.utils import add, multiply, is_even


def test_add():
    assert add(1, 2) == 3
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(-2, 5) == -10
    assert multiply(0, 100) == 0


def test_is_even():
    assert is_even(0) is True
    assert is_even(2) is True
    assert is_even(3) is False
    assert is_even(-4) is True
    assert is_even(-5) is False

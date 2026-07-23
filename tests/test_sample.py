"""
Sample tests for the boat-race-predictor project.
"""
import pytest


def test_sample_pass():
    """Test that passes to verify pytest setup."""
    assert 1 + 1 == 2


def test_sample_variables():
    """Test variable assignment and comparison."""
    x = 5
    y = 10
    assert x < y
    assert x + y == 15


class TestSampleClass:
    """Sample test class."""

    def test_method_one(self):
        """Test method one."""
        data = [1, 2, 3, 4, 5]
        assert len(data) == 5

    def test_method_two(self):
        """Test method two."""
        text = "boat-race-predictor"
        assert "boat" in text
        assert text.startswith("boat")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

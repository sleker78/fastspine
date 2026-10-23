from fastspine.util.math import clamp


def test_clamp():
    """Test the clamp function to ensure it correctly limits values."""
    assert clamp(0, 5, 10) == 5
    assert clamp(0, -1, 10) == 0
    assert clamp(0, 20, 10) == 10

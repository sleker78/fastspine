class RepresentableMixin:
    """Mixin class to provide a __repr__ method for classes."""

    def __repr__(self):
        """Return a string representation of the instance."""
        cls_name = self.__class__.__name__
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{cls_name}({attrs})"

    def __str__(self):
        """Return a string representation of the instance."""
        return self.__repr__()

class FactoryService:
    """Service for managing factories loading for services."""

    @classmethod
    def dependency(cls):
        """Create a FastAPI dependency that returns a default instance of this service."""

        def factory() -> "FactoryService":
            return cls()

        return factory

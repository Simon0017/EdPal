"""
Repositories package for analytics.

Exposes the concrete repository implementation used throughout the
application.  Analytics services depend on the
:class:`~analytics.typing.ActivityRepositoryProtocol` interface
rather than this concrete class directly, enabling dependency injection.
"""

from analytics.repositories.activity_repository import ActivityRepository

__all__ = ["ActivityRepository"]

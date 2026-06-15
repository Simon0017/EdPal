"""
Dedicated caching service for analytics.

Analytics services must never interact with ``django.core.cache`` directly.
All caching goes through this service.

Design decisions
----------------
* Backend-agnostic: uses Django's ``cache`` abstraction.
* Graceful degradation: cache failures are logged as warnings and the
  caller receives None / the callable result; no exception propagates.
* Thread-safe: Django's cache backends are expected to be thread-safe.
* Timeout defaults are resolved from application settings.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, TypeVar

from django.core.cache import cache

from analytics.settings.defaults import (
    get_cache_timeout,
    get_geoip_cache_timeout,
    get_realtime_cache_timeout,
)
from analytics.typing import CacheKey

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AnalyticsCacheService:
    """
    Wrapper around Django's cache framework providing structured access for
    analytics data.

    All cache operations are guarded with try/except so that a cache
    backend failure never propagates to the analytics caller.
    """

    def get(self, key: CacheKey) -> Optional[Any]:
        """
        Retrieve a cached value.

        Parameters
        ----------
        key:
            The cache key to look up.

        Returns
        -------
        Any or None
            The cached value, or ``None`` on a cache miss or backend error.
        """
        try:
            return cache.get(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Cache GET failed for key=%s: %s", key, exc, exc_info=False
            )
            return None

    def set(
        self,
        key: CacheKey,
        value: Any,
        timeout: Optional[int] = None,
    ) -> None:
        """
        Store a value in the cache.

        Parameters
        ----------
        key:
            The cache key.
        value:
            The value to store.  Must be picklable.
        timeout:
            TTL in seconds.  When ``None``, the application default
            timeout is used.
        """
        resolved_timeout = timeout if timeout is not None else get_cache_timeout()
        try:
            cache.set(key, value, timeout=resolved_timeout)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Cache SET failed for key=%s: %s", key, exc, exc_info=False
            )

    def delete(self, key: CacheKey) -> None:
        """
        Remove a cached entry.

        Parameters
        ----------
        key:
            The cache key to evict.
        """
        try:
            cache.delete(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Cache DELETE failed for key=%s: %s", key, exc, exc_info=False
            )

    def get_or_set(
        self,
        key: CacheKey,
        callable_: Callable[[], T],
        timeout: Optional[int] = None,
    ) -> T:
        """
        Return the cached value for *key* if present; otherwise call
        *callable_*, store the result, and return it.

        If the cache backend is unavailable, *callable_* is invoked and
        the result is returned without caching.

        Parameters
        ----------
        key:
            Cache key.
        callable_:
            Zero-argument callable producing the value to cache.
        timeout:
            TTL in seconds.  Defaults to the configured cache timeout.

        Returns
        -------
        T
            The cached or freshly computed value.
        """
        cached = self.get(key)
        if cached is not None:
            logger.debug("Cache HIT for key=%s", key)
            return cached  # type: ignore[return-value]

        logger.debug("Cache MISS for key=%s; computing value.", key)
        value = callable_()
        self.set(key, value, timeout=timeout)
        return value

    # ------------------------------------------------------------------
    # Convenience wrappers with preset timeouts
    # ------------------------------------------------------------------

    def get_or_set_realtime(
        self,
        key: CacheKey,
        callable_: Callable[[], T],
    ) -> T:
        """``get_or_set`` with the realtime cache timeout."""
        return self.get_or_set(key, callable_, timeout=get_realtime_cache_timeout())

    def get_or_set_geoip(
        self,
        key: CacheKey,
        callable_: Callable[[], T],
    ) -> T:
        """``get_or_set`` with the GeoIP cache timeout."""
        return self.get_or_set(key, callable_, timeout=get_geoip_cache_timeout())

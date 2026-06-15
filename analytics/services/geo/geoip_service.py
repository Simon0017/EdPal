"""
GeoIP service for analytics.

Wraps Django's GeoIP2 integration with:
* Graceful fallback when the database is unavailable.
* Cached lookups via the analytics cache service.
* Structured logging.
* Dependency-injectable design for testing.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from analytics.cache.analytics_cache_service import AnalyticsCacheService
from analytics.cache.cache_keys import geoip_key
from analytics.exceptions import GeoIPUnavailableError
from analytics.settings.defaults import get_geoip_enabled, get_geoip_path
from analytics.typing import GeoIPServiceProtocol, IpAddress

logger = logging.getLogger(__name__)


class GeoIPService:
    """
    Resolves geographic information from IP addresses using the MaxMind
    GeoLite2 database via Django's ``django.contrib.gis.geoip2.GeoIP2``.

    If GeoIP is disabled or the database path is unavailable, all lookups
    return ``None`` without raising exceptions.

    Parameters
    ----------
    cache_service:
        An :class:`~analytics.cache.analytics_cache_service.AnalyticsCacheService`
        instance used to cache lookup results.  Injected for testability.
    geoip_path:
        Filesystem path to the directory containing ``GeoLite2-City.mmdb``.
        When ``None``, resolved from settings.
    enabled:
        When ``False``, all lookups return ``None`` immediately.  When
        ``None``, resolved from settings.
    """

    def __init__(
        self,
        cache_service: Optional[AnalyticsCacheService] = None,
        geoip_path: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self._cache = cache_service or AnalyticsCacheService()
        self._enabled: bool = (
            get_geoip_enabled() if enabled is None else enabled
        )
        self._path: str = geoip_path if geoip_path is not None else get_geoip_path()
        self._geoip_instance = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_geoip(self):
        """
        Return a cached GeoIP2 instance, creating one if necessary.

        Returns
        -------
        GeoIP2 or None
            The GeoIP2 instance, or ``None`` when unavailable.
        """
        if not self._enabled:
            return None

        if self._geoip_instance is not None:
            return self._geoip_instance

        try:
            from django.contrib.gis.geoip2 import GeoIP2
            
            self._geoip_instance = GeoIP2(path=self._path)
            logger.debug("GeoIP2 database loaded from path=%s", self._path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "GeoIP2 database unavailable at path=%s: %s",
                self._path,
                exc,
                exc_info=False,
            )
            self._geoip_instance = None

        return self._geoip_instance

    def _lookup(self, ip_address: IpAddress) -> Dict[str, Optional[str]]:
        """
        Perform a raw GeoIP lookup, returning country_code and city.

        Parameters
        ----------
        ip_address:
            The IP to look up.

        Returns
        -------
        dict
            ``{'country_code': str | None, 'city': str | None}``
        """
        geoip = self._get_geoip()
        if geoip is None:
            return {"country_code": None, "city": None}

        try:
            city_data = geoip.city(ip_address)
            return {
                "country_code": city_data.get("country_code") or None,
                "city": city_data.get("city") or None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "GeoIP lookup failed for ip=%s: %s", ip_address, exc, exc_info=False
            )
            return {"country_code": None, "city": None}

    # ------------------------------------------------------------------
    # Public interface (satisfies GeoIPServiceProtocol)
    # ------------------------------------------------------------------

    def get_location(self, ip_address: IpAddress) -> Dict[str, Optional[str]]:
        """
        Return geographic metadata for *ip_address*.

        Results are cached using the configured GeoIP cache timeout.

        Parameters
        ----------
        ip_address:
            IPv4 or IPv6 address to look up.

        Returns
        -------
        dict
            ``{'country_code': str | None, 'city': str | None}``
        """
        if not self._enabled:
            return {"country_code": None, "city": None}

        key = geoip_key(ip_address)
        return self._cache.get_or_set_geoip(key, lambda: self._lookup(ip_address))

    def get_country(self, ip_address: IpAddress) -> Optional[str]:
        """
        Return the ISO 3166-1 alpha-2 country code for *ip_address*, or None.

        Parameters
        ----------
        ip_address:
            IPv4 or IPv6 address.
        """
        return self.get_location(ip_address).get("country_code")

    def get_city(self, ip_address: IpAddress) -> Optional[str]:
        """
        Return the city name for *ip_address*, or None.

        Parameters
        ----------
        ip_address:
            IPv4 or IPv6 address.
        """
        return self.get_location(ip_address).get("city")

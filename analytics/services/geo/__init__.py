"""
Geo services package for analytics.

Place the GeoLite2-City.mmdb file in this directory and configure:

    ANALYTICS_GEOIP_ENABLED = True
    ANALYTICS_GEOIP_PATH = BASE_DIR / "analytics" / "services" / "geo"
"""

from analytics.services.geo.geoip_service import GeoIPService

__all__ = ["GeoIPService"]

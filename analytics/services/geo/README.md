# GeoIP Database Directory

Place your `GeoLite2-City.mmdb` file in this directory, then configure:

```python
# settings.py
REQUEST_ANALYTICS_GEOIP_ENABLED = True
REQUEST_ANALYTICS_GEOIP_PATH = BASE_DIR / "request_analytics" / "services" / "geo"
```

The database file is excluded from version control.
Download GeoLite2-City from https://dev.maxmind.com/geoip/geolite2-free-geolocation-data

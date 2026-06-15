from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics'

    def ready(self) -> None:
        """Perform application startup tasks."""
        # Import settings validation to ensure required configuration is present
        from analytics.settings.defaults import validate_settings

        validate_settings()
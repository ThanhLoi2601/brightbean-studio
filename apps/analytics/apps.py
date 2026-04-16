import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"
    label = "analytics"
    verbose_name = "Analytics"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(self._register_analytics_collection_task, sender=self)

    @staticmethod
    def _register_analytics_collection_task(sender, **kwargs):
        """Register the recurring analytics collection task after migrations."""
        try:
            from background_task.models import Task

            from apps.analytics.tasks import collect_all_analytics

            # Hourly collection task
            if not Task.objects.filter(verbose_name="collect_all_analytics_hourly").exists():
                collect_all_analytics(
                    repeat=3600,  # Every hour
                    verbose_name="collect_all_analytics_hourly",
                    kwargs={"collection_type": "hourly"},
                )
                logger.info("Registered hourly analytics collection task")

            # Daily collection task (for older posts and account metrics)
            if not Task.objects.filter(verbose_name="collect_all_analytics_daily").exists():
                collect_all_analytics(
                    repeat=86400,  # Every 24 hours
                    verbose_name="collect_all_analytics_daily",
                    kwargs={"collection_type": "daily"},
                )
                logger.info("Registered daily analytics collection task")
        except Exception:
            logger.debug("Skipping analytics collection task registration (database not ready)")

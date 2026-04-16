"""Management command to manually collect analytics."""

from django.core.management.base import BaseCommand

from apps.analytics.tasks import (
    _collect_account_analytics,
    _collect_all_post_analytics,
    _collect_recent_post_analytics,
)


class Command(BaseCommand):
    help = "Manually collect analytics for posts and accounts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            type=str,
            choices=["recent", "all", "accounts", "full"],
            default="full",
            help="Type of collection: recent (last 48h), all (last 30d), accounts, or full",
        )

    def handle(self, *args, **options):
        collection_type = options["type"]

        if collection_type in ("recent", "full"):
            self.stdout.write("Collecting recent post analytics...")
            _collect_recent_post_analytics()
            self.stdout.write(self.style.SUCCESS("? Recent post analytics collected"))

        if collection_type in ("all", "full"):
            self.stdout.write("Collecting all post analytics...")
            _collect_all_post_analytics()
            self.stdout.write(self.style.SUCCESS("? All post analytics collected"))

        if collection_type in ("accounts", "full"):
            self.stdout.write("Collecting account metrics...")
            _collect_account_analytics()
            self.stdout.write(self.style.SUCCESS("? Account metrics collected"))

        self.stdout.write(self.style.SUCCESS("Analytics collection complete!"))

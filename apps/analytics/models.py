"""Analytics data models for storing post and account metrics."""

from django.db import models
from django.utils import timezone

from apps.common.managers import WorkspaceScopedManager


class AnalyticsSnapshot(models.Model):
    """Snapshot of metrics for a platform post at a point in time."""

    platform_post = models.ForeignKey(
        "composer.PlatformPost",
        on_delete=models.CASCADE,
        related_name="analytics_snapshots",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="analytics_snapshots",
    )

    # Metrics
    impressions = models.IntegerField(default=0, help_text="Number of times the post was viewed")
    reach = models.IntegerField(default=0, help_text="Number of unique people who saw it")
    likes = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)
    saves = models.IntegerField(default=0, help_text="Bookmarks, retweets, etc.")
    clicks = models.IntegerField(default=0, help_text="Clicks on links")
    video_views = models.IntegerField(null=True, blank=True, help_text="For video posts only")
    engagement_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Percentage (0-100)",
    )

    # Metadata
    snapshot_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Store raw provider data
    extra = models.JSONField(default=dict, blank=True)

    objects = WorkspaceScopedManager()

    class Meta:
        indexes = [
            models.Index(fields=["platform_post", "snapshot_at"]),
            models.Index(fields=["workspace", "snapshot_at"]),
        ]
        ordering = ["-snapshot_at"]

    def __str__(self):
        return f"Snapshot {self.platform_post.platform_post_id} @ {self.snapshot_at}"


class AccountMetricsSnapshot(models.Model):
    """Snapshot of overall account metrics at a point in time."""

    social_account = models.ForeignKey(
        "social_accounts.SocialAccount",
        on_delete=models.CASCADE,
        related_name="metrics_snapshots",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="account_metrics_snapshots",
    )

    # Metrics
    follower_count = models.IntegerField(default=0)
    following_count = models.IntegerField(default=0)
    post_count = models.IntegerField(default=0)
    profile_views = models.IntegerField(null=True, blank=True)
    website_clicks = models.IntegerField(null=True, blank=True)

    # Metadata
    snapshot_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Store raw provider data
    extra = models.JSONField(default=dict, blank=True)

    objects = WorkspaceScopedManager()

    class Meta:
        indexes = [
            models.Index(fields=["social_account", "snapshot_at"]),
            models.Index(fields=["workspace", "snapshot_at"]),
        ]
        ordering = ["-snapshot_at"]

    def __str__(self):
        return f"Account {self.social_account.display_name} @ {self.snapshot_at}"

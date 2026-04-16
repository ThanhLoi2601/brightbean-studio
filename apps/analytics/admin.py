from django.contrib import admin

from .models import AccountMetricsSnapshot, AnalyticsSnapshot


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "platform_post",
        "impressions",
        "likes",
        "engagement_rate",
        "snapshot_at",
    ]
    list_filter = ["snapshot_at", "platform_post__social_account__platform"]
    search_fields = ["platform_post__platform_post_id"]
    readonly_fields = ["created_at"]


@admin.register(AccountMetricsSnapshot)
class AccountMetricsSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "social_account",
        "follower_count",
        "post_count",
        "snapshot_at",
    ]
    list_filter = ["snapshot_at", "social_account__platform"]
    search_fields = ["social_account__display_name"]
    readonly_fields = ["created_at"]

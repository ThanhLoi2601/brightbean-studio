"""Background tasks for analytics collection."""

import logging
from datetime import timedelta

from background_task import background
from django.utils import timezone

from apps.composer.models import PlatformPost
from apps.social_accounts.models import SocialAccount
from providers import get_provider

from .models import AccountMetricsSnapshot, AnalyticsSnapshot

logger = logging.getLogger(__name__)

# Settings for collection frequency
HIGH_FREQUENCY_HOURS = 48  # Collect hourly for posts published within last 48h
DAILY_CUTOFF_DAYS = 30  # Collect daily for posts up to 30 days old


@background()
def collect_all_analytics_daily():
    """Collect metrics for posts and accounts.
    Daily: collects for older posts and account-level metrics.
    """
    logger.info("Starting Daily analytics collection")

    _collect_all_post_analytics()
    _collect_account_analytics()

@background()
def collect_all_analytics_hourly():
    """Collect metrics for posts and accounts.
    Hourly: collects for recently published posts (<48h).
    """
    logger.info("Starting hourly analytics collection")

    _collect_recent_post_analytics()




def _collect_recent_post_analytics():
    """Collect metrics for posts published within HIGH_FREQUENCY_HOURS."""
    threshold = timezone.now() - timedelta(hours=HIGH_FREQUENCY_HOURS)

    posts = (
        PlatformPost.objects.filter(
            published_at__gte=threshold,
            published_at__isnull=False,
        )
        .select_related("social_account", "post__workspace")
        .exclude(platform_post_id__isnull=True)
    )

    count = 0
    for platform_post in posts:
        try:
            _fetch_and_store_post_metrics(platform_post)
            count += 1
        except Exception as e:
            logger.exception(f"Failed to collect metrics for PlatformPost {platform_post.id}: {e}")

    logger.info(f"Collected metrics for {count} recent posts")


def _collect_all_post_analytics():
    """Collect metrics for all published posts (up to DAILY_CUTOFF_DAYS old)."""
    threshold = timezone.now() - timedelta(days=DAILY_CUTOFF_DAYS)

    posts = (
        PlatformPost.objects.filter(
            published_at__gte=threshold,
            published_at__isnull=False,
        )
        .select_related("social_account", "post__workspace")
        .exclude(platform_post_id__isnull=True)
    )

    count = 0
    for platform_post in posts:
        try:
            _fetch_and_store_post_metrics(platform_post)
            count += 1
        except Exception as e:
            logger.exception(f"Failed to collect metrics for PlatformPost {platform_post.id}: {e}")

    logger.info(f"Collected metrics for {count} posts (up to {DAILY_CUTOFF_DAYS} days old)")


def _fetch_and_store_post_metrics(platform_post: PlatformPost) -> bool:
    """Fetch metrics from provider and store in database.

    Returns:
        True if successful, False otherwise.
    """
    social_account = platform_post.social_account
    workspace = platform_post.post.workspace

    try:
        provider = get_provider(social_account.platform)
    except ValueError:
        logger.warning(f"No provider for platform {social_account.platform}")
        return False

    try:
        metrics = provider.get_post_metrics(
            access_token=social_account.oauth_access_token,
            post_id=platform_post.platform_post_id,
        )
    except NotImplementedError:
        logger.debug(f"{social_account.platform} does not support post metrics")
        return False
    except Exception as e:
        logger.exception(
            f"Failed to fetch metrics for {social_account.platform} post {platform_post.platform_post_id}: {e}"
        )
        return False

    # Calculate engagement rate
    total_engagement = metrics.likes + metrics.engagements + (metrics.extra.get("shares", 0))
    engagement_rate = (total_engagement / metrics.impressions * 100) if metrics.impressions > 0 else 0

    # Store snapshot
    snapshot = AnalyticsSnapshot.objects.create(
        platform_post=platform_post,
        workspace=workspace,
        impressions=metrics.impressions,
        reach=metrics.engagements,  # Platform APIs map reach to different fields
        likes=metrics.likes,
        comments=metrics.extra.get("comments", 0),
        shares=metrics.extra.get("shares", 0),
        saves=metrics.extra.get("saves", 0),
        clicks=metrics.clicks,
        video_views=metrics.extra.get("video_views"),
        engagement_rate=min(engagement_rate, 100),  # Cap at 100%
        extra=metrics.extra,
    )

    logger.debug(f"Stored analytics snapshot {snapshot.id} for post {platform_post.platform_post_id}")
    return True


def _collect_account_analytics():
    """Collect account-level metrics for all connected accounts."""
    accounts = SocialAccount.objects.filter(
        connection_status=SocialAccount.ConnectionStatus.CONNECTED,
    ).select_related("workspace")

    count = 0
    for account in accounts:
        try:
            _fetch_and_store_account_metrics(account)
            count += 1
        except Exception as e:
            logger.exception(f"Failed to collect account metrics for {account.id}: {e}")

    logger.info(f"Collected account metrics for {count} accounts")


def _fetch_and_store_account_metrics(account: SocialAccount) -> bool:
    """Fetch account metrics from provider and store in database.

    Returns:
        True if successful, False otherwise.
    """
    try:
        provider = get_provider(account.platform)
    except ValueError:
        logger.warning(f"No provider for platform {account.platform}")
        return False

    try:
        metrics = provider.get_account_metrics(
            access_token=account.oauth_access_token,
            date_range=(
                timezone.now() - timedelta(days=1),
                timezone.now(),
            ),
        )
    except NotImplementedError:
        logger.debug(f"{account.platform} does not support account metrics")
        return False
    except Exception as e:
        logger.exception(f"Failed to fetch account metrics for {account.id}: {e}")
        return False

    # Store snapshot
    snapshot = AccountMetricsSnapshot.objects.create(
        social_account=account,
        workspace=account.workspace,
        follower_count=metrics.followers,
        profile_views=metrics.extra.get("profile_views"),
        website_clicks=metrics.extra.get("website_clicks"),
        extra=metrics.extra,
    )

    logger.debug(f"Stored account metrics snapshot {snapshot.id} for {account.account_name}")
    return True

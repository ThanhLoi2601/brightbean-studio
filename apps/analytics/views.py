"""Analytics views for displaying metrics and dashboard."""

from datetime import timedelta

from django.db.models import Avg, Max, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from apps.members.models import WorkspaceMembership
from apps.social_accounts.models import SocialAccount
from apps.workspaces.models import Workspace

from .models import AccountMetricsSnapshot, AnalyticsSnapshot


@require_http_methods(["GET"])
def analytics_dashboard(request, workspace_id):
    """Analytics dashboard for a workspace."""
    workspace = get_object_or_404(Workspace, id=workspace_id)

    # Verify user has access
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    has_membership = WorkspaceMembership.objects.filter(
        user=request.user,
        workspace=workspace,
    ).exists()
    if not has_membership:
        return JsonResponse({"error": "You are not a member of this workspace"}, status=403)

    # Check if this is an AJAX request for JSON data
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return _analytics_dashboard_json(request, workspace)

    # Render HTML template
    return render(
        request,
        "analytics/dashboard.html",
        {
            "workspace": workspace,
        },
    )


def _analytics_dashboard_json(request, workspace):
    """Return analytics dashboard data as JSON."""
    # Get date range from query params (default: last 30 days)
    days = int(request.GET.get("days", 30))
    start_date = timezone.now() - timedelta(days=days)

    # Get all snapshots in date range
    all_snapshots = list(
        AnalyticsSnapshot.objects.filter(
            workspace=workspace,
            snapshot_at__gte=start_date,
        ).select_related("platform_post__social_account", "platform_post__post")
    )

    # Keep only latest snapshot per post
    latest_by_post = {}
    for s in all_snapshots:
        post_id = s.platform_post_id
        if post_id not in latest_by_post or s.snapshot_at > latest_by_post[post_id].snapshot_at:
            latest_by_post[post_id] = s
    snapshots = list(latest_by_post.values())

    # Aggregate metrics
    total_metrics = {
        "total_impressions": sum(s.impressions for s in snapshots),
        "total_reach": sum(s.reach for s in snapshots),
        "total_likes": sum(s.likes for s in snapshots),
        "total_comments": sum(s.comments for s in snapshots),
        "total_engagement": sum(s.likes + s.comments + s.shares for s in snapshots),
        "avg_engagement_rate": sum(s.engagement_rate for s in snapshots) / len(snapshots) if snapshots else 0,
    }

    # Per-platform breakdown with detailed metrics
    platform_metrics = {}
    platform_posts = {}
    for snapshot in snapshots:
        platform = snapshot.platform_post.social_account.platform
        post_id = str(snapshot.platform_post.id)

        # Platform totals
        if platform not in platform_metrics:
            platform_metrics[platform] = {
                "impressions": 0,
                "reach": 0,
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "post_count": 0,
                "avg_engagement_rate": 0,
                "total_engagement": 0,
            }

        platform_metrics[platform]["impressions"] += snapshot.impressions
        platform_metrics[platform]["reach"] += snapshot.reach
        platform_metrics[platform]["likes"] += snapshot.likes
        platform_metrics[platform]["comments"] += snapshot.comments
        platform_metrics[platform]["shares"] += snapshot.shares
        platform_metrics[platform]["total_engagement"] += snapshot.likes + snapshot.comments + snapshot.shares
        platform_metrics[platform]["post_count"] += 1

        # Individual posts for this platform
        if platform not in platform_posts:
            platform_posts[platform] = {}

        if post_id not in platform_posts[platform]:
            platform_posts[platform][post_id] = {
                "platform_post_id": snapshot.platform_post.platform_post_id,
                "content": snapshot.platform_post.post.caption[:100] + "..."
                if snapshot.platform_post.post.caption
                else "",
                "published_at": snapshot.platform_post.published_at.isoformat()
                if snapshot.platform_post.published_at
                else None,
                "impressions": snapshot.impressions,
                "reach": snapshot.reach,
                "likes": snapshot.likes,
                "comments": snapshot.comments,
                "shares": snapshot.shares,
                "engagement_rate": float(snapshot.engagement_rate),
                "total_engagement": snapshot.likes + snapshot.comments + snapshot.shares,
                "snapshot_at": snapshot.snapshot_at.isoformat(),
            }

    # Calculate averages for platforms
    for platform, metrics in platform_metrics.items():
        if metrics["post_count"] > 0:
            metrics["avg_engagement_rate"] = float(metrics["total_engagement"] / max(metrics["impressions"], 1) * 100)

    # Top performing posts across all platforms
    top_posts = []
    for platform, posts in platform_posts.items():
        for post_id, post_data in posts.items():
            top_posts.append(
                {
                    "platform": platform,
                    "platform_post_id": post_data["platform_post_id"],
                    "content": post_data["content"],
                    "total_engagement": post_data["total_engagement"],
                    "impressions": post_data["impressions"],
                    "engagement_rate": post_data["engagement_rate"],
                }
            )

    top_posts.sort(key=lambda x: x["total_engagement"], reverse=True)
    top_posts = top_posts[:10]  # Top 10 posts

    # Time series data for trends (daily aggregates) - rebuild from latest snapshots
    ts_data = {}
    for s in snapshots:
        date_key = s.snapshot_at.date().isoformat()
        if date_key not in ts_data:
            ts_data[date_key] = {"date": date_key, "impressions": 0, "likes": 0, "comments": 0, "shares": 0}
        ts_data[date_key]["impressions"] += s.impressions
        ts_data[date_key]["likes"] += s.likes
        ts_data[date_key]["comments"] += s.comments
        ts_data[date_key]["shares"] += s.shares

    time_series_list = []
    for date_key, data in sorted(ts_data.items()):
        data["engagement"] = data["likes"] + data["comments"] + data["shares"]
        time_series_list.append(data)

    # Convert Decimal objects and dates to JSON serializable types
    def serialize_for_json(obj):
        if obj is None:
            return None
        elif isinstance(obj, dict):
            return {k: serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [serialize_for_json(item) for item in obj]
        elif hasattr(obj, "__float__"):
            return float(obj)
        elif hasattr(obj, "isoformat"):  # Date/DateTime objects
            return obj.isoformat()
        elif isinstance(obj, (int, str, bool)):
            return obj
        else:
            # For any other type, try to convert to string
            return str(obj)

    # Convert time_series data properly
    def serialize_time_series_item(item):
        result = {}
        for key, value in item.items():
            if key == "date":
                result[key] = value.isoformat() if hasattr(value, "isoformat") else str(value)
            elif hasattr(value, "__float__"):
                result[key] = float(value)
            elif isinstance(value, (int, str, bool)):
                result[key] = value
            else:
                result[key] = str(value)
        return result

    serialized_time_series = [serialize_time_series_item(item) for item in time_series_list]

    # Create the response data
    response_data = {
        "workspace_id": str(workspace.id),
        "date_range_days": days,
        "total_metrics": serialize_for_json(total_metrics),
        "platform_metrics": serialize_for_json(platform_metrics),
        "platform_posts": serialize_for_json(platform_posts),
        "top_posts": serialize_for_json(top_posts),
        "time_series": serialized_time_series,
    }

    return JsonResponse(response_data)


@require_http_methods(["GET"])
def account_analytics(request, workspace_id, account_id):
    """Analytics for a specific social account."""
    workspace = get_object_or_404(Workspace, id=workspace_id)
    account = get_object_or_404(SocialAccount, id=account_id, workspace=workspace)

    # Verify user has access
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    has_membership = WorkspaceMembership.objects.filter(
        user=request.user,
        workspace=workspace,
    ).exists()
    if not has_membership:
        return JsonResponse({"error": "You are not a member of this workspace"}, status=403)

    # Check if this is an AJAX request for JSON data
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return _account_analytics_json(request, workspace, account)

    # Render HTML template (placeholder for now)
    return JsonResponse({"message": "Account analytics HTML view coming soon", "account": account.display_name})


def _account_analytics_json(request, workspace, account):
    """Return account analytics data as JSON."""
    # Get date range
    days = int(request.GET.get("days", 30))
    start_date = timezone.now() - timedelta(days=days)

    # Account metrics
    account_snapshots = AccountMetricsSnapshot.objects.filter(
        social_account=account,
        snapshot_at__gte=start_date,
    ).order_by("snapshot_at")

    latest_account_metrics = account_snapshots.last()

    # Post metrics
    post_snapshots = AnalyticsSnapshot.objects.filter(
        platform_post__social_account=account,
        snapshot_at__gte=start_date,
    ).select_related("platform_post")

    post_metrics = post_snapshots.aggregate(
        total_impressions=Sum("impressions"),
        total_reach=Sum("reach"),
        total_likes=Sum("likes"),
        total_comments=Sum("comments"),
        avg_engagement_rate=Avg("engagement_rate"),
        post_count=Max("platform_post__id"),  # Rough count
    )

    return JsonResponse(
        {
            "account_id": str(account.id),
            "account_name": account.display_name,
            "platform": account.platform,
            "date_range_days": days,
            "account_metrics": {
                "followers": latest_account_metrics.follower_count if latest_account_metrics else 0,
                "profile_views": latest_account_metrics.profile_views if latest_account_metrics else None,
            },
            "post_metrics": post_metrics,
        }
    )


@require_http_methods(["GET"])
def post_metrics_detail(request, workspace_id, platform_post_id):
    """Detailed metrics for a specific post."""
    workspace = get_object_or_404(Workspace, id=workspace_id)

    # Verify user has access
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    has_membership = WorkspaceMembership.objects.filter(
        user=request.user,
        workspace=workspace,
    ).exists()
    if not has_membership:
        return JsonResponse({"error": "You are not a member of this workspace"}, status=403)

    # Check if this is an AJAX request for JSON data
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return _post_metrics_detail_json(request, workspace, platform_post_id)

    # Render HTML template (placeholder for now)
    return JsonResponse({"message": "Post metrics detail HTML view coming soon", "post_id": platform_post_id})


def _post_metrics_detail_json(request, workspace, platform_post_id):
    """Return post metrics detail data as JSON."""
    # Get all snapshots for this post
    snapshots = (
        AnalyticsSnapshot.objects.filter(
            workspace=workspace,
            platform_post__id=platform_post_id,
        )
        .select_related("platform_post")
        .order_by("snapshot_at")
    )

    if not snapshots.exists():
        return JsonResponse({"error": "No analytics data found"}, status=404)

    latest = snapshots.last()
    snapshots_data = [
        {
            "snapshot_at": s.snapshot_at.isoformat(),
            "impressions": s.impressions,
            "reach": s.reach,
            "likes": s.likes,
            "comments": s.comments,
            "engagement_rate": float(s.engagement_rate),
        }
        for s in snapshots
    ]

    return JsonResponse(
        {
            "platform_post_id": str(latest.platform_post.id),
            "platform": latest.platform_post.social_account.platform,
            "latest_metrics": {
                "impressions": latest.impressions,
                "reach": latest.reach,
                "likes": latest.likes,
                "comments": latest.comments,
                "engagement_rate": float(latest.engagement_rate),
                "snapshot_at": latest.snapshot_at.isoformat(),
            },
            "historical_snapshots": snapshots_data,
        }
    )

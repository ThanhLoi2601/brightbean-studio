"""Tests for analytics collection and models."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import WorkspaceMembership
from apps.social_accounts.models import SocialAccount
from apps.workspaces.models import Workspace
from apps.composer.models import PlatformPost, PublishedPost

from .models import AnalyticsSnapshot, AccountMetricsSnapshot
from .tasks import (
    collect_all_analytics,
    _collect_recent_post_analytics,
    _collect_all_post_analytics,
    _fetch_and_store_post_metrics,
    _collect_account_analytics,
    _fetch_and_store_account_metrics,
)


class AnalyticsModelsTestCase(TestCase):
    """Test analytics models."""

    def setUp(self):
        """Set up test data."""
        self.workspace = Workspace.objects.create(name="Test Workspace")
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            workspace_role=WorkspaceMembership.WorkspaceRole.EDITOR,
        )

        self.social_account = SocialAccount.objects.create(
            workspace=self.workspace,
            user=self.user,
            platform="instagram",
            platform_user_id="123456789",
            display_name="Test Account",
            oauth_access_token="test_token_123",
        )

        self.published_post = PublishedPost.objects.create(
            workspace=self.workspace,
            content="Test post",
        )

        self.platform_post = PlatformPost.objects.create(
            workspace=self.workspace,
            published_post=self.published_post,
            social_account=self.social_account,
            platform="instagram",
            platform_post_id="post_123_456",
            platform_url="https://instagram.com/p/test",
            published_at=timezone.now() - timedelta(hours=1),
        )

    def test_analytics_snapshot_creation(self):
        """Test creating an analytics snapshot."""
        snapshot = AnalyticsSnapshot.objects.create(
            workspace=self.workspace,
            platform_post=self.platform_post,
            impressions=1000,
            reach=800,
            likes=50,
            comments=10,
            engagement_rate=Decimal("6.0"),
        )

        self.assertEqual(snapshot.impressions, 1000)
        self.assertEqual(snapshot.reach, 800)
        self.assertEqual(snapshot.workspace, self.workspace)
        self.assertIsNotNone(snapshot.snapshot_at)

    def test_account_metrics_snapshot_creation(self):
        """Test creating account metrics snapshot."""
        snapshot = AccountMetricsSnapshot.objects.create(
            workspace=self.workspace,
            social_account=self.social_account,
            follower_count=5000,
            following_count=100,
            post_count=250,
        )

        self.assertEqual(snapshot.follower_count, 5000)
        self.assertEqual(snapshot.following_count, 100)
        self.assertEqual(snapshot.social_account, self.social_account)

    def test_analytics_snapshot_ordering(self):
        """Test snapshots are ordered by snapshot_at."""
        snap1 = AnalyticsSnapshot.objects.create(
            workspace=self.workspace,
            platform_post=self.platform_post,
            impressions=100,
            engagement_rate=Decimal("1.0"),
            snapshot_at=timezone.now() - timedelta(hours=2),
        )
        snap2 = AnalyticsSnapshot.objects.create(
            workspace=self.workspace,
            platform_post=self.platform_post,
            impressions=200,
            engagement_rate=Decimal("2.0"),
        )

        snapshots = AnalyticsSnapshot.objects.filter(platform_post=self.platform_post)
        self.assertEqual(snapshots[0].id, snap1.id)
        self.assertEqual(snapshots[1].id, snap2.id)


class AnalyticsCollectionTestCase(TestCase):
    """Test analytics collection tasks."""

    def setUp(self):
        """Set up test data."""
        self.workspace = Workspace.objects.create(name="Test Workspace")
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            workspace_role=WorkspaceMembership.WorkspaceRole.EDITOR,
        )

        self.social_account = SocialAccount.objects.create(
            workspace=self.workspace,
            user=self.user,
            platform="instagram",
            platform_user_id="123456789",
            display_name="Test Account",
            oauth_access_token="test_token_123",
        )

        self.published_post = PublishedPost.objects.create(
            workspace=self.workspace,
            content="Test post",
        )

        self.platform_post = PlatformPost.objects.create(
            workspace=self.workspace,
            published_post=self.published_post,
            social_account=self.social_account,
            platform="instagram",
            platform_post_id="post_123_456",
            platform_url="https://instagram.com/p/test",
            published_at=timezone.now() - timedelta(hours=1),
        )

    @patch("apps.analytics.tasks.get_provider")
    def test_fetch_and_store_post_metrics(self, mock_get_provider):
        """Test fetching and storing post metrics."""
        mock_provider = MagicMock()
        mock_provider.get_post_metrics.return_value = MagicMock(
            impressions=1000,
            reach=800,
            likes=50,
            comments=10,
            shares=5,
            clicks=100,
            engagement_rate=Decimal("6.0"),
        )
        mock_get_provider.return_value = mock_provider

        result = _fetch_and_store_post_metrics(self.platform_post)

        self.assertTrue(result)
        self.assertEqual(AnalyticsSnapshot.objects.count(), 1)

        snapshot = AnalyticsSnapshot.objects.first()
        self.assertEqual(snapshot.impressions, 1000)
        self.assertEqual(snapshot.likes, 50)
        self.assertTrue(mock_provider.get_post_metrics.called)

    @patch("apps.analytics.tasks.get_provider")
    def test_fetch_and_store_account_metrics(self, mock_get_provider):
        """Test fetching and storing account metrics."""
        mock_provider = MagicMock()
        mock_provider.get_account_metrics.return_value = MagicMock(
            follower_count=5000,
            following_count=100,
            post_count=250,
        )
        mock_get_provider.return_value = mock_provider

        result = _fetch_and_store_account_metrics(self.social_account)

        self.assertTrue(result)
        self.assertEqual(AccountMetricsSnapshot.objects.count(), 1)

        snapshot = AccountMetricsSnapshot.objects.first()
        self.assertEqual(snapshot.follower_count, 5000)
        self.assertTrue(mock_provider.get_account_metrics.called)

    @patch("apps.analytics.tasks.get_provider")
    def test_collect_recent_post_analytics(self, mock_get_provider):
        """Test collecting recent post analytics (< 48 hours)."""
        mock_provider = MagicMock()
        mock_provider.get_post_metrics.return_value = MagicMock(
            impressions=500,
            reach=400,
            likes=30,
            comments=5,
            shares=2,
            clicks=50,
            engagement_rate=Decimal("7.0"),
        )
        mock_get_provider.return_value = mock_provider

        _collect_recent_post_analytics()

        # Should have created a snapshot for the recent post
        self.assertTrue(AnalyticsSnapshot.objects.filter(
            platform_post=self.platform_post
        ).exists())

    @patch("apps.analytics.tasks.get_provider")
    def test_collect_recent_post_analytics_filters_old_posts(self, mock_get_provider):
        """Test that old posts are not collected in recent collection."""
        # Create an old post (>48 hours)
        old_post = PlatformPost.objects.create(
            workspace=self.workspace,
            published_post=self.published_post,
            social_account=self.social_account,
            platform="instagram",
            platform_post_id="old_post_123",
            platform_url="https://instagram.com/p/old",
            published_at=timezone.now() - timedelta(days=5),
        )

        mock_provider = MagicMock()
        mock_provider.get_post_metrics.return_value = MagicMock(
            impressions=100,
            engagement_rate=Decimal("1.0"),
        )
        mock_get_provider.return_value = mock_provider

        _collect_recent_post_analytics()

        # Should only create snapshot for recent post, not old post
        self.assertTrue(AnalyticsSnapshot.objects.filter(
            platform_post=self.platform_post
        ).exists())
        self.assertFalse(AnalyticsSnapshot.objects.filter(
            platform_post=old_post
        ).exists())

    @patch("apps.analytics.tasks._fetch_and_store_post_metrics")
    @patch("apps.analytics.tasks._collect_account_analytics")
    def test_collect_all_analytics_hourly(self, mock_account, mock_fetch):
        """Test collect_all_analytics with hourly type."""
        mock_fetch.return_value = True

        collect_all_analytics(collection_type="hourly")

        # Should call fetch for posts (but account metrics only on daily)
        # Note: This depends on how the function is structured

    def test_analytics_workspace_scoping(self):
        """Test that analytics are workspace-scoped."""
        other_workspace = Workspace.objects.create(name="Other Workspace")

        snapshot1 = AnalyticsSnapshot.objects.create(
            workspace=self.workspace,
            platform_post=self.platform_post,
            impressions=1000,
            engagement_rate=Decimal("6.0"),
        )

        # This would fail if model allowed cross-workspace access
        # Verify workspace filtering works
        self.assertEqual(
            AnalyticsSnapshot.objects.filter(workspace=self.workspace).count(), 1
        )
        self.assertEqual(
            AnalyticsSnapshot.objects.filter(workspace=other_workspace).count(), 0
        )

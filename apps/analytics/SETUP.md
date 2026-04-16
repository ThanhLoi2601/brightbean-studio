"""Setup guide for the Analytics system."""

# Analytics System Setup Guide

## Overview

The Analytics system has been implemented to collect and store post and account metrics from all connected social media platforms. It uses the previously-unused `get_post_metrics()` and `get_account_metrics()` methods from provider implementations.

## Architecture

### Components

1. **Models** (`apps/analytics/models.py`)
   - `AnalyticsSnapshot`: Stores post-level metrics at different points in time
   - `AccountMetricsSnapshot`: Stores account-level metrics (followers, following, etc.)

2. **Tasks** (`apps/analytics/tasks.py`)
   - Hourly collection: Fetches metrics for posts published in the last 48 hours
   - Daily collection: Fetches metrics for all posts within the last 30 days
   - Account metrics: Collected daily

3. **Views** (`apps/analytics/views.py`)
   - Dashboard view for workspace-wide metrics
   - Account-specific metrics view
   - Post-specific detailed metrics view

4. **Admin** (`apps/analytics/admin.py`)
   - Django admin interface to browse collected snapshots

## Installation Steps

### Step 1: Create Migrations

```bash
python manage.py makemigrations analytics
python manage.py migrate
```

This creates the database tables for `AnalyticsSnapshot` and `AccountMetricsSnapshot`.

### Step 2: Verify Task Registration

The tasks are automatically registered when the app initializes. To verify:

```bash
# Start the background task worker
python manage.py process_tasks
```

You should see log output like:
```
[INFO] Task registered: collect_all_analytics_hourly (repeat=3600s)
[INFO] Task registered: collect_all_analytics_daily (repeat=86400s)
```

### Step 3: Manual Collection (Testing)

Before relying on automatic collection, test the system:

```bash
# Collect metrics for recent posts (< 48 hours)
python manage.py collect_analytics --type recent

# Collect metrics for all posts (< 30 days)
python manage.py collect_analytics --type all

# Collect account-level metrics
python manage.py collect_analytics --type accounts

# Collect everything
python manage.py collect_analytics --type full
```

## Configuration

### Settings

Configure analytics collection via `apps/settings_manager/defaults.py`:

```python
{
    "analytics": {
        # Collect metrics for posts newer than this (hours)
        "high_frequency_collection_hours": 48,
        # Collect metrics for posts up to this many days old
        "optimal_time_lookback_days": 30,
    }
}
```

## API Endpoints

Once the app is running, use these endpoints to access analytics data:

### Dashboard

```
GET /api/analytics/workspace/<workspace_id>/dashboard/?days=30
```

Returns aggregated metrics for all accounts in the workspace.

**Query Parameters:**
- `days`: Number of days to look back (default: 30)

**Response:**
```json
{
  "workspace_id": "...",
  "date_range_days": 30,
  "total_metrics": {
    "total_impressions": 50000,
    "total_reach": 40000,
    "total_likes": 1200,
    "total_comments": 150,
    "avg_engagement_rate": 5.5
  },
  "platform_metrics": {
    "instagram": {...},
    "facebook": {...}
  },
  "top_posts": [...]
}
```

### Account Analytics

```
GET /api/analytics/workspace/<workspace_id>/account/<account_id>/?days=30
```

Returns metrics for a specific social account.

**Query Parameters:**
- `days`: Number of days to look back (default: 30)

**Response:**
```json
{
  "account_id": "...",
  "account_name": "My Instagram",
  "platform": "instagram",
  "date_range_days": 30,
  "account_metrics": {
    "followers": 5000,
    "profile_views": 1200
  },
  "post_metrics": {
    "total_impressions": 25000,
    "total_likes": 600,
    "avg_engagement_rate": 5.2
  }
}
```

### Post Detail

```
GET /api/analytics/workspace/<workspace_id>/post/<platform_post_id>/
```

Returns detailed metrics history for a specific post.

**Response:**
```json
{
  "platform_post_id": "...",
  "platform": "instagram",
  "latest_metrics": {
    "impressions": 1500,
    "likes": 75,
    "engagement_rate": 5.0,
    "snapshot_at": "2024-01-15T10:30:00Z"
  },
  "historical_snapshots": [
    {
      "snapshot_at": "2024-01-15T09:30:00Z",
      "impressions": 1200,
      "likes": 60,
      ...
    }
  ]
}
```

## How It Works

### Data Collection Flow

1. **Task Scheduler** (django-background-tasks)
   - Hourly: Triggers `collect_all_analytics(collection_type="hourly")`
   - Daily: Triggers `collect_all_analytics(collection_type="daily")`

2. **Collection Task** (`apps/analytics/tasks.py::collect_all_analytics`)
   - Routes to appropriate collection function based on type
   - Catches and logs any errors (doesn't crash the worker)

3. **Post Collection**
   - Queries `PlatformPost` filtered by `published_at`
   - For each post, gets the associated `SocialAccount`
   - Loads the provider implementation (Instagram, Facebook, etc.)
   - Calls `provider.get_post_metrics(access_token, post_id)`
   - Creates `AnalyticsSnapshot` with returned metrics

4. **Account Collection**
   - Queries all `SocialAccount` objects with valid OAuth tokens
   - Calls `provider.get_account_metrics(access_token, date_range)`
   - Creates `AccountMetricsSnapshot` with returned metrics

### Error Handling

Each collection function has try/except blocks:
- If provider API fails ? logs exception, continues with next
- If token expired ? logs warning, skips that account
- If post no longer exists ? logs info, continues

Failed collections don't block the background task worker.

## Monitoring

### Check Collected Snapshots

```bash
python manage.py shell
>>> from apps.analytics.models import AnalyticsSnapshot
>>> AnalyticsSnapshot.objects.count()
45203  # Number of snapshots collected
>>> AnalyticsSnapshot.objects.latest('snapshot_at').snapshot_at
datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=<UTC>)
```

### Check Task Status

```bash
python manage.py shell
>>> from django_background_tasks.models import Task
>>> Task.objects.filter(task_name='apps.analytics.tasks.collect_all_analytics')
```

### View in Admin

Visit: `/admin/analytics/analyticssnapshot/`

Filter by:
- Date range
- Platform
- Workspace

## Development & Testing

### Run Unit Tests

```bash
python manage.py test apps.analytics
```

### Test Collection Manually

```bash
# In Django shell
>>> from apps.analytics.tasks import _collect_recent_post_analytics
>>> _collect_recent_post_analytics()
```

## Troubleshooting

### Snapshots Not Being Created

1. **Check task is registered:**
   ```bash
   python manage.py process_tasks
   ```
   Should show "Task registered" for both hourly/daily tasks

2. **Check database:**
   ```bash
   python manage.py shell
   >>> from django_background_tasks.models import Task
   >>> Task.objects.all()
   ```

3. **Check for posts:**
   ```bash
   >>> from apps.composer.models import PlatformPost
   >>> PlatformPost.objects.filter(published_at__gte=...).count()
   ```

4. **Check OAuth tokens:**
   ```bash
   >>> from apps.social_accounts.models import SocialAccount
   >>> SocialAccount.objects.filter(oauth_access_token__isnull=False).count()
   ```

### Provider API Errors

Check logs during task execution:
```bash
# In terminal running "python manage.py process_tasks"
[ERROR] Failed to collect metrics for Instagram post post_123: "Rate limited by API"
```

This is logged but doesn't stop the worker. Most providers have rate limits that reset after 1 hour.

## Next Steps

1. ? Models and tasks created
2. ? Admin interface added
3. ? API endpoints created
4. ? Tests written
5. **TODO:** Run migrations: `python manage.py makemigrations analytics && python manage.py migrate`
6. **TODO:** Test with `python manage.py collect_analytics --type full`
7. **TODO:** Build frontend dashboard to visualize data
8. **TODO:** Add email reports with key metrics

## Questions?

Refer to:
- `apps/analytics/tasks.py` - Collection logic
- `apps/analytics/models.py` - Data storage
- `providers/base.py` - Available metrics methods

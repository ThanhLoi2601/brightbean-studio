# Analytics UI

The analytics system now includes a complete user interface for viewing social media performance metrics.

## Features

### Dashboard (`/workspace/{id}/analytics/dashboard/`)
- **Overview Cards**: Total impressions, likes, comments, and average engagement rate
- **Platform Breakdown**: Performance metrics broken down by social media platform
- **Top Performing Posts**: List of posts with highest engagement
- **Date Range Selection**: Choose from 7 days, 30 days, 90 days, or 1 year
- **Real-time Refresh**: Button to reload latest analytics data

### Navigation
- Added "Analytics" menu item in the sidebar between "Social Inbox" and "Notifications"
- Only visible when user is in a workspace
- Uses chart/bar graph icon

## Technical Implementation

### Templates
- `templates/analytics/dashboard.html`: Main analytics dashboard with interactive charts and data visualization

### Views
- `analytics_dashboard()`: Handles both HTML rendering and JSON API responses
- Supports AJAX requests for dynamic data loading
- Proper workspace membership validation

### JavaScript
- Dynamic data loading via Fetch API
- Responsive UI with loading states and error handling
- Real-time metric updates

## API Endpoints

The same JSON API endpoints now support both AJAX calls and direct browser access:

- `GET /workspace/{workspace_id}/analytics/dashboard/?days=30`
- `GET /workspace/{workspace_id}/analytics/account/{account_id}/?days=30`
- `GET /workspace/{workspace_id}/analytics/post/{post_id}/`

## Usage

1. Navigate to any workspace
2. Click "Analytics" in the sidebar
3. View performance metrics across all connected social accounts
4. Use date range selector to analyze different time periods
5. Click "Refresh" to get latest data

## Data Collection

Analytics data is collected automatically via background tasks:
- **Hourly**: Recent posts (< 48 hours old)
- **Daily**: All posts (< 30 days old) + account metrics

Use `python manage.py collect_analytics --type full` to manually trigger collection.

## Future Enhancements

- Individual account analytics pages
- Detailed post performance charts
- Export functionality
- Custom date ranges
- Comparative analysis between platforms
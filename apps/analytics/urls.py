"""URL routing for analytics endpoints."""

from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("dashboard/", views.analytics_dashboard, name="dashboard"),
    path(
        "account/<uuid:account_id>/",
        views.account_analytics,
        name="account_detail",
    ),
    path(
        "post/<uuid:platform_post_id>/",
        views.post_metrics_detail,
        name="post_detail",
    ),
]

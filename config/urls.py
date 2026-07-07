from django.contrib import admin
from django.urls import path

from config.frontend_views import favicon, frontend_asset, frontend_index
from sessions.views import CreateSessionView


urlpatterns = [
    path("", frontend_index, name="frontend-index"),
    path("favicon.ico", favicon, name="frontend-favicon"),
    path("frontend/<path:path>", frontend_asset, name="frontend-asset"),
    path("admin/", admin.site.urls),
    path("api/sessions/", CreateSessionView.as_view(), name="session-create"),
]

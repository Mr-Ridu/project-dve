"""Root URL configuration.

Named URL patterns only; pages and apps include their own urls.py.
The core catch-all must stay last — it swallows any unmatched slug.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("tutorials/", include("tutorials.urls")),
    path("", include("core.urls")),
]

# Custom 404 (templates/404.html) — used whenever DEBUG is False.
handler404 = "core.views.page_not_found"
handler500 = "core.views.page_not_found"

# Development convenience only: runserver serves uploaded media.
# In production media must NOT be publicly mapped (see docs/PHASE1_INSPECTION_REPORT.md §9).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

"""Public page views.

Phase 2 provides a placeholder home page only. Phase 3 converts the real
Home / About / Products / Services / Contact templates into these views and
adds the legacy catch-all for the remaining mirrored pages.
"""
from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")

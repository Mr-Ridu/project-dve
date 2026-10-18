"""Tutorial URLs (Phase 5).

Namespace tutorials. /tutorials/ lists the published catalog; playback
authorization is POST-only and CSRF-protected.
"""
from django.urls import path

from . import views

app_name = "tutorials"

urlpatterns = [
    path("", views.tutorial_list, name="list"),
    path("<slug:slug>/", views.tutorial_detail, name="detail"),
    path("<slug:slug>/authorize/", views.playback_authorize, name="authorize"),
]

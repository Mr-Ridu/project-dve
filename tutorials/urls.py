"""Tutorial URLs (Phase 5, redemption added in Phase 6).

Namespace tutorials. /tutorials/ lists the published catalog; playback
authorize + redeem are POST-only and CSRF-protected.
"""
from django.urls import path

from . import views

app_name = "tutorials"

urlpatterns = [
    path("", views.tutorial_list, name="list"),
    # Literal routes BEFORE the slug pattern — /tutorials/redeem/ must not be
    # swallowed by /tutorials/<slug>/ (which 404s as an unknown tutorial slug).
    path("redeem/", views.playback_redeem, name="redeem"),
    path("<slug:slug>/", views.tutorial_detail, name="detail"),
    path("<slug:slug>/authorize/", views.playback_authorize, name="authorize"),
]

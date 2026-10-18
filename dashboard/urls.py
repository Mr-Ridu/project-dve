"""Staff dashboard URLs (Phase 7). All mutations are POST-only."""
from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/approve/<str:action>/", views.user_approval, name="user_approval"),
    path("users/<int:pk>/toggle-access-flag/", views.user_access_flag, name="user_access_flag"),
    path("users/<int:pk>/grant/<int:tutorial_pk>/", views.grant_access, name="grant"),
    path("users/<int:pk>/revoke/<int:tutorial_pk>/", views.revoke_access, name="revoke"),
    path("tutorials/", views.tutorial_list, name="tutorial_list"),
    path("tutorials/new/", views.tutorial_edit, name="tutorial_create"),
    path("tutorials/<int:pk>/edit/", views.tutorial_edit, name="tutorial_edit"),
    path("tutorials/<int:pk>/delete/", views.tutorial_delete, name="tutorial_delete"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
]

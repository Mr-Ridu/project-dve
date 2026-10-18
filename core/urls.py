from django.urls import path, re_path

from . import views

app_name = "core"

urlpatterns = [
    # Core pages (converted templates)
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("products/", views.products, name="products"),
    path("services/", views.services, name="services"),
    path("contact/", views.contact, name="contact"),
    # Original-URL aliases (old slugs keep working)
    path("product-information/", views.products, name="products-legacy"),
    path("service-support/", views.services, name="services-legacy"),
    path("contact-us/", views.contact, name="contact-legacy"),
    # Local stubs (real delivery/search configured in later phases)
    path("forms/placeholder/", views.form_placeholder, name="form-placeholder"),
    path("search/", views.search_stub, name="search"),
    # Sanitized legacy catch-all — must stay last
    re_path(r"^(?P<slug>[a-z0-9][a-z0-9-]{0,99})/$", views.legacy_page, name="legacy-page"),
]

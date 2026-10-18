from django.test import TestCase
from django.urls import reverse


class ScaffoldTests(TestCase):
    """Phase 2 smoke tests: the project serves pages and resolves URLs."""

    def test_home_renders(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)

    def test_admin_login_page_loads(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    def test_404_for_unknown_page(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)

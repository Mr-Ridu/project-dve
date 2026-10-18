from django.contrib.auth import get_user_model
from django.test import TestCase


class UserModelTests(TestCase):
    def test_auth_user_model_is_custom(self):
        self.assertEqual(get_user_model()._meta.label, "accounts.User")

    def test_new_user_defaults_to_pending(self):
        user = get_user_model().objects.create_user("alice", password="secret-123")
        self.assertEqual(user.approval_status, "pending")
        self.assertFalse(user.access_all_tutorials)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_approved())

    def test_approved_active_user_is_approved(self):
        user = get_user_model().objects.create_user("bob", password="secret-123")
        user.approval_status = "approved"
        user.save()
        self.assertTrue(user.is_approved())

    def test_rejected_user_is_not_approved(self):
        user = get_user_model().objects.create_user("carol", password="secret-123")
        user.approval_status = "rejected"
        user.save()
        self.assertFalse(user.is_approved())

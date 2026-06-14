from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .models import WaitListModel


class WaitlistViewsTests(TestCase):
	def setUp(self):
		self.client = APIClient()

	@patch("waitlist.views.send_waitlist_welcome_email")
	def test_join_waitlist_saves_email_and_triggers_welcome_email(self, mock_send_email):
		payload = {"email": "student@example.com"}

		response = self.client.post("/waitlist/", payload, format="json")

		self.assertEqual(response.status_code, 201)
		self.assertEqual(WaitListModel.objects.count(), 1)
		self.assertEqual(WaitListModel.objects.first().email, "student@example.com")
		mock_send_email.assert_called_once_with("student@example.com")

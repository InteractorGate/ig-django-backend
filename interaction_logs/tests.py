"""Tests for the interaction_logs app.

These logs live in Cosmos DB (via PyMongo), not the Django ORM. The Mongo
collection is replaced with an in-memory fake so the tests run offline with no
real database connection.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: d.get(key), reverse=direction == -1)
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeCollection:
    """Minimal in-memory stand-in for a PyMongo collection."""

    def __init__(self):
        self.docs = []
        self._next_id = 0

    def insert_one(self, document):
        self._next_id += 1
        stored = {**document, "_id": self._next_id}
        self.docs.append(stored)
        return type("Result", (), {"inserted_id": self._next_id})()

    def find(self, query):
        matched = [
            dict(d) for d in self.docs
            if all(d.get(k) == v for k, v in query.items())
        ]
        return _FakeCursor(matched)


class InteractionLogsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="eduardo", password="x")
        self.other = User.objects.create_user(username="otro", password="x")
        self.log_url = reverse("interaction_logs:log")

        # Patch the collection factory so every call returns our shared fake.
        self.collection = _FakeCollection()
        patcher = patch(
            "interaction_logs.views.interaction_logs_collection",
            return_value=self.collection,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _session_url(self, session_id):
        return reverse("interaction_logs:session-logs", args=[session_id])

    def test_write_log_requires_authentication(self):
        res = self.client.post(self.log_url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_write_log_persists_document(self):
        self.client.force_authenticate(self.user)
        payload = {
            "session_id": "sess-1",
            "event_type": "selection",
            "gaze_coordinates": {"x": 0.42, "y": 0.71},
            "selected_word": "agua",
        }
        res = self.client.post(self.log_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", res.data)
        self.assertEqual(res.data["user_id"], self.user.id)
        self.assertEqual(len(self.collection.docs), 1)
        self.assertEqual(self.collection.docs[0]["selected_word"], "agua")

    def test_write_log_rejects_invalid_event_type(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(
            self.log_url,
            {"session_id": "s", "event_type": "not_a_real_event"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(self.collection.docs), 0)

    def test_session_logs_returns_user_events(self):
        self.client.force_authenticate(self.user)
        for evt in ("session_start", "selection"):
            self.client.post(
                self.log_url,
                {"session_id": "sess-1", "event_type": evt},
                format="json",
            )
        res = self.client.get(self._session_url("sess-1"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["session_id"], "sess-1")
        self.assertEqual(res.data["count"], 2)
        self.assertEqual(len(res.data["logs"]), 2)

    def test_session_logs_are_isolated_per_user(self):
        # user writes an event to a session...
        self.client.force_authenticate(self.user)
        self.client.post(
            self.log_url,
            {"session_id": "shared", "event_type": "selection"},
            format="json",
        )
        # ...the other user must not see it.
        self.client.force_authenticate(self.other)
        res = self.client.get(self._session_url("shared"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 0)

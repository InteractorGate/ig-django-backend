"""Tests for the interaction_logs app.

These logs live in Cosmos DB (via PyMongo), not the Django ORM. The Mongo
collection is replaced with an in-memory fake so the tests run offline with no
real database connection.
"""
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4
from pymongo.errors import DuplicateKeyError

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import SimpleTestCase
from .summary import summarize_session

User = get_user_model()


class SummaryIntegrityTests(SimpleTestCase):
    def test_health_advertises_delivery_protocol(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["telemetry_schema"], 2)

    def _records(self, condition="with_prediction"):
        common = {"study":"E2", "trial_id":"t", "condition":condition,
                  "phrase_id":"A1", "target_phrase":"A", "practice":False,
                  "block":1,"order":1,"protocol_session":"s2", "bank_version":"pilot-v1",
                  "list":"A","participant_number":1}
        return [
            {"schema_version":2,"sequence":1,"event_type":"trial_start","data":common},
            {"schema_version":2,"sequence":2,"event_type":"selection",
             "data":{**common,"action":"letter","inserted_text":"A","removed_characters":0,"text_length":1}},
            {"schema_version":2,"sequence":3,"event_type":"trial_end",
             "data":{**common,"status":"completed","final_text":"A","duration_ms":5}},
        ]

    def test_missing_or_duplicated_sequence_is_not_approved(self):
        events=self._records()
        self.assertTrue(summarize_session(events)["consistent"])
        events[1]["sequence"]=4
        self.assertFalse(summarize_session(events)["consistent"])
        events[1]["sequence"]=1
        self.assertFalse(summarize_session(events)["consistent"])

    def test_open_trial_and_wrong_final_text_are_not_approved(self):
        events=self._records()
        self.assertFalse(summarize_session(events[:-1])["consistent"])
        events[-1]["data"]["final_text"]="B"
        self.assertFalse(summarize_session(events)["consistent"])

    def test_suggestion_without_matching_display_is_not_approved(self):
        events=self._records()
        events[1]["data"].update(action="suggestion",suggestion_rank=1,request_id="missing")
        self.assertFalse(summarize_session(events)["consistent"])

    def test_prediction_in_disabled_condition_is_not_approved(self):
        events=self._records("without_prediction")
        events[1]["data"]["action"]="requested"
        self.assertFalse(summarize_session(events)["consistent"])


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: d.get(key), reverse=direction == -1)
        return self

    def __iter__(self):
        return iter(self._docs)

    def limit(self, count):
        return _FakeCursor(self._docs[:count])


class _FakeCollection:
    """Minimal in-memory stand-in for a PyMongo collection."""

    def __init__(self):
        self.docs = []
        self._next_id = 0

    def insert_one(self, document):
        self._next_id += 1
        stored = {"_id": self._next_id, **document}
        if any(d["_id"] == stored["_id"] for d in self.docs):
            raise DuplicateKeyError("duplicate")
        self.docs.append(stored)
        return type("Result", (), {"inserted_id": stored["_id"]})()

    def find_one(self, query):
        return next(iter(self.find(query)), None)

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

    def test_write_log_stores_study_event_with_data(self):
        self.client.force_authenticate(self.user)
        payload = {
            "session_id": "sess-1",
            "event_type": "trial_start",
            "timestamp": "2026-10-08T15:00:00.123Z",
            "data": {"condition": "con_prediccion", "target": "quiero agua"},
        }
        res = self.client.post(self.log_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = self.collection.docs[0]
        self.assertEqual(doc["data"]["condition"], "con_prediccion")
        # The client clock is kept apart from the server's arrival time.
        self.assertEqual(
            doc["timestamp"],
            datetime(2026, 10, 8, 15, 0, 0, 123000, tzinfo=timezone.utc),
        )
        self.assertIn("received_at", doc)
        self.assertNotEqual(doc["received_at"], doc["timestamp"])

    def test_write_log_rejects_oversized_data(self):
        # A base64 camera frame must never make it into the logs.
        self.client.force_authenticate(self.user)
        res = self.client.post(
            self.log_url,
            {"session_id": "s", "event_type": "selection",
             "data": {"frame": "A" * 10_000}},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(self.collection.docs), 0)

    def _event(self, sequence=1, **overrides):
        return {"session_id": "study-session", "event_id": str(uuid4()), "participant_id":self.user.id,
                "sequence": sequence, "timestamp": "2026-11-03T10:00:00.123456Z",
                "event_type": "selection", **overrides}

    def test_retry_returns_original_event_without_new_document_or_receipt_time(self):
        self.client.force_authenticate(self.user)
        payload = self._event(data={"action": "letter", "inserted_text": "A"})
        first = self.client.post(self.log_url, payload, format="json")
        replay = self.client.post(self.log_url, payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.data["id"], replay.data["id"])
        self.assertEqual(first.data["received_at"], replay.data["received_at"])
        self.assertEqual(first.data["event_id"], payload["event_id"])
        self.assertEqual(first.data["schema_version"], 2)
        self.assertEqual(len(self.collection.docs), 1)

    def test_event_id_cannot_be_reused_with_different_payload(self):
        self.client.force_authenticate(self.user)
        payload = self._event(selected_word="A")
        self.client.post(self.log_url, payload, format="json")
        replay = self.client.post(self.log_url, {**payload, "selected_word": "B"}, format="json")
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(self.collection.docs[0]["selected_word"], "A")

    def test_event_keys_and_reads_remain_isolated_between_accounts(self):
        payload = self._event()
        self.client.force_authenticate(self.user)
        first = self.client.post(self.log_url, {**payload, "user_id": self.other.id}, format="json")
        self.assertEqual(first.data["user_id"], self.user.id)
        self.client.force_authenticate(self.other)
        second = self.client.post(self.log_url, {**payload,"participant_id":self.other.id}, format="json")
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.data["id"], second.data["id"])
        logs = self.client.get(self._session_url("study-session")).data["logs"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["user_id"], self.other.id)

    def test_v2_requires_sequence_clock_and_valid_id_and_rejects_images(self):
        self.client.force_authenticate(self.user)
        payload = self._event()
        for missing in ("participant_id", "sequence", "timestamp"):
            self.assertEqual(self.client.post(self.log_url,
                {k:v for k,v in payload.items() if k != missing}, format="json").status_code, 400)
        for data in ({"frame": "tiny-image"}, {"suggestions": [{"image": "x"}]}):
            self.assertEqual(self.client.post(self.log_url, self._event(data=data),
                format="json").status_code, 400)
        self.assertEqual(self.collection.docs, [])

    def test_wrong_token_account_cannot_persist_another_participants_event(self):
        payload=self._event()
        self.client.force_authenticate(self.other)
        response=self.client.post(self.log_url,payload,format="json")
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.collection.docs,[])

    def test_session_reconstructs_corrections_and_suggestion_after_entire_batch_replay(self):
        self.client.force_authenticate(self.user)
        common = {"study": "E2", "trial_id": str(uuid4()), "condition": "with_prediction",
                  "practice": False, "phrase_id": "A1", "target_phrase": "AGUA por favor",
                  "protocol_session": "s2", "block": 1, "order": 1,
                  "bank_version":"pilot-v1","list":"A","participant_number":1}
        steps = [
            ("trial_start", {}),
            ("selection", {"action": "letter", "inserted_text": "A", "removed_characters": 0, "text_length": 1}),
            ("selection", {"action": "space", "inserted_text": " ", "removed_characters": 0, "text_length": 2}),
            ("delete", {"action": "backspace", "inserted_text": "", "removed_characters": 1, "text_length": 1}),
            ("clear", {"action": "clear", "inserted_text": "", "removed_characters": 1, "text_length": 0}),
            ("selection", {"action": "word", "inserted_text": "AGUA", "removed_characters": 0, "text_length": 4}),
            ("settings", {"action": "board_mode", "board_mode": "words"}),
            ("suggestions", {"action": "requested", "request_id": "request1"}),
            ("suggestions", {"action": "shown", "request_id": "request1", "suggestions": ["por favor"], "latency_ms": 101}),
            ("selection", {"action": "suggestion", "request_id": "request1", "suggestion_rank": 1, "inserted_text": " por favor", "removed_characters": 0, "text_length": 14}),
            ("trial_end", {"status": "completed", "final_text": "AGUA por favor", "duration_ms": 5000}),
        ]
        payloads = [self._event(i+1, event_type=kind, data={**common, **data})
                    for i,(kind,data) in enumerate(steps)]
        for payload in payloads:
            self.assertEqual(self.client.post(self.log_url, payload, format="json").status_code, 201)
        for payload in payloads:
            self.assertEqual(self.client.post(self.log_url, payload, format="json").status_code, 200)
        report = self.client.get(self._session_url("study-session")).data
        self.assertEqual(report["count"], len(steps))
        summary = report["summary"]
        self.assertTrue(summary["consistent"])
        self.assertEqual(summary["trials"][0]["reconstructed_text"], "AGUA por favor")
        self.assertEqual(summary["trials"][0]["actions"]["backspace"], 1)
        self.assertEqual(summary["trials"][0]["suggestion_latencies_ms"], [101])

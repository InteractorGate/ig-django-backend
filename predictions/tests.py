"""Tests for the predictions app: the prediction pipeline (real RNN + CNN) and history."""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PredictionRequest

User = get_user_model()


class PredictionEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="eduardo", password="x")
        self.url = reverse("predictions:predict")
        self.client.force_authenticate(self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        res = self.client.post(self.url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_text_prediction_routes_to_real_rnn(self):
        res = self.client.post(
            self.url,
            {
                "input_type": "text",
                "raw_input": {"context": "me duele"},
                "session_id": "sess-1",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        result = res.data["result"]
        self.assertEqual(result["model_used"], "RNN")
        # Real model output: non-empty text and a valid probability.
        self.assertTrue(result["output_text"])
        self.assertGreaterEqual(result["confidence_score"], 0.0)
        self.assertLessEqual(result["confidence_score"], 1.0)
        self.assertGreaterEqual(result["response_time_ms"], 0)
        # The request was persisted and linked to the user.
        self.assertTrue(
            PredictionRequest.objects.filter(user=self.user, session_id="sess-1").exists()
        )

    def test_gaze_prediction_routes_to_cnn(self):
        res = self.client.post(
            self.url,
            {
                "input_type": "gaze",
                "raw_input": {"frame": "<b64>"},
                "session_id": "sess-2",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        result = res.data["result"]
        self.assertEqual(result["model_used"], "CNN")
        # Real model output: a selected board cell and a valid probability.
        # (An unparseable frame degrades to a neutral patch but still runs the
        # real CNN, so we always get a cell + confidence back.)
        self.assertTrue(result["output_text"])
        self.assertGreaterEqual(result["confidence_score"], 0.0)
        self.assertLessEqual(result["confidence_score"], 1.0)
        self.assertGreaterEqual(result["response_time_ms"], 0)

    def test_invalid_input_type_is_rejected(self):
        res = self.client.post(
            self.url,
            {"input_type": "audio", "raw_input": {}, "session_id": "s"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class PredictionHistoryTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="eduardo", password="x")
        self.other = User.objects.create_user(username="otro", password="x")
        self.predict_url = reverse("predictions:predict")
        self.history_url = reverse("predictions:history")

    def _make_prediction(self, user, session_id):
        self.client.force_authenticate(user)
        return self.client.post(
            self.predict_url,
            {
                "input_type": "text",
                "raw_input": {"context": "hola"},
                "session_id": session_id,
            },
            format="json",
        )

    def test_history_is_scoped_to_the_requesting_user(self):
        self._make_prediction(self.user, "mine")
        self._make_prediction(self.other, "theirs")

        self.client.force_authenticate(self.user)
        res = self.client.get(self.history_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        sessions = [item["session_id"] for item in res.data]
        self.assertIn("mine", sessions)
        self.assertNotIn("theirs", sessions)

    def test_history_requires_authentication(self):
        res = self.client.get(self.history_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

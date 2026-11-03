"""Exercise real HTTP + Mongo on loopback, including concurrent ACK retries."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

BASE = "http://127.0.0.1:8000"


def request(path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(BASE + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urlopen(req, timeout=45) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def login(code):
    status, body = request("/api/users/login/", {"username": code, "password": "Local-B3-only-2026!"})
    assert status == 200, status
    return body["access"]


def main():
    token = login("LOCAL_B3")
    other = login("LOCAL_B3_2")
    participant = request("/api/users/me/", token=token)[1]["id"]
    session_id, trial_id = str(uuid4()), str(uuid4())
    sequence = 0

    def event(kind, data=None):
        nonlocal sequence
        sequence += 1
        return {"event_id": str(uuid4()), "participant_id": participant, "sequence": sequence, "session_id": session_id,
                "event_type": kind, "timestamp": datetime.now(timezone.utc).isoformat(),
                **({"data": data} if data is not None else {})}

    first = event("session_start")
    with ThreadPoolExecutor(max_workers=6) as workers:
        replies = list(workers.map(lambda _: request("/api/logs/", first, token), range(6)))
    assert sorted(code for code, _ in replies) == [200] * 5 + [201], [code for code, _ in replies]
    common = {"study": "E2", "trial_id": trial_id, "condition": "with_prediction",
              "practice": True, "phrase_id": "P6", "target_phrase": "AGUA por favor",
              "protocol_session": "practice", "block": 2, "order": 6,
              "bank_version":"pilot-v1","list":"practice","participant_number":1}
    steps = [
        ("trial_start", {}),
        ("selection", {"action": "letter", "inserted_text": "A", "removed_characters": 0, "text_length": 1}),
        ("selection", {"action": "space", "inserted_text": " ", "removed_characters": 0, "text_length": 2}),
        ("delete", {"action": "backspace", "inserted_text": "", "removed_characters": 1, "text_length": 1}),
        ("clear", {"action": "clear", "inserted_text": "", "removed_characters": 1, "text_length": 0}),
        ("selection", {"action": "word", "inserted_text": "AGUA", "removed_characters": 0, "text_length": 4}),
        ("suggestions", {"action": "requested", "request_id": "r1"}),
        ("suggestions", {"action": "shown", "request_id": "r1", "suggestions": ["por favor"], "latency_ms": 121}),
        ("selection", {"action": "suggestion", "request_id": "r1", "suggestion_rank": 1, "inserted_text": " por favor", "removed_characters": 0, "text_length": 14}),
        ("trial_end", {"status": "completed", "final_text": "AGUA por favor", "duration_ms": 5100}),
    ]
    batch = [event(kind, {**common, **data}) for kind, data in steps]
    for payload in batch:
        assert request("/api/logs/", payload, token)[0] == 201
    for payload in [first, *batch]:
        assert request("/api/logs/", payload, token)[0] == 200
    status, report = request(f"/api/logs/session/{session_id}/", token=token)
    assert status == 200 and report["count"] == len(batch) + 1
    assert report["summary"]["consistent"], report["summary"]
    assert report["summary"]["trials"][0]["reconstructed_text"] == "AGUA por favor"
    assert request(f"/api/logs/session/{session_id}/", token=other)[1]["count"] == 0
    assert request("/api/logs/", first, other)[0] == 403
    assert request("/api/logs/", {**first, "event_type": "session_end"}, token)[0] == 409
    print(json.dumps({"http_mongo": "pass", "concurrent_retries": 6,
                      "persisted_events": report["count"], "reconstructed_trial": True,
                      "cross_account_read": "blocked", "duplicate_payload_conflict": 409}))


if __name__ == "__main__":
    main()

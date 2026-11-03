"""Reconstruct E2 trials from persisted edits; no inference of missing actions."""
from collections import Counter, defaultdict


def summarize_session(logs):
    events = sorted((e for e in logs if e.get("schema_version") == 2),
                    key=lambda e: e["sequence"])
    counts = Counter(e["sequence"] for e in events)
    gaps = []
    previous = 0
    for number in sorted(counts):
        if number > previous + 1:
            gaps.append([previous + 1, number - 1])
        previous = number
    groups = defaultdict(list)
    for event in events:
        data = event.get("data") or {}
        if data.get("study") == "E2" and data.get("trial_id"):
            groups[data["trial_id"]].append(event)
    trials = []
    for trial_id, records in groups.items():
        starts = [e for e in records if e["event_type"] == "trial_start"]
        ends = [e for e in records if e["event_type"] == "trial_end"]
        actions = Counter()
        text = ""
        valid_edits = True
        latencies = []
        shown = {}
        valid_suggestions = True
        for event in records:
            data = event.get("data") or {}
            action = data.get("action")
            if action:
                actions[action] += 1
            if event["event_type"] in {"selection", "delete", "clear"}:
                removed = data.get("removed_characters")
                inserted = data.get("inserted_text")
                if (type(removed) is not int or not 0 <= removed <= len(text)
                        or not isinstance(inserted, str)):
                    valid_edits = False
                    continue
                text = text[:len(text) - removed] + inserted
                if data.get("text_length") != len(text):
                    valid_edits = False
            if action == "shown" and isinstance(data.get("latency_ms"), (float, int)):
                latencies.append(data["latency_ms"])
                shown[data.get("request_id")] = data.get("suggestions", [])
            if action == "suggestion":
                choices = shown.get(data.get("request_id"), [])
                rank = data.get("suggestion_rank")
                if (type(rank) is not int or not 1 <= rank <= len(choices)
                        or not isinstance(data.get("inserted_text"), str)
                        or data.get("inserted_text", "").strip() != choices[rank-1]):
                    valid_suggestions = False
        final = (ends[-1].get("data") or {}) if ends else {}
        first = (starts[0].get("data") or {}) if starts else {}
        required = ("phrase_id", "target_phrase", "condition", "practice", "block",
                    "order", "protocol_session", "bank_version", "list", "participant_number")
        valid_metadata = (
            all(first.get(k) is not None for k in required)
            and first.get("condition") in {"with_prediction", "without_prediction"}
            and first.get("protocol_session") in {"practice", "s2", "s3"}
            and type(first.get("practice")) is bool
            and first["practice"] == (first["protocol_session"] == "practice")
            and all(all((e.get("data") or {}).get(k) == first.get(k) for k in required)
                    for e in records)
            and final.get("status") in {"completed", "interrupted"}
            and type(final.get("duration_ms")) is int and final["duration_ms"] >= 0
            and (final.get("status") != "completed" or (
                isinstance(final.get("final_text"), str) and bool(final["final_text"].strip())))
        )
        matches = valid_edits and bool(ends) and text == final.get("final_text")
        forbidden_prediction = first.get("condition") == "without_prediction" and (
            actions["requested"] or actions["shown"] or actions["suggestion"]
        )
        trials.append({
            "trial_id": trial_id,
            **{k: first.get(k) for k in ("phrase_id", "target_phrase", "condition",
                                       "practice", "block", "order", "protocol_session")},
            "status": final.get("status", "open"),
            "duration_ms": final.get("duration_ms"),
            "actions": dict(actions),
            "reconstructed_text": text,
            "final_text_matches": matches,
            "suggestion_latencies_ms": latencies,
            "consistent": bool(len(starts) == 1 and len(ends) == 1 and matches and valid_suggestions and valid_metadata
                               and not forbidden_prediction),
        })
    legacy = len(logs) - len(events)
    return {
        "schema_version": 2,
        "event_count": len(logs),
        "legacy_events": legacy,
        "duplicate_sequences": [n for n, count in counts.items() if count > 1],
        "sequence_gaps": gaps,
        "trials": trials,
        "consistent": bool(trials and not legacy and not gaps
                           and all(count == 1 for count in counts.values())
                           and all(t["consistent"] for t in trials)),
    }

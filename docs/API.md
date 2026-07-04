# InteractorGate — Backend API Contract

Reference for the Flutter desktop client. Every request/response shape below
matches the current backend code.

- **Prod base URL:** `https://ig-backend-tesis.azurewebsites.net`
- **Dev base URL:** `http://localhost:8000`
- **Content type:** `application/json` for all request bodies.
- **Language:** validation/error messages are returned in Spanish.

## Authentication

JWT (Bearer). Obtain a token pair from `login`, then send it on every
protected request:

```
Authorization: Bearer <access_token>
```

- **Access token lifetime:** 60 min · **Refresh token lifetime:** 7 days.
- **Rotation + blacklist are ON:** each call to `token/refresh/` returns a *new*
  refresh token and invalidates the old one. Always store the latest refresh
  token returned.
- **Public endpoints (no token):** `GET /`, `GET /healthz/`,
  `POST /api/users/register/`, `POST /api/users/login/`,
  `POST /api/token/refresh/`. Everything else requires a valid Bearer token.

### Rate limits (HTTP 429 when exceeded)

| Scope | Limit |
|---|---|
| Anonymous (per IP) | 60 / min |
| Authenticated (per user) | 240 / min |
| `login` | 10 / min |
| `register` | 20 / hour |

A throttled response is `429 Too Many Requests` with a `Retry-After` header.

## Common error shapes

| Status | When | Body |
|---|---|---|
| 400 | Validation failed | `{ "<field>": ["message", ...] }` |
| 401 | Missing/invalid/expired token | `{ "detail": "..." }` |
| 403 | Authenticated but not allowed | `{ "detail": "..." }` |
| 404 | Not found | `{ "detail": "No encontrado." }` |
| 429 | Rate limited | `{ "detail": "Request was throttled. Expected available in N seconds." }` |

---

## Service

### `GET /` — API index (public)
`200` →
```json
{ "service": "InteractorGate API", "status": "ok", "endpoints": { "...": "..." } }
```

### `GET /healthz/` — liveness probe (public)
`200` → `{ "status": "ok" }`

---

## Users & Auth

### `POST /api/users/register/` — register (public)
Request:
```json
{
  "username": "eduardo",
  "email": "eduardo@example.com",
  "password": "SecurePass123",
  "password2": "SecurePass123",
  "first_name": "Eduardo",
  "last_name": "Chero"
}
```
- `first_name` / `last_name` are optional. `password` is validated (min length,
  not all-numeric, not too common). `password` and `password2` must match.

`201` →
```json
{ "id": 1, "username": "eduardo", "email": "eduardo@example.com",
  "first_name": "Eduardo", "last_name": "Chero" }
```
`400` example → `{ "password": ["Las contraseñas no coinciden."] }`

### `POST /api/users/login/` — obtain token pair (public, 10/min)
Request → `{ "username": "eduardo", "password": "SecurePass123" }`

`200` →
```json
{ "refresh": "<refresh_jwt>", "access": "<access_jwt>" }
```
`401` → `{ "detail": "No active account found with the given credentials" }`

### `POST /api/token/refresh/` — refresh access token (public)
Request → `{ "refresh": "<refresh_jwt>" }`

`200` → `{ "access": "<new_access_jwt>", "refresh": "<new_refresh_jwt>" }`
> Rotation is on: **replace your stored refresh token** with the one returned.

### `POST /api/users/logout/` — blacklist a refresh token (Bearer)
Request → `{ "refresh": "<refresh_jwt>" }`

`205 Reset Content` (no body) on success.
`400` → `{ "detail": "El token 'refresh' es obligatorio." }` or
`{ "detail": "Token inválido o expirado." }`

### `GET /api/users/me/` — current profile (Bearer)
`200` →
```json
{ "id": 1, "username": "eduardo", "email": "eduardo@example.com",
  "first_name": "Eduardo", "last_name": "Chero",
  "date_joined": "2026-07-04T12:00:00Z" }
```

### `PUT` / `PATCH /api/users/me/` — update own profile (Bearer)
Editable: `email`, `first_name`, `last_name`.
Read-only (ignored if sent): `id`, `username`, `date_joined`.
Request (PATCH) → `{ "first_name": "Ed" }` → `200` with the full profile.

---

## Predictions

### `POST /api/predictions/` — run a prediction (Bearer)
Routes to the RNN (text) or CNN (gaze) via the orchestrator, stores the
request + result, and returns them nested.

**Text prediction (real RNN — PyTorch LSTM):**
```json
{
  "input_type": "text",
  "raw_input": { "context": "me duele" },
  "session_id": "b3f1c2a4-...."
}
```
`201` →
```json
{
  "id": 12,
  "input_type": "text",
  "raw_input": { "context": "me duele" },
  "session_id": "b3f1c2a4-....",
  "created_at": "2026-07-04T12:34:56Z",
  "result": {
    "id": 12,
    "model_used": "RNN",
    "output_text": "la cabeza | el estómago | mucho aquí",
    "confidence_score": 0.4756,
    "response_time_ms": 18,
    "created_at": "2026-07-04T12:34:56Z"
  }
}
```
> `output_text` for text predictions is the ranked suggestions joined by
> `" | "`. Split on `" | "` to get the individual phrases for the UI.
> `confidence_score` is the model's real softmax probability (0–1).

**Gaze prediction (CNN — currently a stub, shape is stable):**
```json
{
  "input_type": "gaze",
  "raw_input": { "frame": "<base64-jpeg-or-coords>" },
  "session_id": "b3f1c2a4-...."
}
```
`201` → same envelope with `"model_used": "CNN"`, `output_text` = the selected
board cell (e.g. `"agua"`). **Note:** the CNN returns random data for now, and
real-time gaze is expected to run *on the client*, not here — treat this
endpoint as batch/verification, not the live gaze loop.

- `input_type` must be `"gaze"` or `"text"`. Any other value → `400`.
- `raw_input` is free-form JSON; `session_id` is a string (send a UUID).

### `GET /api/predictions/history/` — the caller's past predictions (Bearer)
`200` → array of the same objects as above (newest first), each with its
nested `result`.

---

## Interaction Logs (telemetry → Cosmos DB)

Fire-and-store events for analysis and future model retraining. Stored in
Cosmos DB (no SQL). `user_id` and a fallback `timestamp` are added server-side.

### `POST /api/logs/` — write one event (Bearer)
```json
{
  "session_id": "b3f1c2a4-....",
  "event_type": "selection",
  "gaze_coordinates": { "x": 0.42, "y": 0.71 },
  "selected_word": "agua",
  "timestamp": "2026-07-04T12:34:56Z"
}
```
- `event_type` ∈ `gaze` · `selection` · `dwell` · `calibration` ·
  `session_start` · `session_end`.
- `gaze_coordinates`, `selected_word`, `timestamp` are all optional
  (`timestamp` defaults to server UTC now).

`201` → the stored document, including a generated `id` and `user_id`:
```json
{
  "id": "665f...",
  "user_id": 1,
  "session_id": "b3f1c2a4-....",
  "event_type": "selection",
  "gaze_coordinates": { "x": 0.42, "y": 0.71 },
  "selected_word": "agua",
  "timestamp": "2026-07-04T12:34:56Z"
}
```

### `GET /api/logs/session/<session_id>/` — read a session's events (Bearer)
Returns only the **calling user's** events for that session, sorted by time.
`200` →
```json
{ "session_id": "b3f1c2a4-....", "count": 2, "logs": [ { "...": "..." } ] }
```

---

## Suggested client integration flow

1. `register` (once) → `login` → store `access` + `refresh`.
2. Attach `Authorization: Bearer <access>` to every protected call.
3. On `401`, call `token/refresh/`, store the **new** refresh token, retry once.
4. `session_start`: generate a `session_id` (UUID); send a `session_start` log.
5. During use: send `text` predictions for phrase autocomplete; POST gaze/
   selection events to `/api/logs/`.
6. `session_end`: send a `session_end` log; on sign-out call `logout`.

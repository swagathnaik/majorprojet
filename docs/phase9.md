# Phase 9 – Safety verification

## Flow

```
Anomaly detected
  → pending safety_check
  → Modal: "Are you safe?"
      ├─ YES, I'M SAFE → clear anomaly, continue
      ├─ I NEED HELP → SOS (manual reason path)
      └─ No response
            → Countdown
                 ├─ Cancel → safe
                 └─ 0 → Automatic SOS
```

## API

| Method | Endpoint |
|--------|----------|
| POST | `/api/safety-checks/:id/respond` `{ response: "safe"\|"need_help" }` |
| POST | `/api/safety-checks/:id/cancel-countdown` |
| POST | `/api/safety-checks/:id/timeout` |

## Config

- `SAFETY_RESPONSE_SEC` – time to answer before countdown (default 40)
- `SOS_COUNTDOWN_SEC` – countdown length (default 20)

## Demo

1. Start journey
2. Click **Simulate stop**
3. Answer the modal (or wait for countdown)

## Tests

```bash
cd backend
python -m tests.test_safety
```

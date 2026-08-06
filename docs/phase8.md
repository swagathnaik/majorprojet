# Phase 8 – Rule-based anomaly detection

## Rules

| Type | Trigger |
|------|---------|
| `prolonged_stop` | Was moving, then stopped ≥ `STOP_THRESHOLD_SEC` |
| `route_deviation` | Distance from start→dest line ≥ `DEVIATION_THRESHOLD_M` |
| `lost_signal` | No GPS update ≥ `LOST_SIGNAL_SEC` while active |
| `speed_spike` | Sudden speed jump vs recent average |

## Behaviour

- Creates an **open** `anomalies` row
- Creates a **pending** `safety_checks` row (Phase 9 will ask “Are you safe?”)
- **Does not** trigger SOS
- Cooldown + no stacking while a safety check is pending

## Demo

`POST /api/journeys/:id/demo/simulate-anomaly`  
Body: `{ "type": "prolonged_stop" }`  
Requires `DEMO_MODE=true`

UI: Journey page → Demo buttons (Simulate stop / deviation / signal loss)

## Tests

```bash
cd backend
python -m tests.test_anomalies
```

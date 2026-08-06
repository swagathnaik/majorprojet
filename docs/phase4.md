# Phase 4 – GPS location tracking

## Flow

```
Browser Geolocation API
  → useGeolocation hook
  → Start minimal journey (POST /api/journeys)
  → Every ~5s POST /api/journeys/:id/locations
  → SQLite location_logs
```

## Limitations (important for viva)

- Needs **localhost** or **HTTPS**
- Keep the **tab open**; browser background GPS is unreliable
- Future: Flutter/native app for true background tracking

## UI

- `/track` – Start / Stop GPS tracking
- Shows live lat/lng/accuracy/speed/heading
- Lists recent uploaded points

## Tests

```bash
cd backend
python -m tests.test_locations
```

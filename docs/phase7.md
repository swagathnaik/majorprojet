# Phase 7 – Journey monitoring

## Endpoint

`GET /api/journeys/:id/monitoring`

Also returned on each `POST .../locations` as `monitoring`.

## Metrics

| Field | Meaning |
|-------|---------|
| movement_status | moving / stopped / paused / signal_lost / … |
| speed_mps / speed_kmh | Device speed or derived from points |
| heading_deg / heading_label | Direction of travel |
| stop_duration_sec | Current stationary streak |
| distance_traveled_m | Path length so far |
| distance_to_dest_m | Straight-line to destination (if coords set) |
| deviation_m | Distance off start→dest line |
| journey_duration_sec | Time since start |
| eta_sec | Rough walk ETA (~5 km/h) |
| flags | Soft “watch” hints (no SOS yet) |

## Important

Monitoring **does not** trigger SOS. Phase 8 uses these metrics for anomaly rules + “Are you safe?”.

## Tests

```bash
cd backend
python -m tests.test_monitoring
```

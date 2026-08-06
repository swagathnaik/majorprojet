# Phase 5 – Safe Journey Mode

## User flow

1. Add emergency contact (Phase 3)
2. Open **/journey**
3. Enter destination + select trusted contact
4. **START SAFE JOURNEY** → GPS permission → tracking begins
5. Pause / Resume / End / Cancel
6. **SOS** button stores a manual SOS alert (notification dashboard later)

## Rules

- Destination label is required
- At least one emergency contact is required
- Only one in-progress journey (`active` | `paused` | `sos`) at a time
- GPS uploads only while `active`
- Manual SOS sets journey status to `sos` and creates `sos_alerts` row

## Tests

```bash
cd backend
python -m tests.test_journey_mode
```

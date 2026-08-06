# Phase 3 – Emergency contacts

## Backend

- `GET/POST /api/contacts`
- `GET/PUT/DELETE /api/contacts/:id`
- `PATCH /api/contacts/:id/primary`

Rules:
- First contact is auto-primary
- Only one primary per user
- Deleting primary promotes the oldest remaining contact
- Ownership enforced via JWT user id

## Frontend

- Protected page `/contacts`
- Add / edit / delete / set primary
- Nav link: **Contacts**

## Tests

```bash
cd backend
.\.venv\Scripts\Activate.ps1
python -m tests.test_contacts
```

# Phase 1–2 notes

## What was built

- Flask app factory, config from `.env`, CORS, JWT, SQLAlchemy
- Full DB schema (all MVP tables) so later phases do not reshape early
- Auth: register, login, me, update profile
- React + Vite UI: landing, register, login, protected home

## Test checklist

1. `GET /api/health` → `{ "status": "ok" }`
2. Register a user → 201 + token
3. Login → 200 + token
4. `GET /api/auth/me` with Bearer token → user profile
5. Frontend: register → redirected to `/home` with profile visible
6. Logout → login again with same credentials

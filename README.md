# SafeRoute

AI-assisted **proactive personal journey safety** system.

SafeRoute monitors a journey for potentially unusual patterns, asks **"Are you safe?"** before escalating, and alerts trusted contacts only when needed.

It is **not** a replacement for Google Maps, ride-hailing apps, or **112 India**, and it does **not** claim to detect crimes or assaults.

---

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + Vite |
| Backend | Python Flask REST API |
| Database | SQLite (dev) |
| Auth | JWT + hashed passwords |
| Maps (later) | Leaflet + OpenStreetMap |

---

## Current progress

- [x] **Phase 1** – Project setup
- [x] **Phase 2** – Database schema + authentication
- [x] **Phase 3** – Emergency contact management
- [x] **Phase 4** – GPS location tracking
- [x] **Phase 5** – Safe Journey Mode
- [x] **Phase 6** – Live map (Leaflet)
- [x] **Phase 7** – Journey monitoring
- [x] **Phase 8** – Rule-based anomaly detection
- [x] **Phase 9** – Safety verification (“Are you safe?”)
- [ ] Phase 10+ – SOS polish, trusted contact dashboard

---

## Folder structure

```
saferoute/
├── backend/          # Flask API
├── frontend/         # React + Vite
├── docs/             # Architecture notes (growing)
├── .gitignore
└── README.md
```

---

## Prerequisites

- Python 3.11+ (tested with 3.13)
- Node.js 18+ and npm
- Git

---

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env
python run.py
```

API runs at: `http://localhost:5000`  
Health check: `http://localhost:5000/api/health`

### 2. Frontend

```bash
cd frontend
copy .env.example .env   # or: cp .env.example .env
npm install
npm run dev
```

App runs at: `http://localhost:5173`

---

## Environment variables

### `backend/.env`

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask secret |
| `JWT_SECRET_KEY` | JWT signing key |
| `DATABASE_URL` | Default `sqlite:///saferoute.db` |
| `CORS_ORIGINS` | Frontend origin(s), e.g. `http://localhost:5173` |

### `frontend/.env`

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE_URL` | Flask API base, e.g. `http://localhost:5000/api` |

**Never commit real secrets.** Use `.env.example` as a template.

---

## Auth API (Phase 2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login → JWT |
| GET | `/api/auth/me` | Current user (Bearer token) |
| PUT | `/api/auth/me` | Update name / phone |

Passwords are hashed with Werkzeug. JWT identity is the user id.

### Contacts API (Phase 3)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/contacts` | List contacts |
| POST | `/api/contacts` | Add contact |
| GET | `/api/contacts/:id` | Get one contact |
| PUT | `/api/contacts/:id` | Edit contact |
| PATCH | `/api/contacts/:id/primary` | Set primary |
| DELETE | `/api/contacts/:id` | Delete contact |

### Journeys / GPS API (Phase 4–5)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/journeys/active` | Current journey |
| POST | `/api/journeys` | Start Safe Journey |
| POST | `/api/journeys/:id/pause` | Pause GPS uploads |
| POST | `/api/journeys/:id/resume` | Resume journey |
| POST | `/api/journeys/:id/end` | End journey |
| POST | `/api/journeys/:id/cancel` | Cancel journey |
| POST | `/api/journeys/:id/sos` | Manual SOS shell |
| POST | `/api/journeys/:id/locations` | Upload GPS point |
| GET | `/api/journeys/:id/locations` | List GPS points |
| GET | `/api/journeys/:id/monitoring` | Live monitoring snapshot |
| GET | `/api/journeys/:id/anomalies` | List anomalies |
| POST | `/api/journeys/:id/demo/simulate-anomaly` | Demo anomaly |
| POST | `/api/safety-checks/:id/respond` | safe / need_help |
| POST | `/api/safety-checks/:id/cancel-countdown` | Cancel auto-SOS |
| POST | `/api/safety-checks/:id/timeout` | Automatic SOS |

Frontend: `/journey` (nav: **Journey**)

### Example – register

```bash
curl -X POST http://localhost:5000/api/auth/register ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Test User\",\"email\":\"test@example.com\",\"phone\":\"9999999999\",\"password\":\"secret1\"}"
```

### Example – login

```bash
curl -X POST http://localhost:5000/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"test@example.com\",\"password\":\"secret1\"}"
```

---

## How frontend talks to Flask

1. Vite app calls `VITE_API_BASE_URL` via `src/api/client.js`.
2. On register/login, Flask returns `access_token` + `user`.
3. Token is stored in `localStorage` and sent as `Authorization: Bearer <token>`.
4. Protected pages use `ProtectedRoute` + `AuthContext`.

---

## Database (created on first run)

Tables: `users`, `emergency_contacts`, `journeys`, `location_logs`, `anomalies`, `safety_checks`, `sos_alerts`.

SQLite file is created under `backend/instance/saferoute.db` (Flask default for relative `sqlite:///` URIs).

---

## Positioning

> SafeRoute is an AI-assisted proactive personal journey safety system that monitors a user's journey for potentially unusual patterns, verifies the user's safety before escalating an alert, and provides emergency assistance through trusted contacts and optional emergency-service integration.

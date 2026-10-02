# SafeRoute — Complete Project & Operational Documentation

AI-Assisted Proactive Personal Journey Safety & Navigation System.

---

## 1. Executive Summary & Purpose

**SafeRoute** is an AI-assisted proactive personal journey safety platform designed to protect travelers by continuously evaluating route safety, tracking real-time movement telemetry, identifying behavioral anomalies, and initiating timely verification and emergency alerts.

### Core Philosophy
Traditional safety applications are **reactive**: they require a user in distress to physically unlock their phone, open an app, and trigger an SOS button. In high-stress or incapacitating situations, this is often impossible. Conversely, fully automated panic systems often suffer from high false-alarm rates.

**SafeRoute addresses this with a four-pillar approach:**
1. **Crime-Aware Safe Route Planning**: Evaluates road routes using historical crime hotspot density and dynamic community safety feedback.
2. **Real-time Telemetry & Anomaly Detection**: Monitors trip movement (stop duration streaks, path deviations, speed spikes, signal losses).
3. **The "Are You Safe?" Verification Gate**: Employs an interactive verification protocol with audio-visual cues and a countdown timer to prevent false alarms before escalating.
4. **Multi-Channel Emergency Escalation**: Dispatches SMS alerts with exact coordinates, 1-click WhatsApp/SMS failover links, and a zero-login live tracking dashboard for emergency contacts, along with instant access to dial **112 India**.

> **Academic Disclaimer**: SafeRoute is an academic prototype for proactive personal safety. It does not claim to detect active assaults or replace police or emergency medical services (112 India), nor is it a commercial navigation replacement for Google Maps.

---

## 2. Technology Stack

| Layer | Technology | Key Libraries / Modules | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend** | React 19 + Vite | React Router v7, React Context, Lucide Icons | Client user interface, authentication state, responsive bottom sheet |
| **Mapping** | Leaflet + React-Leaflet | `leaflet.heat`, CARTO Voyager / OSM Tiles | Full-bleed street map, live user pin, path polyline, crime heatmap overlay |
| **Backend** | Python 3.11+ / Flask | Flask-SQLAlchemy, Flask-JWT-Extended, Flask-CORS | REST API, state machine, auth tokens, database ORM |
| **Database** | SQLite (Dev) / PostgreSQL (Prod) | SQLAlchemy Models, `psycopg2-binary` | Persistent storage for users, journeys, logs, anomalies, contacts |
| **Routing & Geo** | OSRM + Nominatim + Mapbox | `urllib`, Haversine formulas, GeoJSON | Geocoding, road-following street routing, lateral distance calculation |
| **Crime Analytics** | Kaggle Datasets + In-Memory Grid | `pandas`, `kagglehub` | Crime hotspot ingestion (`sudhanvahg/indian-crimes-dataset`), spatial scoring |
| **Notifications** | Infobip & Vonage SMS APIs | Custom HTTP client, `wa.me` deep links | Automated emergency SMS dispatch, 1-click WhatsApp fallback links |
| **Resilience** | Offline Store-and-Forward | Web `localStorage` queue | Buffers GPS telemetry during subway / network dead zones |

---

## 3. System Architecture & Component Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                           FRONTEND (React 19 + Leaflet)                             |
|  +--------------------+  +--------------------+  +----------------------+  +---------------------+  |
|  | SafeRoutePlanner   |  | JourneyMap         |  | MonitoringPanel      |  | SafetyModal         |  |
|  | (Route Search & UI)|  | (Leaflet Live Map) |  | (Speed, Status, ETA) |  | ("Are You Safe?")   |  |
|  +--------------------+  +--------------------+  +----------------------+  +---------------------+  |
|           │                         │                        │                         │            |
|           ▼                         ▼                        ▼                         ▼            |
|  +-----------------------------------------------------------------------------------------------+  |
|  |                     API Client (JWT Bearer Auth) & useGeolocation Hook                        |  |
|  |                     Offline Buffer (offlineQueue.js store-and-forward)                        |  |
|  +-----------------------------------------------------------------------------------------------+  |
+-------------------------------------------------┬────────────────────────────────------------------+
                                                  │ HTTP / JSON (REST)
+-------------------------------------------------▼--------------------------------------------------+
|                                           BACKEND (Python Flask API)                               |
|  +--------------------+  +--------------------+  +----------------------+  +---------------------+  |
|  | /api/auth          |  | /api/contacts      |  | /api/journeys        |  | /api/share/:token   |  |
|  | (Auth & Profile)   |  | (Emergency List)   |  | (Lifecycle & GPS)   |  | (Public Live Track) |  |
|  +--------------------+  +--------------------+  +----------------------+  +---------------------+  |
|           │                         │                        │                         │            |
|  +--------------------+  +--------------------+  +----------------------+  +---------------------+  |
|  | Routing Service    |  | Crime Scoring      |  | Anomaly Engine       |  | Safety Verification |  |
|  | (OSRM & Geocoding) |  | (Kaggle Hotspots)  |  | (4 Rule Detectors)   |  | (Countdown & SOS)   |  |
|  +--------------------+  +--------------------+  +----------------------+  +---------------------+  |
|                                             │                                                      |
|                             +---------------+---------------+                                      |
|                             ▼                               ▼                                      |
|                  +--------------------+          +--------------------+                            | 
|                  | Feedback Retraining|          | Notification Engine|                            |
|                  | (Spatial Grid)     |          | (Infobip / Vonage) |                            |
|                  +--------------------+          +--------------------+                            |
+--------------------------------------┬──────────────────────┬--------------------------------------+
                                       │                      │
                                       ▼                      ▼
                    +----------------------+      +-----------------------+
                    | SQLite / PostgreSQL  |      | External Gateways     |
                    | (Tables & Schemas)   |      | (OSRM, SMS, WhatsApp) |
                    +----------------------+      +-----------------------+
```

---

## 4. How the System Works (Step-by-Step Workflow)

### Step 1: User Onboarding & Contact Provisioning
1. The traveler registers with Name, Email, Phone, and Password.
2. The server hashes passwords using Werkzeug (`generate_password_hash`) and stores them in the `users` table.
3. Upon login, the client receives a JSON Web Token (JWT) that is retained in `localStorage` and sent with all API requests.
4. The traveler adds one or more emergency contacts (`emergency_contacts` table) with phone numbers and relationship tags (`Parent`, `Friend`, `Spouse`).
5. A **Test SMS** feature (`POST /api/contacts/:id/test-sms`) allows the user to verify telecom gateway connectivity.

---

### Step 2: Safe Route Planning & Crime Risk Scoring
1. The user inputs their destination.
2. **Geocoding**: The system searches in order:
   - Fast local presets (Bangalore landmarks such as Acharya Institutes, Majestic, Electronic City).
   - Mapbox Places API (if configured).
   - Nominatim OpenStreetMap search.
3. **Multi-Route Generation**: The backend calls OSRM (`router.project-osrm.org`) to fetch up to 3 real street-following driving and walking geometries.
4. **Safety Scoring Algorithm**:
   - The route polyline is sampled every 80 meters (up to 100 sample points).
   - Ingests Kaggle Indian Crimes Dataset (`sudhanvahg/indian-crimes-dataset`), mapping city-level crime records and spreading Bangalore crimes across 30+ neighbourhoods with spatial jitter.
   - For every sample point $(lat_s, lng_s)$, it queries crime hotspots $(lat_h, lng_h)$ within an influence radius of $R = 400\text{m}$:
     $$\text{Haversine Distance: } d = 2r \arcsin \sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)}$$
     $$\text{Weight: } W = 1.0 - \left(\frac{d}{400.0}\right)$$
     $$\text{Exposure} = \sum (h_{\text{intensity}} \times W)$$
   - Evaluates dynamic spatial penalties/bonuses from retrained community feedback.
   - Computes composite Safety Score:
     $$\text{Risk} = \min\left(100.0, \frac{\text{Exposure}}{\text{Samples}} \times 48.0 + \text{Feedback\_Penalty}\right)$$
     $$\text{Safety Score} = \text{round}(\max(0.0, 100.0 - \text{Risk}), 1)$$
5. **Ranking**: The routes are ranked by Safety Score ($\ge 75$ = Low Risk, $50–74$ = Moderate Risk, $< 50$ = High Risk), highlighting the safest option.

---

### Step 3: Journey Initiation & Trusted Contact Handshake
1. The traveler taps **"Start Safe Journey"** (`POST /api/journeys`).
2. A `journeys` record is created with status `active` and a 64-character cryptographic token (`share_token`).
3. An automated notification (`notify_journey_started`) is sent to the primary contact via SMS or in-app logger:
   > *"Swagath started a Safe Journey to MG Road Metro Station. Live tracking: http://localhost:5173/s/3f9a7b..."*
4. The frontend switches to live navigation mode with a full-bleed Leaflet map.

---

### Step 4: Real-time Telemetry Streaming & Offline Queue
1. **Multi-layer Geolocation (`useGeolocation.js`)**:
   - Primary: High-accuracy hardware GPS (`navigator.geolocation.watchPosition`).
   - Secondary: Wi-Fi cell-tower positioning.
   - Tertiary: Server IP fallback (`/api/maps/ip-location`).
   - Quaternary: Default campus landmark.
2. Every **5 seconds**, coordinates (lat, lng, speed, heading, accuracy) are posted to `POST /api/journeys/:id/locations`.
3. **Offline Store-and-Forward (`offlineQueue.js`)**:
   - If the network drops (e.g. in a subway or basement), coordinates are buffered locally in browser storage (up to 80 points).
   - As soon as the connection is restored, the queue automatically syncs buffered points in chronological sequence.

---

### Step 5: Real-time Trip Monitoring Metrics
With each uploaded coordinate, the server calculates:
- **Movement Status**: `moving`, `stopped`, `paused`, `signal_lost`, or `sos`.
- **Speed & Heading**: Hardware device speed or derived delta over recent points.
- **Stop Streak**: Iterates backwards through recent logs while speed $< 0.5\text{ m/s}$ to measure stationary streak duration in seconds.
- **Path Deviation**: Perpendicular orthogonal distance from current position to the planned polyline.
- **Environmental Context**: Converts UTC time to Indian Standard Time (IST) to flag nighttime travel (22:00 to 05:00).
- **Walking ETA**: Estimated time remaining based on straight-line distance to destination.

---

### Step 6: Rule-Based Anomaly Detection
The backend evaluates four safety rules:

| Rule Type | Trigger Condition | Severity | Description |
| :--- | :--- | :--- | :--- |
| **`prolonged_stop`** | `stop_duration_sec >= 150` | Medium | User had started moving, then remained stationary for $\ge 2.5$ minutes. |
| **`route_deviation`** | `deviation_m >= 100` | Medium | Distance from expected route polyline exceeds 100 meters. |
| **`lost_signal`** | `seconds_since_update >= 75` | High | Telemetry stopped arriving while journey is active. |
| **`speed_spike`** | $\Delta \text{speed} \ge 3.5\text{ m/s}$ | Low | Sudden unnatural acceleration compared to recent baseline. |

- **Debounce & Cooldown**: A 180-second cooldown prevents repeated alerts for the same event.
- **Demo Mode**: Includes a simulation endpoint (`POST /api/journeys/:id/demo/simulate-anomaly`) allowing viva evaluators to trigger any anomaly with 1 click from the interface.

---

### Step 7: The "Are You Safe?" Verification Protocol

```
           Anomaly Triggered
                   │
                   ▼
         SafetyCheck Created (status: "pending")
                   │
                   ▼
       Modal: "Are you safe?" (Visual + Audio)
                   │
    ┌──────────────┼───────────────────────────┐
    │              │                           │
    ▼              ▼                           ▼
[I'M SAFE]    [I NEED HELP]            [No User Action]
    │              │                           │
    ▼              ▼                           ▼
Marked Safe    Immediate SOS          Wait 40 seconds
Anomaly Closes SMS Dispatched                  │
Trip Continues                                 ▼
                                      Audible 20s Countdown
                                      ┌────────┴────────┐
                                      ▼                 ▼
                                [User Cancels]    [Timer Hits 0s]
                                      │                 │
                                      ▼                 ▼
                                 Marked Safe       Automatic SOS
                                                   SMS Dispatched
```

- **Server-Side Enforcement**: If the phone loses power or is taken during countdown, backend automated check routines trigger the SOS upon timeout expiration.

---

### Step 8: Multi-Channel Emergency Dispatch & Escalation
When an SOS is activated (manual or automated timeout):
1. The journey status changes to `sos` and an `sos_alerts` record is logged with current GPS coordinates.
2. **Automated SMS Broadcast**: Uses **Infobip** or **Vonage** APIs to dispatch an urgent SMS to all emergency contacts:
   > *"SOS! Swagath: Automatic SOS: no response after anomaly safety verification (prolonged_stop) @ 13.0841,77.4862. Track: http://localhost:5173/s/3f9a7b..."*
3. **1-Click Direct Links**: Generates instant deep links in the UI:
   - **WhatsApp**: `https://wa.me/<number>?text=...`
   - **SMS**: `sms:<number>?body=...`
4. **Emergency Services**: Highlights a prominent one-tap dial button for **112 India** (`tel:112`).

---

### Step 9: Zero-Login Trusted Contact Tracking
- Contacts receive the URL `http://<host>/s/<share_token>`.
- **Zero Authentication Barrier**: The page loads without requiring an account or password.
- Renders the traveler's live position, trail, destination ETA, movement status, active anomalies, and an SOS emergency banner.
- Auto-polls every 5 seconds for continuous real-time updates.

---

### Step 10: Closed-Loop AI Model Retraining from User Feedback
Upon journey completion:
1. The traveler rates the trip (1 to 5 stars) and selects hazard tags (`Poor Lighting`, `Unsafe Area`, `Isolated Street`, `Suspicious Activity`, or `Well Lit & Safe`).
2. **Spatial Grid Retraining (`feedback_service.py`)**:
   - Negative ratings and safety tags apply safety score penalties ($+1.5$ to $+5.0$).
   - Positive ratings and well-lit tags apply safety score bonuses ($-1.5$ to $-3.0$).
   - Creates a spatial cluster with a $350\text{m}$ radius and linear distance decay:
     $$\text{Weight} = \max\left(0, 1.0 - \frac{\text{Distance}}{350.0}\right)$$
3. The AI route scoring model version updates (e.g., `v1.2.0`), immediately influencing all future route calculations in that area.

---

## 5. Database Schema Reference

```
+----------------------------------------------------------------------------------------------------+
|                                            DATABASE SCHEMA                                          |
+----------------------------------------------------------------------------------------------------+

TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT UTC_NOW
);

TABLE emergency_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    relationship VARCHAR(50),
    is_primary BOOLEAN DEFAULT FALSE
);

TABLE journeys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL, -- planned | active | paused | ended | cancelled | sos
    start_lat FLOAT, start_lng FLOAT,
    dest_lat FLOAT, dest_lng FLOAT,
    dest_label VARCHAR(255),
    expected_route_json TEXT,
    share_token VARCHAR(64) UNIQUE NOT NULL,
    active_contact_id INTEGER REFERENCES emergency_contacts(id),
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT UTC_NOW
);

TABLE location_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    lat FLOAT NOT NULL,
    lng FLOAT NOT NULL,
    accuracy FLOAT,
    speed FLOAT,
    heading FLOAT,
    recorded_at TIMESTAMP,
    received_at TIMESTAMP DEFAULT UTC_NOW
);

TABLE anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    type VARCHAR(40) NOT NULL, -- prolonged_stop | route_deviation | lost_signal | speed_spike
    severity VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(20) DEFAULT 'open', -- open | cleared | escalated
    details_json TEXT,
    detected_at TIMESTAMP DEFAULT UTC_NOW,
    cleared_at TIMESTAMP
);

TABLE safety_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    anomaly_id INTEGER NOT NULL REFERENCES anomalies(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending', -- pending | safe | need_help | timeout
    countdown_seconds INTEGER DEFAULT 20,
    prompted_at TIMESTAMP DEFAULT UTC_NOW,
    responded_at TIMESTAMP,
    response VARCHAR(20) -- safe | need_help | NULL
);

TABLE sos_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL, -- manual | automatic
    trigger_reason VARCHAR(255),
    lat FLOAT, lng FLOAT,
    status VARCHAR(20) DEFAULT 'active', -- active | resolved | cancelled
    created_at TIMESTAMP DEFAULT UTC_NOW
);

TABLE route_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    journey_id INTEGER REFERENCES journeys(id),
    dest_label VARCHAR(255),
    lat FLOAT, lng FLOAT,
    rating INTEGER NOT NULL, -- 1 to 5
    safety_tags VARCHAR(255),
    comments TEXT,
    created_at TIMESTAMP DEFAULT UTC_NOW
);
```

---

## 6. System Configuration & Threshold Parameters

| Parameter | Environment Variable | Default Value | Function |
| :--- | :--- | :--- | :--- |
| **GPS Sampling Interval** | `LOCATION_INTERVAL_SEC` | `5` seconds | Frequency of telemetry transmission from client |
| **Prolonged Stop Threshold** | `STOP_THRESHOLD_SEC` | `150` seconds | Stationary duration before triggering an anomaly |
| **Route Deviation Threshold**| `DEVIATION_THRESHOLD_M`| `100` meters | Off-route distance before triggering deviation |
| **Lost Signal Threshold** | `LOST_SIGNAL_SEC` | `75` seconds | Telemetry silence interval before flagging lost signal |
| **Safety Response Window** | `SAFETY_RESPONSE_SEC` | `40` seconds | Duration user has to answer before countdown begins |
| **Countdown Duration** | `SOS_COUNTDOWN_SEC` | `20` seconds | Audible countdown length before automatic SOS dispatch |
| **Anomaly Cooldown** | `ANOMALY_COOLDOWN_SEC` | `180` seconds | Time to prevent duplicate triggers of the same anomaly |
| **Crime Kernel Radius** | `INFLUENCE_RADIUS_M` | `400` meters | Spatial neighborhood radius for route crime exposure |
| **Feedback Kernel Radius** | `FEEDBACK_RADIUS_M` | `350` meters | Community feedback spatial influence radius |
| **Demo Simulator** | `DEMO_MODE` | `true` | Enables 1-click anomaly simulations in UI for viva demos |

---

## 7. How to Run Locally & Execute Automated Tests

### 1. Backend Server
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run.py
```
- API Base URL: `http://localhost:5000`
- Health check: `http://localhost:5000/api/health`

### 2. Frontend Client
```powershell
cd frontend
copy .env.example .env
npm install
npm run dev
```
- Client Application: `http://localhost:5173`

### 3. Automated Test Suite
To verify the entire backend engine across all phases:
```powershell
cd backend
python -m tests.test_auth
python -m tests.test_contacts
python -m tests.test_journey_mode
python -m tests.test_monitoring
python -m tests.test_anomalies
python -m tests.test_safety
python -m tests.test_notify
python -m tests.test_feedback
```

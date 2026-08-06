import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { journeysApi } from "../api/client";
import { useGeolocation } from "../hooks/useGeolocation";

const DEFAULT_INTERVAL_SEC = 5;

/**
 * Phase 4 – GPS tracking page.
 * Starts a minimal journey session and periodically POSTs locations to Flask.
 */
export default function Track() {
  const { token } = useAuth();
  const [journey, setJourney] = useState(null);
  const [tracking, setTracking] = useState(false);
  const [logs, setLogs] = useState([]);
  const [serverCount, setServerCount] = useState(0);
  const [intervalSec, setIntervalSec] = useState(DEFAULT_INTERVAL_SEC);
  const [statusMsg, setStatusMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lastSentAtRef = useRef(0);

  const { position, error: geoError, permissionState, requestOnce } =
    useGeolocation({ enabled: tracking });

  const refreshActive = useCallback(async () => {
    try {
      const data = await journeysApi.active(token);
      setJourney(data.journey);
      if (data.journey?.status === "active") {
        setTracking(true);
        const locData = await journeysApi.listLocations(token, data.journey.id);
        setLogs(locData.locations || []);
        setServerCount(locData.count || 0);
      }
    } catch (err) {
      setError(err.message || "Failed to load journey.");
    }
  }, [token]);

  useEffect(() => {
    refreshActive();
  }, [refreshActive]);

  // Periodically send GPS updates while tracking
  useEffect(() => {
    if (!tracking || !journey || journey.status !== "active" || !position) {
      return;
    }

    const intervalMs = intervalSec * 1000;

    async function sendIfDue() {
      const now = Date.now();
      if (now - lastSentAtRef.current < intervalMs - 200) return;
      lastSentAtRef.current = now;
      try {
        const data = await journeysApi.postLocation(token, journey.id, position);
        setStatusMsg(`Last upload: ${new Date().toLocaleTimeString()}`);
        if (data.interval_sec) setIntervalSec(data.interval_sec);
        setLogs((prev) => {
          const next = [...prev, data.location];
          return next.slice(-30);
        });
        setServerCount((c) => c + 1);
        setError("");
      } catch (err) {
        setError(err.message || "Failed to upload location.");
      }
    }

    sendIfDue();
    const id = setInterval(sendIfDue, intervalMs);
    return () => clearInterval(id);
  }, [tracking, journey, position, token, intervalSec]);

  async function startTracking() {
    setBusy(true);
    setError("");
    setStatusMsg("");
    try {
      const pos = await requestOnce();
      const data = await journeysApi.start(token, {
        start_lat: pos.lat,
        start_lng: pos.lng,
        dest_label: "GPS tracking session (Phase 4)",
      });
      setJourney(data.journey);
      setLogs([]);
      setServerCount(0);
      lastSentAtRef.current = 0;
      setTracking(true);
      setStatusMsg("Tracking started. Keep this tab open.");
    } catch (err) {
      setError(err.message || "Could not start tracking.");
      setTracking(false);
    } finally {
      setBusy(false);
    }
  }

  async function stopTracking() {
    if (!journey) return;
    setBusy(true);
    setError("");
    try {
      const data = await journeysApi.end(token, journey.id);
      setJourney(data.journey);
      setTracking(false);
      setStatusMsg("Tracking stopped. Journey ended.");
    } catch (err) {
      setError(err.message || "Could not end journey.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page track-page">
      <section className="panel track-panel">
        <h1>GPS location tracking</h1>
        <p className="muted">
          Phase 4: browser GPS → Flask → database. Keep this tab open while
          tracking. Background GPS in browsers is unreliable.
        </p>

        {error && <div className="alert alert-error">{error}</div>}
        {geoError && tracking && (
          <div className="alert alert-error">{geoError}</div>
        )}
        {statusMsg && <div className="alert alert-success">{statusMsg}</div>}

        <div className="track-controls">
          {!tracking ? (
            <button
              type="button"
              className="btn"
              onClick={startTracking}
              disabled={busy}
            >
              {busy ? "Starting…" : "Start GPS tracking"}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-danger"
              onClick={stopTracking}
              disabled={busy}
            >
              {busy ? "Stopping…" : "Stop tracking"}
            </button>
          )}
          <Link className="btn btn-ghost" to="/contacts">
            Contacts
          </Link>
        </div>

        <div className="profile-grid track-stats">
          <div>
            <span className="label">Permission</span>
            <p>{permissionState}</p>
          </div>
          <div>
            <span className="label">Journey</span>
            <p>
              {journey
                ? `#${journey.id} · ${journey.status}`
                : "None"}
            </p>
          </div>
          <div>
            <span className="label">Upload interval</span>
            <p>{intervalSec}s</p>
          </div>
          <div>
            <span className="label">Points saved</span>
            <p>{serverCount}</p>
          </div>
        </div>

        <div className="gps-live">
          <h2>Live GPS reading</h2>
          {position ? (
            <div className="profile-grid">
              <div>
                <span className="label">Latitude</span>
                <p className="mono">{position.lat.toFixed(6)}</p>
              </div>
              <div>
                <span className="label">Longitude</span>
                <p className="mono">{position.lng.toFixed(6)}</p>
              </div>
              <div>
                <span className="label">Accuracy</span>
                <p>
                  {position.accuracy != null
                    ? `${Math.round(position.accuracy)} m`
                    : "—"}
                </p>
              </div>
              <div>
                <span className="label">Speed</span>
                <p>
                  {position.speed != null
                    ? `${position.speed.toFixed(2)} m/s`
                    : "—"}
                </p>
              </div>
              <div>
                <span className="label">Heading</span>
                <p>
                  {position.heading != null
                    ? `${Math.round(position.heading)}°`
                    : "—"}
                </p>
              </div>
              <div>
                <span className="label">Recorded at</span>
                <p className="mono small">
                  {new Date(position.recorded_at).toLocaleString()}
                </p>
              </div>
            </div>
          ) : (
            <p className="muted">
              No reading yet. Click Start to request location permission.
            </p>
          )}
        </div>

        <div className="recent-logs">
          <h2>Recent uploads (this session)</h2>
          {logs.length === 0 ? (
            <p className="muted">No points uploaded yet.</p>
          ) : (
            <ul className="log-list">
              {[...logs].reverse().map((log) => (
                <li key={log.id} className="log-item">
                  <span className="mono">
                    {log.lat.toFixed(5)}, {log.lng.toFixed(5)}
                  </span>
                  <span className="muted">
                    {log.recorded_at
                      ? new Date(log.recorded_at).toLocaleTimeString()
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <p className="fineprint">
          Note: On a phone, use HTTPS or the same Wi‑Fi LAN URL. Allow location
          when prompted. Closing this tab stops reliable updates.
        </p>
      </section>
    </main>
  );
}

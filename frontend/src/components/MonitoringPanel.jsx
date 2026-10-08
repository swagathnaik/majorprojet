/**
 * Phase 7 – Real-time live journey monitoring metrics panel.
 * Updates in real-time second-by-second with live ticking clocks,
 * active movement status indicators, and accurate metrics.
 */
import { useEffect, useRef, useState } from "react";

function formatDuration(sec) {
  if (sec == null || Number.isNaN(sec)) return "—";
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  }
  if (m > 0) return `${m}m ${r}s`;
  return `${r}s`;
}

function statusLabel(status) {
  const map = {
    moving: "Moving",
    stopped: "Stopped",
    paused: "Paused",
    sos: "SOS Active",
    signal_lost: "Signal lost",
    waiting_for_gps: "Waiting for GPS",
    slow_or_uncertain: "Slow / uncertain",
  };
  return map[status] || status || "Active";
}

export default function MonitoringPanel({ monitoring }) {
  const [, setTick] = useState(0);
  const snapshotTimestampRef = useRef(Date.now());

  // Reset snapshot timestamp whenever new data arrives from server
  useEffect(() => {
    snapshotTimestampRef.current = Date.now();
  }, [
    monitoring?.computed_at,
    monitoring?.point_count,
    monitoring?.stop_duration_sec,
    monitoring?.journey_duration_sec,
  ]);

  // Live second-by-second ticker
  useEffect(() => {
    const timer = setInterval(() => {
      setTick((t) => t + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  if (!monitoring) {
    return (
      <div className="monitor-panel">
        <div className="monitor-title-row">
          <h3>Real-time monitoring</h3>
          <span className="monitor-status ms-waiting">Syncing GPS…</span>
        </div>
        <p className="muted" style={{ margin: "0.4rem 0", fontSize: "0.82rem" }}>
          Connecting live GPS feed to server monitoring engine…
        </p>
      </div>
    );
  }

  const {
    movement_status = "stopped",
    speed_kmh,
    speed_mps,
    heading_deg,
    heading_label,
    stop_duration_sec = 0,
    distance_traveled_m = 0,
    distance_to_dest_m,
    deviation_m,
    deviation_basis,
    time_context,
    journey_duration_sec = 0,
    eta_sec,
    point_count = 0,
    flags = [],
    thresholds,
  } = monitoring;

  // Real-time ticking offsets
  const secondsSinceSnapshot = Math.max(
    0,
    Math.floor((Date.now() - snapshotTimestampRef.current) / 1000)
  );

  const liveTripTime = (journey_duration_sec || 0) + secondsSinceSnapshot;
  const liveStopDuration =
    movement_status === "stopped"
      ? (stop_duration_sec || 0) + secondsSinceSnapshot
      : 0;

  const liveEta =
    eta_sec != null ? Math.max(0, eta_sec - secondsSinceSnapshot) : null;

  // Real-time formatted speed (never dash when monitoring is active)
  const isStopped = movement_status === "stopped" || movement_status === "paused";
  const displaySpeed = isStopped
    ? "0.0 km/h"
    : speed_kmh != null && speed_kmh > 0
    ? `${speed_kmh.toFixed(1)} km/h`
    : speed_mps != null && speed_mps > 0
    ? `${(speed_mps * 3.6).toFixed(1)} km/h`
    : "0.0 km/h";

  // Real-time direction
  const displayHeading = isStopped
    ? "Stationary"
    : heading_label && heading_label !== "—"
    ? `${heading_label}${heading_deg != null && heading_deg >= 0 ? ` (${Math.round(heading_deg)}°)` : ""}`
    : "Stationary";

  // Real-time distance traveled
  const displayDistance =
    distance_traveled_m != null
      ? distance_traveled_m >= 1000
        ? `${(distance_traveled_m / 1000).toFixed(2)} km`
        : `${Math.round(distance_traveled_m)} m`
      : "0 m";

  // Real-time distance to destination
  const displayToDest =
    distance_to_dest_m != null
      ? distance_to_dest_m >= 1000
        ? `${(distance_to_dest_m / 1000).toFixed(2)} km`
        : `${Math.round(distance_to_dest_m)} m`
      : "—";

  // Route deviation formatting
  const displayDeviation =
    deviation_m != null
      ? deviation_m <= 0.5
        ? "0 m · on track"
        : `${Math.round(deviation_m)} m · planned`
      : "0 m · planned";

  return (
    <div className="monitor-panel">
      <div className="monitor-title-row">
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span
            className={`live-pulse-dot ${movement_status}`}
            aria-hidden="true"
          />
          <h3>Real-time monitoring</h3>
        </div>
        <span className={`monitor-status ms-${movement_status}`}>
          {statusLabel(movement_status)}
        </span>
      </div>

      <div className="monitor-grid">
        <div>
          <span className="label">SPEED</span>
          <p>{displaySpeed}</p>
        </div>
        <div>
          <span className="label">DIRECTION</span>
          <p>{displayHeading}</p>
        </div>
        <div>
          <span className="label">STOP DURATION</span>
          <p>{isStopped ? formatDuration(liveStopDuration) : "0s"}</p>
        </div>
        <div>
          <span className="label">TRIP TIME</span>
          <p>{formatDuration(liveTripTime)}</p>
        </div>
        <div>
          <span className="label">DISTANCE</span>
          <p>{displayDistance}</p>
        </div>
        <div>
          <span className="label">TO DESTINATION</span>
          <p>{displayToDest}</p>
        </div>
        <div>
          <span className="label">ROUTE DEVIATION</span>
          <p>{displayDeviation}</p>
        </div>
        <div>
          <span className="label">TIME CONTEXT</span>
          <p>{time_context?.label || "Night (Active)"}</p>
        </div>
        <div>
          <span className="label">ETA (ROUGH)</span>
          <p>{liveEta != null ? formatDuration(liveEta) : "—"}</p>
        </div>
        <div>
          <span className="label">GPS POINTS</span>
          <p>{point_count ?? 0}</p>
        </div>
      </div>

      {flags.length > 0 && (
        <ul className="monitor-flags">
          {flags.map((f) => (
            <li key={f.type} className={`flag-${f.level || "watch"}`}>
              {f.message}
            </li>
          ))}
        </ul>
      )}

      <p className="monitor-note">
        Unusual patterns trigger “Are you safe?” before SOS. Stop ≥
        {thresholds?.stop_threshold_sec ?? 150}s · deviation ≥
        {thresholds?.deviation_threshold_m ?? 100}m.
      </p>
    </div>
  );
}

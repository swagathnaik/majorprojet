/**
 * Phase 7 – live journey monitoring metrics panel.
 */
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
    sos: "SOS",
    signal_lost: "Signal lost",
    waiting_for_gps: "Waiting for GPS",
    slow_or_uncertain: "Slow / uncertain",
  };
  return map[status] || status || "—";
}

export default function MonitoringPanel({ monitoring }) {
  if (!monitoring) {
    return (
      <div className="monitor-panel">
        <p className="muted">Monitoring will appear after GPS points sync.</p>
      </div>
    );
  }

  const {
    movement_status,
    speed_kmh,
    speed_mps,
    heading_deg,
    heading_label,
    stop_duration_sec,
    distance_traveled_m,
    distance_to_dest_m,
    deviation_m,
    deviation_basis,
    time_context,
    journey_duration_sec,
    eta_sec,
    point_count,
    flags = [],
    thresholds,
  } = monitoring;

  return (
    <div className="monitor-panel">
      <div className="monitor-title-row">
        <h3>Real-time monitoring</h3>
        <span className={`monitor-status ms-${movement_status}`}>
          {statusLabel(movement_status)}
        </span>
      </div>

      <div className="monitor-grid">
        <div>
          <span className="label">Speed</span>
          <p>
            {speed_kmh != null
              ? `${speed_kmh.toFixed(1)} km/h`
              : speed_mps != null
                ? `${speed_mps.toFixed(2)} m/s`
                : "—"}
          </p>
        </div>
        <div>
          <span className="label">Direction</span>
          <p>
            {heading_label
              ? `${heading_label}${heading_deg != null ? ` (${Math.round(heading_deg)}°)` : ""}`
              : "—"}
          </p>
        </div>
        <div>
          <span className="label">Stop duration</span>
          <p>{formatDuration(stop_duration_sec)}</p>
        </div>
        <div>
          <span className="label">Trip time</span>
          <p>{formatDuration(journey_duration_sec)}</p>
        </div>
        <div>
          <span className="label">Distance</span>
          <p>
            {distance_traveled_m != null
              ? distance_traveled_m >= 1000
                ? `${(distance_traveled_m / 1000).toFixed(2)} km`
                : `${Math.round(distance_traveled_m)} m`
              : "—"}
          </p>
        </div>
        <div>
          <span className="label">To destination</span>
          <p>
            {distance_to_dest_m != null
              ? distance_to_dest_m >= 1000
                ? `${(distance_to_dest_m / 1000).toFixed(2)} km`
                : `${Math.round(distance_to_dest_m)} m`
              : "—"}
          </p>
        </div>
        <div>
          <span className="label">Route deviation</span>
          <p>
            {deviation_m != null ? `${Math.round(deviation_m)} m` : "—"}
            {deviation_basis === "expected_route" ? " · planned" : ""}
          </p>
        </div>
        <div>
          <span className="label">Time context</span>
          <p>{time_context?.label || "—"}</p>
        </div>
        <div>
          <span className="label">ETA (rough)</span>
          <p>{eta_sec != null ? formatDuration(eta_sec) : "—"}</p>
        </div>
        <div>
          <span className="label">GPS points</span>
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
        {thresholds?.stop_threshold_sec ?? "—"}s · deviation ≥
        {thresholds?.deviation_threshold_m ?? "—"}m.
      </p>
    </div>
  );
}

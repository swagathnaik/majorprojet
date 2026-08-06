/**
 * Phase 8 – open anomaly banner + demo simulate controls.
 */
const TYPE_LABELS = {
  prolonged_stop: "Prolonged inactivity",
  route_deviation: "Route deviation",
  lost_signal: "Lost location signal",
  speed_spike: "Sudden speed change",
};

export default function AnomalyBanner({
  anomalies = [],
  safetyCheck = null,
  onSimulate = null,
  simulating = false,
}) {
  const open = anomalies.filter((a) => a.status === "open");

  return (
    <div className="anomaly-wrap">
      {open.length > 0 ? (
        <div className="alert alert-anomaly">
          <strong>Unusual activity detected</strong>
          <ul className="anomaly-list">
            {open.map((a) => (
              <li key={a.id}>
                {TYPE_LABELS[a.type] || a.type}
                {a.details?.message ? ` — ${a.details.message}` : ""}
                <span className="anomaly-meta">
                  {" "}
                  · {a.severity} · #{a.id}
                </span>
              </li>
            ))}
          </ul>
          {safetyCheck?.status === "pending" && (
            <p className="anomaly-next">
              Safety check open — please answer the “Are you safe?” prompt.
            </p>
          )}
        </div>
      ) : (
        <p className="anomaly-idle muted">No open anomalies.</p>
      )}

      {onSimulate && (
        <div className="demo-anomaly-row">
          <span className="muted">Demo:</span>
          <button
            type="button"
            className="btn btn-ghost btn-tiny"
            disabled={simulating || safetyCheck?.status === "pending"}
            onClick={() => onSimulate("prolonged_stop")}
          >
            Simulate stop
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-tiny"
            disabled={simulating || safetyCheck?.status === "pending"}
            onClick={() => onSimulate("route_deviation")}
          >
            Simulate deviation
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-tiny"
            disabled={simulating || safetyCheck?.status === "pending"}
            onClick={() => onSimulate("lost_signal")}
          >
            Simulate signal loss
          </button>
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect, useRef } from "react";
import MonitoringPanel from "./MonitoringPanel";
import AnomalyBanner from "./AnomalyBanner";

export default function JourneyBottomSheet({
  journey,
  monitoring,
  openAnomalies = [],
  safetyCheck = null,
  sosAlert = null,
  serverCount = 0,
  shareUrl = "",
  shareCopied = false,
  copyShareLink,
  mapPosition,
  position,
  error = "",
  geoError = "",
  statusMsg = "",
  offlinePending = 0,
  permissionState = "granted",
  intervalSec = 5,
  followMode = true,
  setFollowMode,
  triggerSos,
  runAction,
  simulateAnomaly,
  simulating = false,
  busy = false,
  isContactView = false,
  load,
  emergency,
  traveler,
  contactName,
  locationCount,
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const touchStartYRef = useRef(null);

  // Auto-expand on high priority safety alerts like SOS or Anomaly
  useEffect(() => {
    if (sosAlert || openAnomalies.length > 0 || safetyCheck) {
      setIsExpanded(true);
    }
  }, [sosAlert, openAnomalies.length, safetyCheck]);

  const toggleExpand = () => setIsExpanded((prev) => !prev);

  // Touch drag handlers for swiping sheet up or down
  const handleTouchStart = (e) => {
    touchStartYRef.current = e.touches[0].clientY;
  };

  const handleTouchEnd = (e) => {
    if (touchStartYRef.current === null) return;
    const touchEndY = e.changedTouches[0].clientY;
    const diffY = touchStartYRef.current - touchEndY;
    // Swipe up -> expand, Swipe down -> collapse
    if (diffY > 40) {
      setIsExpanded(true);
    } else if (diffY < -40) {
      setIsExpanded(false);
    }
    touchStartYRef.current = null;
  };

  // Format quick metrics for peek view
  const speedStr =
    monitoring?.speed_kmh != null
      ? `${monitoring.speed_kmh.toFixed(1)} km/h`
      : monitoring?.speed_mps != null
      ? `${(monitoring.speed_mps * 3.6).toFixed(1)} km/h`
      : null;

  const etaStr =
    monitoring?.eta_sec != null
      ? monitoring.eta_sec >= 3600
        ? `${Math.floor(monitoring.eta_sec / 3600)}h ${Math.floor((monitoring.eta_sec % 3600) / 60)}m`
        : `${Math.ceil(monitoring.eta_sec / 60)}m`
      : null;

  const distStr =
    monitoring?.distance_to_dest_m != null
      ? monitoring.distance_to_dest_m >= 1000
        ? `${(monitoring.distance_to_dest_m / 1000).toFixed(1)} km`
        : `${Math.round(monitoring.distance_to_dest_m)} m`
      : null;

  const activeStatus = journey?.status || "active";
  const contactDisplayName = isContactView
    ? contactName || "Contact"
    : journey?.contact?.name || "—";
  const destName = isContactView
    ? `${traveler?.first_name || "Traveler"} → ${journey?.dest_label || "Destination"}`
    : journey?.dest_label || "Journey Destination";

  return (
    <div className="bottom-sheet-wrapper">
      {/* Floating Map Controls positioned right above the bottom sheet */}
      <div className="floating-map-actions">
        {setFollowMode && (
          <button
            type="button"
            className={`btn-floating-action ${followMode ? "active" : ""}`}
            onClick={() => setFollowMode((v) => !v)}
            title={followMode ? "Following target" : "Recenter map"}
          >
            <span className="floating-icon">🎯</span>
            <span className="floating-text">{followMode ? "Following" : "Recenter"}</span>
          </button>
        )}
        <button
          type="button"
          className="btn-floating-action"
          onClick={toggleExpand}
          title={isExpanded ? "Collapse sheet" : "Expand sheet"}
        >
          <span className="floating-icon">{isExpanded ? "🔽" : "🔼"}</span>
          <span className="floating-text">{isExpanded ? "Minimize" : "Details"}</span>
        </button>
      </div>

      {/* Main Bottom Sheet Container */}
      <div
        className={`bottom-sheet-container ${isExpanded ? "expanded" : "collapsed"}`}
      >
        {/* Drag Handle Bar & Header (Clickable & Swipable) */}
        <div
          className="bottom-sheet-header"
          onClick={toggleExpand}
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") toggleExpand();
          }}
          aria-label={isExpanded ? "Collapse bottom sheet" : "Expand bottom sheet"}
        >
          <div className="bottom-sheet-drag-pill" />

          {/* Peek Summary Bar */}
          <div className="bottom-sheet-peek-bar">
            <div className="peek-main-info">
              <span className={`status-pill status-${activeStatus}`}>
                {activeStatus}
              </span>
              <span className="peek-dest-label" title={destName}>
                {destName}
              </span>
            </div>

            {/* Quick Metrics (visible in collapsed peek view) */}
            <div className="peek-stats-chips">
              {speedStr && (
                <div className="stat-chip" title="Current Speed">
                  <span className="chip-icon">⚡</span>
                  <span className="chip-val">{speedStr}</span>
                </div>
              )}
              {etaStr && (
                <div className="stat-chip" title="Estimated Time of Arrival">
                  <span className="chip-icon">⏱️</span>
                  <span className="chip-val">{etaStr}</span>
                </div>
              )}
              {distStr && (
                <div className="stat-chip" title="Distance Remaining">
                  <span className="chip-icon">📍</span>
                  <span className="chip-val">{distStr}</span>
                </div>
              )}
            </div>

            {/* Quick Actions in Peek Bar */}
            <div className="peek-actions">
              {!isContactView && triggerSos && (
                <button
                  type="button"
                  className="sos-btn sos-btn-compact"
                  onClick={(e) => {
                    e.stopPropagation();
                    triggerSos();
                  }}
                  disabled={busy || activeStatus === "sos"}
                >
                  SOS
                </button>
              )}
              <button
                type="button"
                className="btn-chevron-toggle"
                onClick={(e) => {
                  e.stopPropagation();
                  toggleExpand();
                }}
                aria-label="Toggle details view"
              >
                {isExpanded ? "▼" : "▲"}
              </button>
            </div>
          </div>
        </div>

        {/* Sheet Inner Scrollable Content */}
        <div className="bottom-sheet-content">
          {/* SOS Emergency Box */}
          {sosAlert && !isContactView && (
            <div className="sos-alert-box-sheet">
              <div className="sos-title">
                🚨 EMERGENCY SOS ACTIVE — Alert #{sosAlert.id}
              </div>
              <div className="sos-desc">
                {sosAlert.trigger_reason || "User requested emergency assistance."}
              </div>
              <div className="sos-action-buttons">
                {journey?.contact?.phone && (
                  <>
                    <a
                      className="btn btn-sm btn-whatsapp"
                      href={`https://wa.me/${
                        journey.contact.phone.replace(/\D/g, "").length === 10
                          ? "91" + journey.contact.phone.replace(/\D/g, "")
                          : journey.contact.phone.replace(/\D/g, "")
                      }?text=${encodeURIComponent(
                        `🚨 EMERGENCY SOS ALERT! I need help!\n\nReason: ${
                          sosAlert.trigger_reason || "Emergency"
                        }\n\n📍 Live Tracking: ${shareUrl}\n\nPlease check on me immediately or dial 112!`
                      )}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      📲 Send WhatsApp Msg
                    </a>
                    <a
                      className="btn btn-sm btn-sms"
                      href={`sms:${journey.contact.phone.replace(/\D/g, "")}?body=${encodeURIComponent(
                        `SOS ALERT! I need help! Track: ${shareUrl}`
                      )}`}
                    >
                      💬 Send SMS
                    </a>
                    <a
                      className="btn btn-sm btn-call"
                      href={`tel:${journey.contact.phone}`}
                    >
                      📞 Call {journey.contact.name}
                    </a>
                  </>
                )}
                <a className="btn btn-sm btn-112" href="tel:112">
                  🚨 Call 112
                </a>
              </div>
            </div>
          )}

          {/* Contact View SOS Alert */}
          {isContactView && sosAlert && (
            <div className="sos-alert-box-sheet">
              <div className="sos-title">🚨 SOS ACTIVE</div>
              <div className="sos-desc">
                Reason: {sosAlert.trigger_reason || sosAlert.type}
              </div>
              {sosAlert.lat != null && (
                <div className="mono tiny text-red-200">
                  Coordinates: {sosAlert.lat.toFixed(5)}, {sosAlert.lng.toFixed(5)}
                </div>
              )}
            </div>
          )}

          {/* Anomaly & Safety Banner */}
          {!isContactView && (
            <AnomalyBanner
              anomalies={openAnomalies}
              safetyCheck={safetyCheck}
              onSimulate={
                activeStatus === "active" || activeStatus === "paused"
                  ? simulateAnomaly
                  : null
              }
              simulating={simulating}
            />
          )}

          {/* Meta Info Row: Contact & Point Count */}
          <div className="sheet-info-row">
            <span>
              {isContactView ? "Trusted contact view · " : "Contact: "}
              <strong>{contactDisplayName}</strong>
            </span>
            <span className="mono-pts">
              {isContactView ? `${locationCount || 0} pts` : `${serverCount} pts`}
            </span>
          </div>

          {/* Share Tracking Link */}
          {!isContactView && shareUrl && (
            <div className="share-box">
              <div className="share-label">Shared tracking link</div>
              <div className="share-row">
                <input readOnly value={shareUrl} className="share-input" />
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={copyShareLink}
                >
                  {shareCopied ? "Copied" : "Copy"}
                </button>
                <a
                  className="btn btn-ghost"
                  href={shareUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open
                </a>
              </div>
            </div>
          )}

          {/* GPS Coordinates & System Banners */}
          {mapPosition && (
            <div className="map-info-coords mono">
              {mapPosition.lat.toFixed(5)}, {mapPosition.lng.toFixed(5)}
              {position?.accuracy != null
                ? ` · ±${Math.round(position.accuracy)}m`
                : ""}
            </div>
          )}
          {error && <div className="map-error">{error}</div>}
          {geoError && <div className="map-error">{geoError}</div>}
          {statusMsg && <div className="map-ok">{statusMsg}</div>}
          {offlinePending > 0 && (
            <div className="map-error">
              Offline queue: {offlinePending} item(s) waiting to sync
            </div>
          )}

          {/* Real-time Monitoring Stats Grid */}
          <MonitoringPanel monitoring={monitoring} />

          {/* Action Control Buttons */}
          <div className="journey-controls map-controls">
            {!isContactView && (
              <>
                {activeStatus === "active" && runAction && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={busy}
                    onClick={() => runAction("pause")}
                  >
                    Pause
                  </button>
                )}
                {activeStatus === "paused" && runAction && (
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    onClick={() => runAction("resume")}
                  >
                    Resume
                  </button>
                )}
                {setFollowMode && (
                  <button
                    type="button"
                    className={`btn btn-ghost ${followMode ? "btn-follow-on" : ""}`}
                    onClick={() => setFollowMode((v) => !v)}
                  >
                    {followMode ? "Following" : "Follow me"}
                  </button>
                )}
                {runAction && (
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    onClick={() => runAction("end")}
                  >
                    End
                  </button>
                )}
                {(activeStatus === "active" || activeStatus === "paused") &&
                  runAction && (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={busy}
                      onClick={() => runAction("cancel")}
                    >
                      Cancel
                    </button>
                  )}
                {activeStatus === "sos" && (
                  <a className="btn btn-danger" href="tel:112">
                    Call 112
                  </a>
                )}
              </>
            )}

            {isContactView && (
              <>
                <a className="btn" href="tel:112">
                  Call 112 (optional)
                </a>
                {load && (
                  <button type="button" className="btn btn-ghost" onClick={load}>
                    Refresh
                  </button>
                )}
              </>
            )}
          </div>

          {/* Footer Metadata */}
          <p className="map-attrib muted">
            {isContactView ? (
              <>
                {emergency?.note ||
                  "SafeRoute does not auto-dial emergency services."}{" "}
                Auto-refresh 5s.
              </>
            ) : (
              <>
                GPS: {permissionState} · {intervalSec}s sync · share auto-sent to{" "}
                {journey?.contact?.name || "contact"}
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}

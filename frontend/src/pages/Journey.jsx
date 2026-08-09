import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { journeysApi, safetyApi } from "../api/client";
import { useGeolocation } from "../hooks/useGeolocation";
import JourneyMap from "../components/JourneyMap";
import MonitoringPanel from "../components/MonitoringPanel";
import AnomalyBanner from "../components/AnomalyBanner";
import SafetyModal from "../components/SafetyModal";
import SafeRoutePlanner from "../components/SafeRoutePlanner";
import JourneyBottomSheet from "../components/JourneyBottomSheet";
import {
  enqueueOffline,
  flushOfflineQueue,
  pendingOfflineCount,
} from "../utils/offlineQueue";

const DEFAULT_INTERVAL_SEC = 5;

function contactNotifyMessage(notifications, fallback) {
  if (!Array.isArray(notifications) || notifications.length === 0) {
    return fallback;
  }
  const names = notifications.map((n) => n.contact_name).filter(Boolean);
  if (names.length) {
    return `${fallback} — message sent to ${names.join(", ")}.`;
  }
  return `${fallback} — ${notifications.length} contact(s) notified.`;
}

/**
 * Full Safe Journey pipeline:
 * start → GPS + auto-share → monitor → anomaly → "Are you safe?" → SOS → contact / 112
 */
export default function Journey() {
  const { token } = useAuth();
  const [journey, setJourney] = useState(null);
  const [logs, setLogs] = useState([]);
  const [serverCount, setServerCount] = useState(0);
  const [intervalSec, setIntervalSec] = useState(DEFAULT_INTERVAL_SEC);
  const [statusMsg, setStatusMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sosAlert, setSosAlert] = useState(null);
  const [followMode, setFollowMode] = useState(true);
  const [monitoring, setMonitoring] = useState(null);
  const [openAnomalies, setOpenAnomalies] = useState([]);
  const [safetyCheck, setSafetyCheck] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const [shareCopied, setShareCopied] = useState(false);
  const [offlinePending, setOfflinePending] = useState(0);
  const lastSentAtRef = useRef(0);

  const isLive = journey?.status === "active";
  const inProgress = ["active", "paused", "sos"].includes(journey?.status);

  const { position, error: geoError, permissionState } = useGeolocation({
    enabled: isLive || journey?.status === "paused",
  });

  function applyMonitoringPayload(data) {
    if (data.monitoring) setMonitoring(data.monitoring);
    if (data.open_anomalies) setOpenAnomalies(data.open_anomalies);
    if ("active_safety_check" in data) setSafetyCheck(data.active_safety_check);
    if (data.newly_created_anomalies?.length) {
      setStatusMsg(
        `Anomaly detected: ${data.newly_created_anomalies
          .map((a) => a.type)
          .join(", ")}`
      );
    }
  }

  const refreshActive = useCallback(async () => {
    try {
      const data = await journeysApi.active(token);
      setJourney(data.journey);
      if (data.journey) {
        setShareUrl(data.journey.share_url || "");
        const locData = await journeysApi.listLocations(token, data.journey.id);
        setLogs(locData.locations || []);
        setServerCount(locData.count || 0);
        try {
          const mon = await journeysApi.monitoring(token, data.journey.id);
          applyMonitoringPayload(mon);
        } catch {
          /* optional */
        }
      } else {
        setMonitoring(null);
        setOpenAnomalies([]);
        setSafetyCheck(null);
        setShareUrl("");
      }
    } catch (err) {
      setError(err.message || "Failed to load journey.");
    }
  }, [token]);

  useEffect(() => {
    refreshActive();
  }, [refreshActive]);

  useEffect(() => {
    async function flush() {
      const result = await flushOfflineQueue({
        token,
        postLocation: journeysApi.postLocation,
        postSos: journeysApi.sos,
      });
      setOfflinePending(result.remaining);
      if (result.flushed) {
        setStatusMsg(`Synced ${result.flushed} offline update(s).`);
        refreshActive();
      }
    }
    flush();
    window.addEventListener("online", flush);
    return () => window.removeEventListener("online", flush);
  }, [token, refreshActive]);

  useEffect(() => {
    if (!inProgress || !journey) return undefined;
    let cancelled = false;

    async function tick() {
      try {
        const mon = await journeysApi.monitoring(token, journey.id);
        if (!cancelled) applyMonitoringPayload(mon);
      } catch {
        /* ignore */
      }
    }

    tick();
    const id = setInterval(tick, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [inProgress, journey, token]);

  useEffect(() => {
    if (!isLive || !journey || !position) return;

    const intervalMs = intervalSec * 1000;

    async function sendIfDue() {
      const now = Date.now();
      if (now - lastSentAtRef.current < intervalMs - 200) return;
      lastSentAtRef.current = now;
      try {
        if (!navigator.onLine) {
          enqueueOffline({
            kind: "location",
            journeyId: journey.id,
            payload: position,
          });
          setOfflinePending(pendingOfflineCount());
          setStatusMsg("Offline — location queued for sync.");
          return;
        }
        const data = await journeysApi.postLocation(token, journey.id, position);
        setStatusMsg(`Location synced · ${new Date().toLocaleTimeString()}`);
        if (data.interval_sec) setIntervalSec(data.interval_sec);
        setLogs((prev) => [...prev, data.location].slice(-200));
        setServerCount((c) => c + 1);
        applyMonitoringPayload(data);
        setError("");
      } catch (err) {
        enqueueOffline({
          kind: "location",
          journeyId: journey.id,
          payload: position,
        });
        setOfflinePending(pendingOfflineCount());
        setError(err.message || "Failed to upload location — queued offline.");
      }
    }

    sendIfDue();
    const id = setInterval(sendIfDue, intervalMs);
    return () => clearInterval(id);
  }, [isLive, journey, position, token, intervalSec]);

  async function startJourneyFromPlanner(payload) {
    setBusy(true);
    setError("");
    setStatusMsg("");
    setSosAlert(null);
    setShareCopied(false);
    try {
      const data = await journeysApi.start(token, payload);
      setJourney(data.journey);
      setShareUrl(data.share?.share_url || data.journey?.share_url || "");
      setLogs([]);
      setServerCount(0);
      setMonitoring(null);
      setOpenAnomalies([]);
      setSafetyCheck(null);
      lastSentAtRef.current = 0;
      setFollowMode(true);
      setStatusMsg(
        data.message ||
          "Safe Journey started. Tracking link shared with trusted contact."
      );
    } catch (err) {
      setError(err.message || "Could not start journey.");
      throw err;
    } finally {
      setBusy(false);
    }
  }

  async function copyShareLink() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setShareCopied(true);
      setStatusMsg("Tracking link copied.");
    } catch {
      setError("Could not copy link — select and copy manually.");
    }
  }

  async function runAction(action) {
    if (!journey) return;
    setBusy(true);
    setError("");
    try {
      let data;
      if (action === "pause") data = await journeysApi.pause(token, journey.id);
      if (action === "resume") data = await journeysApi.resume(token, journey.id);
      if (action === "end") data = await journeysApi.end(token, journey.id);
      if (action === "cancel") {
        const ok = window.confirm("Cancel this Safe Journey?");
        if (!ok) return;
        data = await journeysApi.cancel(token, journey.id);
      }
      setJourney(data.journey);
      setStatusMsg(data.message || "Updated.");
      if (["ended", "cancelled"].includes(data.journey.status)) {
        setSosAlert(null);
        setShareUrl("");
      }
    } catch (err) {
      setError(err.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function triggerSos() {
    if (!journey) return;
    const ok = window.confirm(
      "Trigger MANUAL SOS?\n\nTrusted contact will be notified with your live tracking link."
    );
    if (!ok) return;

    setBusy(true);
    setError("");
    const payload = position
      ? { lat: position.lat, lng: position.lng }
      : {};
    try {
      if (!navigator.onLine) {
        enqueueOffline({ kind: "sos", journeyId: journey.id, payload });
        setOfflinePending(pendingOfflineCount());
        setStatusMsg("Offline — SOS queued; will send when network returns.");
        setJourney((j) => (j ? { ...j, status: "sos" } : j));
        return;
      }
      const data = await journeysApi.sos(token, journey.id, payload);
      setJourney(data.journey);
      setSosAlert(data.sos);
      setStatusMsg(
        contactNotifyMessage(
          data.notifications,
          "SOS triggered — emergency contacts notified"
        )
      );
    } catch (err) {
      enqueueOffline({ kind: "sos", journeyId: journey.id, payload });
      setOfflinePending(pendingOfflineCount());
      setError(err.message || "SOS failed — queued offline.");
    } finally {
      setBusy(false);
    }
  }

  async function simulateAnomaly(type) {
    if (!journey) return;
    setSimulating(true);
    setError("");
    try {
      const data = await journeysApi.simulateAnomaly(token, journey.id, type);
      setOpenAnomalies((prev) => {
        const next = prev.filter((a) => a.id !== data.anomaly.id);
        return [data.anomaly, ...next];
      });
      if (data.active_safety_check) setSafetyCheck(data.active_safety_check);
      setStatusMsg(data.message || "Simulated anomaly created.");
    } catch (err) {
      setError(err.message || "Simulate failed.");
    } finally {
      setSimulating(false);
    }
  }

  async function handleSafe() {
    if (!safetyCheck) return;
    setBusy(true);
    setError("");
    try {
      const data = await safetyApi.respond(token, safetyCheck.id, {
        response: "safe",
      });
      setSafetyCheck(null);
      setOpenAnomalies([]);
      setJourney(data.journey);
      setStatusMsg("Verified safe — journey continues.");
    } catch (err) {
      setError(err.message || "Could not confirm safety.");
    } finally {
      setBusy(false);
    }
  }

  async function handleNeedHelp() {
    if (!safetyCheck) return;
    setBusy(true);
    setError("");
    try {
      const payload = {
        response: "need_help",
        ...(position ? { lat: position.lat, lng: position.lng } : {}),
      };
      const data = await safetyApi.respond(token, safetyCheck.id, payload);
      setSafetyCheck(null);
      setOpenAnomalies([]);
      setJourney(data.journey);
      setSosAlert(data.sos);
      setStatusMsg(
        contactNotifyMessage(
          data.notifications,
          "Help requested — SOS sent to emergency contacts"
        )
      );
    } catch (err) {
      setError(err.message || "Could not request help.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancelCountdown() {
    if (!safetyCheck) return;
    setBusy(true);
    setError("");
    try {
      const data = await safetyApi.cancelCountdown(token, safetyCheck.id);
      setSafetyCheck(null);
      setOpenAnomalies([]);
      setJourney(data.journey);
      setStatusMsg("Countdown cancelled — marked safe.");
    } catch (err) {
      setError(err.message || "Could not cancel countdown.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSafetyTimeout() {
    if (!safetyCheck || busy) return;
    setBusy(true);
    setError("");
    try {
      const payload = position
        ? { lat: position.lat, lng: position.lng }
        : {};
      const data = await safetyApi.timeout(token, safetyCheck.id, payload);
      setSafetyCheck(null);
      setOpenAnomalies([]);
      setJourney(data.journey);
      setSosAlert(data.sos);
      setStatusMsg(
        contactNotifyMessage(
          data.notifications,
          "Automatic SOS — no response to safety check"
        )
      );
    } catch (err) {
      if (!String(err.message || "").includes("already")) {
        setError(err.message || "Timeout handling failed.");
      }
      setSafetyCheck(null);
    } finally {
      setBusy(false);
    }
  }

  const mapPosition =
    position ||
    (logs.length
      ? { lat: logs[logs.length - 1].lat, lng: logs[logs.length - 1].lng }
      : null);

  const destination =
    journey?.dest_lat != null && journey?.dest_lng != null
      ? {
          lat: journey.dest_lat,
          lng: journey.dest_lng,
          label: journey.dest_label,
        }
      : null;

  const startPoint =
    journey?.start_lat != null && journey?.start_lng != null
      ? { lat: journey.start_lat, lng: journey.start_lng }
      : null;

  return (
    <main
      className={`journey-page journey-live ${inProgress ? "" : "journey-planning"}`}
    >
      {safetyCheck?.status === "pending" && (
        <SafetyModal
          safetyCheck={safetyCheck}
          busy={busy}
          onSafe={handleSafe}
          onNeedHelp={handleNeedHelp}
          onCancelCountdown={handleCancelCountdown}
          onTimeout={handleSafetyTimeout}
        />
      )}

      {!inProgress ? (
        <SafeRoutePlanner
          token={token}
          busy={busy}
          onStartJourney={startJourneyFromPlanner}
          startError={error}
        />
      ) : (
        <section className="journey-map-layout">
          <div className="map-stage">
            <JourneyMap
              key={journey.id}
              position={mapPosition}
              path={logs}
              destination={destination}
              start={startPoint}
              followMode={followMode}
              status={journey.status}
              expectedRoute={journey.expected_route}
            />

            <div className="map-overlay-top">
              <div className="map-chip">
                <span className={`status-pill status-${journey.status}`}>
                  {journey.status}
                </span>
                <strong>{journey.dest_label}</strong>
              </div>
              <button
                type="button"
                className="sos-btn sos-btn-compact"
                onClick={triggerSos}
                disabled={busy || journey.status === "sos"}
              >
                SOS
              </button>
            </div>

            <JourneyBottomSheet
              journey={journey}
              monitoring={monitoring}
              openAnomalies={openAnomalies}
              safetyCheck={safetyCheck}
              sosAlert={sosAlert}
              serverCount={serverCount}
              shareUrl={shareUrl}
              shareCopied={shareCopied}
              copyShareLink={copyShareLink}
              mapPosition={mapPosition}
              position={position}
              error={error}
              geoError={geoError}
              statusMsg={statusMsg}
              offlinePending={offlinePending}
              permissionState={permissionState}
              intervalSec={intervalSec}
              followMode={followMode}
              setFollowMode={setFollowMode}
              triggerSos={triggerSos}
              runAction={runAction}
              simulateAnomaly={simulateAnomaly}
              simulating={simulating}
              busy={busy}
            />
          </div>
        </section>
      )}
    </main>
  );
}

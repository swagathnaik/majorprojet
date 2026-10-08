import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { journeysApi, mapsApi, safetyApi } from "../api/client";
import { useGeolocation } from "../hooks/useGeolocation";
import JourneyMap from "../components/JourneyMap";
import MonitoringPanel from "../components/MonitoringPanel";
import AnomalyBanner from "../components/AnomalyBanner";
import SafetyModal from "../components/SafetyModal";
import SafeRoutePlanner from "../components/SafeRoutePlanner";
import JourneyBottomSheet from "../components/JourneyBottomSheet";
import PostJourneyFeedbackModal from "../components/PostJourneyFeedbackModal";

import {
  clearOfflineQueue,
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
  const cloudFailed = notifications.some((n) => {
    const channels = n.delivery?.channels || [];
    return (
      channels.some((ch) => String(ch).includes("failed")) ||
      !n.delivery?.whatsapp_sent
    );
  });
  let msg = fallback;
  if (names.length) {
    msg = `${fallback} to ${names.join(", ")}.`;
  } else {
    msg = `${fallback} (${notifications.length} contact(s)).`;
  }
  if (cloudFailed) {
    msg += " (Cloud gateway expired or unprovisioned — tap 📲 Send WhatsApp below for instant 1-click delivery).";
  }
  return msg;
}

/**
 * Full Safe Journey pipeline:
 * start → GPS + auto-share → monitor → anomaly → "Are you safe?" → SOS → contact / 112
 */
export default function Journey() {
  const { token } = useAuth();
  const [journey, setJourney] = useState(null);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [endedJourneyData, setEndedJourneyData] = useState(null);
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
    enabled: isLive || journey?.status === "paused" || journey?.status === "sos",
  });

  const positionRef = useRef(position);
  useEffect(() => {
    positionRef.current = position;
  }, [position]);

  const journeyId = journey?.id;
  const journeyStatus = journey?.status;

  function applyMonitoringPayload(data) {
    if (data.monitoring) setMonitoring(data.monitoring);
    if (data.open_anomalies) setOpenAnomalies(data.open_anomalies);
    if ("active_safety_check" in data) setSafetyCheck(data.active_safety_check);
    if (data.journey && data.journey.status === "sos") {
      setJourney((prev) => (prev?.status === "sos" ? prev : data.journey));
    }
    if (data.sos) {
      setSosAlert(data.sos);
    }
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
    const timer = setInterval(() => {
      if (pendingOfflineCount() > 0) {
        flush();
      }
    }, 5000);
    window.addEventListener("online", flush);
    return () => {
      clearInterval(timer);
      window.removeEventListener("online", flush);
    };
  }, [token, refreshActive]);

  useEffect(() => {
    if (!inProgress || !journeyId) return undefined;
    let cancelled = false;

    async function tick() {
      try {
        const mon = await journeysApi.monitoring(token, journeyId);
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
  }, [inProgress, journeyId, token]);


  useEffect(() => {
    if ((!isLive && journeyStatus !== "sos") || !journeyId) return;

    const intervalMs = intervalSec * 1000;

    async function sendIfDue() {
      const pos = positionRef.current;
      if (!pos || pos.lat == null || pos.lng == null) return;

      const now = Date.now();
      if (now - lastSentAtRef.current < intervalMs - 200) return;
      lastSentAtRef.current = now;
      try {
        if (!navigator.onLine) {
          enqueueOffline({
            kind: "location",
            journeyId: journeyId,
            payload: pos,
          });
          setOfflinePending(pendingOfflineCount());
          setStatusMsg("Offline — location queued for sync.");
          return;
        }
        const data = await journeysApi.postLocation(token, journeyId, pos);
        setStatusMsg(`Location synced · ${new Date().toLocaleTimeString()}`);
        if (data.interval_sec) setIntervalSec(data.interval_sec);
        setLogs((prev) => [...prev, data.location].slice(-200));
        setServerCount((c) => c + 1);
        applyMonitoringPayload(data);
        setError("");
      } catch (err) {
        const msg = (err?.message || "").toLowerCase();
        if (msg.includes("not found") || (msg.includes("active journey") && journeyStatus !== "sos")) {
          // Journey ended or is no longer active on server
          setJourney((prev) => (prev ? { ...prev, status: "completed" } : null));
          refreshActive();
          return;
        }
        enqueueOffline({
          kind: "location",
          journeyId: journeyId,
          payload: pos,
        });
        setOfflinePending(pendingOfflineCount());
        setError(err.message || "Failed to upload location — queued offline.");
      }
    }

    sendIfDue();
    const id = setInterval(sendIfDue, intervalMs);
    return () => clearInterval(id);
  }, [isLive, journeyStatus, journeyId, token, intervalSec, refreshActive]);

  function sendBrowserNotification(title, options) {
    try {
      if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
        new Notification(title, options);
      }
    } catch {
      /* Ignore browser notification errors */
    }
  }

  async function startJourneyFromPlanner(payload) {
    setBusy(true);
    setError("");
    setStatusMsg("");
    setSosAlert(null);
    setShareCopied(false);
    if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().catch(() => { });
    }
    try {
      const data = await journeysApi.start(token, payload);
      setJourney(data.journey);
      setShareUrl(data.share?.share_url || data.journey?.share_url || "");
      clearOfflineQueue();
      setOfflinePending(0);
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
      if (action === "end") {
        setEndedJourneyData(data.journey);
        setShowFeedbackModal(true);
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
      sendBrowserNotification("🚨 SafeRoute SOS Triggered", {
        body: "Emergency SOS activated. Trusted contacts have been automatically notified.",
        tag: "sos_alert",
      });
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
      if (data.journey) setJourney(data.journey);
      if (data.sos) {
        setSosAlert(data.sos);
        sendBrowserNotification("🚨 Emergency SOS Triggered", {
          body: `Automatic SOS activated for simulated ${type}.`,
          tag: "sos_alert",
        });
      }
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
      sendBrowserNotification("🚨 Emergency Help Requested", {
        body: "SOS alert sent to emergency contacts.",
        tag: "sos_alert",
      });
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
    const checkIdToTimeout = safetyCheck.id;
    try {
      const payload = position
        ? { lat: position.lat, lng: position.lng }
        : {};
      const data = await safetyApi.timeout(token, checkIdToTimeout, payload);
      setSafetyCheck(null);
      setOpenAnomalies([]);
      if (data.journey) setJourney(data.journey);
      if (data.sos) setSosAlert(data.sos);
      sendBrowserNotification("🚨 Automatic SOS Triggered", {
        body: "No response to safety check. Automatic SOS alert sent to trusted contacts.",
        tag: "sos_alert",
      });
      setStatusMsg(
        contactNotifyMessage(
          data.notifications,
          "Automatic SOS — no response to safety check"
        )
      );
    } catch (err) {
      try {
        const mon = await journeysApi.monitoring(token, journey.id);
        applyMonitoringPayload(mon);
      } catch {
        /* ignore */
      }
      setSafetyCheck(null);
    } finally {
      setBusy(false);
    }
  }

  const mapPosition = useMemo(() => {
    if (position?.lat != null && position?.lng != null) return position;
    if (logs.length) {
      const last = logs[logs.length - 1];
      return { lat: last.lat, lng: last.lng };
    }
    return null;
  }, [position?.lat, position?.lng, logs]);

  const destination = useMemo(() => {
    if (journey?.dest_lat == null || journey?.dest_lng == null) return null;
    return {
      lat: journey.dest_lat,
      lng: journey.dest_lng,
      label: journey.dest_label,
    };
  }, [journey?.dest_lat, journey?.dest_lng, journey?.dest_label]);

  const startPoint = useMemo(() => {
    if (journey?.start_lat == null || journey?.start_lng == null) return null;
    return { lat: journey.start_lat, lng: journey.start_lng };
  }, [journey?.start_lat, journey?.start_lng]);

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

      {showFeedbackModal && (
        <PostJourneyFeedbackModal
          isOpen={showFeedbackModal}
          onClose={() => {
            setShowFeedbackModal(false);
            setEndedJourneyData(null);
          }}
          journey={endedJourneyData || journey}
          token={token}
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
              onClearOffline={() => {
                clearOfflineQueue();
                setOfflinePending(0);
              }}
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

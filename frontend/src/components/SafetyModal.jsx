/**
 * Phase 9 – "Are you safe?" modal with response window + SOS countdown.
 */
import { useEffect, useRef, useState } from "react";

const TYPE_LABELS = {
  prolonged_stop: "Prolonged inactivity",
  route_deviation: "Route deviation",
  lost_signal: "Lost location signal",
  speed_spike: "Sudden speed change",
};

export default function SafetyModal({
  safetyCheck,
  busy = false,
  onSafe,
  onNeedHelp,
  onTimeout,
  onCancelCountdown,
}) {
  const [phase, setPhase] = useState("ask"); // ask | countdown
  const [secondsLeft, setSecondsLeft] = useState(0);
  const timedOutRef = useRef(false);
  const phaseRef = useRef("ask");
  const currentCheckIdRef = useRef(null);

  const responseWindow = safetyCheck?.response_window_sec ?? 40;
  const countdownSec = safetyCheck?.countdown_seconds ?? 20;
  const anomalyType = safetyCheck?.anomaly?.type;
  const checkId = safetyCheck?.id;

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  // Reset ONLY when a genuinely new safety check ID appears
  useEffect(() => {
    if (!safetyCheck || safetyCheck.status !== "pending") {
      currentCheckIdRef.current = null;
      return;
    }

    if (currentCheckIdRef.current !== checkId) {
      currentCheckIdRef.current = checkId;
      timedOutRef.current = false;
      setPhase("ask");
      phaseRef.current = "ask";
      const remaining = Math.max(
        1,
        safetyCheck.response_deadline_sec ?? responseWindow
      );
      setSecondsLeft(remaining);
    }
  }, [checkId, safetyCheck, responseWindow]);

  // Tick every second
  useEffect(() => {
    if (!safetyCheck || safetyCheck.status !== "pending" || busy) return undefined;

    const id = setInterval(() => {
      setSecondsLeft((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(id);
  }, [checkId, safetyCheck?.status, busy]);

  // Handle hitting zero
  useEffect(() => {
    if (!safetyCheck || safetyCheck.status !== "pending" || busy) return;
    if (secondsLeft > 0) return;

    if (phaseRef.current === "ask") {
      setPhase("countdown");
      phaseRef.current = "countdown";
      setSecondsLeft(countdownSec);
      return;
    }

    if (phaseRef.current === "countdown" && !timedOutRef.current) {
      timedOutRef.current = true;
      onTimeout?.();
    }
  }, [secondsLeft, safetyCheck?.status, busy, countdownSec, onTimeout]);

  if (!safetyCheck || safetyCheck.status !== "pending") return null;

  return (
    <div className="safety-modal-backdrop" role="dialog" aria-modal="true">
      <div className="safety-modal">
        <p className="eyebrow">Safety verification</p>
        <h2>Are you safe?</h2>
        <p className="safety-copy">
          We noticed unusual activity during your journey
          {anomalyType ? ` (${TYPE_LABELS[anomalyType] || anomalyType})` : ""}.
          Please confirm you are okay.
        </p>

        {phase === "ask" ? (
          <>
            <p className="safety-timer">
              Please respond within <strong>{secondsLeft}s</strong>
            </p>
            <div className="safety-actions">
              <button
                type="button"
                className="btn btn-safe"
                disabled={busy}
                onClick={onSafe}
              >
                YES, I&apos;M SAFE
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={busy}
                onClick={onNeedHelp}
              >
                I NEED HELP
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="countdown-ring" aria-live="assertive">
              <span>{secondsLeft}</span>
            </div>
            <p className="safety-copy">
              No response yet. Automatic SOS in <strong>{secondsLeft}</strong>{" "}
              seconds unless you cancel.
            </p>
            <div className="safety-actions">
              <button
                type="button"
                className="btn btn-safe"
                disabled={busy}
                onClick={onCancelCountdown}
              >
                Cancel — I&apos;m safe
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={busy}
                onClick={onNeedHelp}
              >
                I NEED HELP
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Browser Geolocation hook for SafeRoute.
 *
 * Limitations (document for viva):
 * - Requires HTTPS or localhost
 * - Tracking is unreliable when the browser tab is backgrounded/closed
 * - A native app (Flutter) would be better for background GPS later
 */
import { useCallback, useEffect, useRef, useState } from "react";

const defaultOptions = {
  enableHighAccuracy: true,
  maximumAge: 5000,
  timeout: 15000,
};

export function useGeolocation({ enabled = false, options = defaultOptions } = {}) {
  const [position, setPosition] = useState(null);
  const [error, setError] = useState(null);
  const [permissionState, setPermissionState] = useState("prompt"); // prompt|granted|denied|unsupported
  const watchIdRef = useRef(null);

  const clearWatch = useCallback(() => {
    if (watchIdRef.current != null && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
  }, []);

  const requestOnce = useCallback(() => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        const err = new Error("Geolocation is not supported by this browser.");
        setPermissionState("unsupported");
        setError(err.message);
        reject(err);
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const next = mapPosition(pos);
          setPosition(next);
          setError(null);
          setPermissionState("granted");
          resolve(next);
        },
        (geoError) => {
          const message = geoErrorMessage(geoError);
          setError(message);
          if (geoError.code === geoError.PERMISSION_DENIED) {
            setPermissionState("denied");
          }
          reject(new Error(message));
        },
        { ...defaultOptions, ...options }
      );
    });
  }, [options]);

  useEffect(() => {
    if (!enabled) {
      clearWatch();
      return;
    }

    if (!navigator.geolocation) {
      setPermissionState("unsupported");
      setError("Geolocation is not supported by this browser.");
      return;
    }

    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setPosition(mapPosition(pos));
        setError(null);
        setPermissionState("granted");
      },
      (geoError) => {
        setError(geoErrorMessage(geoError));
        if (geoError.code === geoError.PERMISSION_DENIED) {
          setPermissionState("denied");
        }
      },
      { ...defaultOptions, ...options }
    );

    return clearWatch;
  }, [enabled, options, clearWatch]);

  return {
    position,
    error,
    permissionState,
    supported: typeof navigator !== "undefined" && Boolean(navigator.geolocation),
    requestOnce,
    clearWatch,
  };
}

function mapPosition(pos) {
  const { latitude, longitude, accuracy, speed, heading } = pos.coords;
  return {
    lat: latitude,
    lng: longitude,
    accuracy: accuracy ?? null,
    // Browser speed is m/s; may be null when stationary
    speed: speed != null && !Number.isNaN(speed) ? speed : null,
    heading: heading != null && !Number.isNaN(heading) ? heading : null,
    recorded_at: new Date(pos.timestamp).toISOString(),
  };
}

function geoErrorMessage(err) {
  switch (err.code) {
    case err.PERMISSION_DENIED:
      return "Location permission denied. Allow location access for SafeRoute.";
    case err.POSITION_UNAVAILABLE:
      return "Location unavailable. Check GPS / network settings.";
    case err.TIMEOUT:
      return "Location request timed out. Try again.";
    default:
      return err.message || "Unable to get location.";
  }
}

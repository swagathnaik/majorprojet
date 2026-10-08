/**
 * Browser Geolocation hook for SafeRoute with robust multi-layer fallback.
 *
 * Layer 1: High-accuracy GPS (smartphones, GPS hardware)
 * Layer 2: Standard-accuracy Wi-Fi/Cell positioning (laptops, PCs, desktops)
 * Layer 3: Network IP-based geolocation (/api/maps/ip-location or geojs)
 * Layer 4: Landmark fallback (Soladevanahalli / Bengaluru campus)
 */
import { useCallback, useEffect, useRef, useState } from "react";

const FALLBACK_DEFAULT = {
  lat: 13.0837,
  lng: 77.4857,
  accuracy: 1000,
  speed: null,
  heading: null,
  label: "Acharya Institutes, Soladevanahalli, Bengaluru",
  source: "default_fallback",
  recorded_at: new Date().toISOString(),
};

export function useGeolocation({ enabled = false } = {}) {
  const [position, setPosition] = useState(null);
  const [error, setError] = useState(null);
  const [permissionState, setPermissionState] = useState("prompt"); // prompt|granted|denied|unsupported|approximate
  const [isLocating, setIsLocating] = useState(false);
  const watchIdRef = useRef(null);

  const clearWatch = useCallback(() => {
    if (watchIdRef.current != null && typeof navigator !== "undefined" && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
  }, []);

  const fetchIpFallback = useCallback(async () => {
    try {
      const res = await fetch("/api/maps/ip-location");
      if (res.ok) {
        const data = await res.json();
        if (data.lat && data.lng) {
          const approx = {
            lat: data.lat,
            lng: data.lng,
            accuracy: 5000,
            speed: null,
            heading: null,
            label: data.label || "Current Area",
            source: data.source || "ip",
            recorded_at: new Date().toISOString(),
          };
          setPosition(approx);
          setPermissionState("approximate");
          return approx;
        }
      }
    } catch {
      // ignore
    }

    try {
      const res = await fetch("https://get.geojs.io/v1/ip/geo.json");
      if (res.ok) {
        const data = await res.json();
        if (data.latitude && data.longitude) {
          const approx = {
            lat: parseFloat(data.latitude),
            lng: parseFloat(data.longitude),
            accuracy: 5000,
            speed: null,
            heading: null,
            label: `${data.city || "Bengaluru"}, ${data.region || "Karnataka"}`,
            source: "ip",
            recorded_at: new Date().toISOString(),
          };
          setPosition(approx);
          setPermissionState("approximate");
          return approx;
        }
      }
    } catch {
      // ignore
    }

    setPosition(FALLBACK_DEFAULT);
    setPermissionState("approximate");
    return FALLBACK_DEFAULT;
  }, []);

  const requestOnce = useCallback(async () => {
    setIsLocating(true);
    setError(null);

    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setPermissionState("unsupported");
      const fallback = await fetchIpFallback();
      setIsLocating(false);
      return fallback;
    }

    // Step 1: Try high accuracy (allowing fresh cached positions up to 60s)
    const tryHigh = () =>
      new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          (pos) => resolve(mapPosition(pos)),
          (err) => reject(err),
          { enableHighAccuracy: true, timeout: 6000, maximumAge: 60000 }
        );
      });

    // Step 2: Try low accuracy (Wi-Fi / ISP / network triangulation)
    const tryLow = () =>
      new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          (pos) => resolve(mapPosition(pos)),
          (err) => reject(err),
          { enableHighAccuracy: false, timeout: 6000, maximumAge: 120000 }
        );
      });

    try {
      const pos = await tryHigh();
      setPosition(pos);
      setError(null);
      setPermissionState("granted");
      setIsLocating(false);
      return pos;
    } catch {
      // High accuracy timed out or unavailable, try low accuracy
      try {
        const pos = await tryLow();
        setPosition(pos);
        setError(null);
        setPermissionState("granted");
        setIsLocating(false);
        return pos;
      } catch (lowErr) {
        // Step 3: Browser geolocation failed (e.g. desktop with no GPS or permission denied)
        const msg = geoErrorMessage(lowErr);
        if (lowErr.code === lowErr.PERMISSION_DENIED) {
          setPermissionState("denied");
        }
        const fallback = await fetchIpFallback();
        setError(`${msg} Using approximate area.`);
        setIsLocating(false);
        return fallback;
      }
    }
  }, [fetchIpFallback]);

  const prevSampleRef = useRef(null);

  // Handle active watching when enabled
  useEffect(() => {
    if (!enabled) {
      clearWatch();
      return undefined;
    }

    if (typeof navigator === "undefined" || !navigator.geolocation) {
      fetchIpFallback();
      return undefined;
    }

    // Initial position fetch
    requestOnce().catch(() => { });

    // Start watchPosition with high accuracy for mobile/GPS devices
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const mapped = mapPositionWithDerivation(pos, prevSampleRef.current);
        prevSampleRef.current = {
          lat: mapped.lat,
          lng: mapped.lng,
          timestamp: pos.timestamp || Date.now(),
        };
        setPosition(mapped);
        setError(null);
        setPermissionState("granted");
      },
      (geoError) => {
        // If watchPosition encounters error, don't wipe existing position
        if (geoError.code === geoError.PERMISSION_DENIED) {
          setPermissionState("denied");
          setError(geoErrorMessage(geoError));
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 3000 }
    );

    return clearWatch;
  }, [enabled, clearWatch, requestOnce, fetchIpFallback]);

  const setManualPosition = useCallback((coords) => {
    if (!coords || coords.lat == null || coords.lng == null) return;
    setPosition({
      lat: coords.lat,
      lng: coords.lng,
      accuracy: 10,
      speed: null,
      heading: null,
      label: coords.label || "Selected location",
      source: "manual",
      recorded_at: new Date().toISOString(),
    });
    setError(null);
  }, []);

  return {
    position,
    error,
    permissionState,
    isLocating,
    supported: typeof navigator !== "undefined" && Boolean(navigator.geolocation),
    requestOnce,
    clearWatch,
    setManualPosition,
  };
}

function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function bearingDeg(lat1, lon1, lat2, lon2) {
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(dLon) * Math.cos((lat2 * Math.PI) / 180);
  const x =
    Math.cos((lat1 * Math.PI) / 180) * Math.sin((lat2 * Math.PI) / 180) -
    Math.sin((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.cos(dLon);
  return (Math.atan2(y, x) * (180 / Math.PI) + 360) % 360;
}

function mapPositionWithDerivation(pos, prev) {
  const { latitude, longitude, accuracy, speed, heading } = pos.coords;
  let finalSpeed = speed != null && !Number.isNaN(speed) && speed >= 0 ? speed : null;
  let finalHeading = heading != null && !Number.isNaN(heading) && heading >= 0 ? heading : null;

  if (prev && prev.lat != null && prev.lng != null) {
    const dt = ((pos.timestamp || Date.now()) - prev.timestamp) / 1000;
    if (dt >= 0.8) {
      const dist = haversineM(prev.lat, prev.lng, latitude, longitude);
      if (finalSpeed == null) {
        finalSpeed = dist < 2.0 ? 0 : dist / dt;
      }
      if (finalHeading == null && dist >= 3.0) {
        finalHeading = bearingDeg(prev.lat, prev.lng, latitude, longitude);
      }
    }
  }

  return {
    lat: latitude,
    lng: longitude,
    accuracy: accuracy ?? null,
    speed: finalSpeed,
    heading: finalHeading,
    source: "gps",
    recorded_at: new Date(pos.timestamp || Date.now()).toISOString(),
  };
}

function mapPosition(pos) {
  return mapPositionWithDerivation(pos, null);
}

function geoErrorMessage(err) {
  switch (err.code) {
    case err.PERMISSION_DENIED:
      return "Location permission denied.";
    case err.POSITION_UNAVAILABLE:
      return "GPS / Wi-Fi position unavailable.";
    case err.TIMEOUT:
      return "Location request timed out.";
    default:
      return err.message || "Unable to get GPS.";
  }
}

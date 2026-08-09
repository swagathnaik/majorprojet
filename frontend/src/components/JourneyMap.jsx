/**
 * Live journey map – Leaflet + OpenStreetMap-style tiles (Carto Voyager).
 * Shows planned safer path + live GPS trail.
 */
import { useEffect, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Polyline,
  Circle,
  Popup,
  ZoomControl,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const DEFAULT_CENTER = [12.9716, 77.5946];
const DEFAULT_ZOOM = 16;

function userIcon(isDeviated = false) {
  return L.divIcon({
    className: `sr-user-marker ${isDeviated ? "sr-user-marker-deviated" : ""}`,
    html: `
      <div class="sr-user-dot-wrap">
        <div class="sr-user-pulse"></div>
        <div class="sr-user-dot"></div>
      </div>
    `,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function destIcon() {
  return L.divIcon({
    className: "sr-dest-marker",
    html: `
      <div class="sr-dest-pin">
        <span></span>
      </div>
    `,
    iconSize: [28, 40],
    iconAnchor: [14, 40],
  });
}

function startIcon() {
  return L.divIcon({
    className: "sr-start-marker",
    html: `<div class="sr-start-dot"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

function MapResizer() {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 100);
    const handleResize = () => map.invalidateSize();
    window.addEventListener("resize", handleResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", handleResize);
    };
  }, [map]);
  return null;
}

function FollowUser({ position, followMode }) {
  const map = useMap();
  useEffect(() => {
    if (followMode && position?.lat != null && position?.lng != null) {
      map.panTo([position.lat, position.lng], { animate: true });
    }
  }, [map, position, followMode]);
  return null;
}

function FitJourney({ points, dest, user, planned }) {
  const map = useMap();
  useEffect(() => {
    const coords = [];
    (planned || []).forEach((p) => coords.push(p));
    points.forEach((p) => coords.push([p.lat, p.lng]));
    if (user?.lat != null) coords.push([user.lat, user.lng]);
    if (dest?.lat != null) coords.push([dest.lat, dest.lng]);
    if (coords.length >= 2) {
      map.fitBounds(coords, { padding: [48, 48], maxZoom: 17 });
    } else if (coords.length === 1) {
      map.setView(coords[0], DEFAULT_ZOOM);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);
  return null;
}

function plannedLatLng(expectedRoute) {
  if (!expectedRoute?.coordinates?.length) return [];
  return expectedRoute.coordinates.map((c) => [c[1], c[0]]);
}

export default function JourneyMap({
  position,
  path = [],
  destination = null,
  start = null,
  followMode = true,
  status = "active",
  expectedRoute = null,
  openAnomalies = [],
  monitoring = null,
  isDeviated: isDeviatedProp = false,
}) {
  const isDeviated =
    isDeviatedProp ||
    status === "sos" ||
    openAnomalies?.some((a) => a.type === "route_deviation") ||
    (monitoring?.deviation_m != null && monitoring.deviation_m >= 40);

  const center = useMemo(() => {
    if (position?.lat != null) return [position.lat, position.lng];
    if (path.length) return [path[path.length - 1].lat, path[path.length - 1].lng];
    if (start?.lat != null) return [start.lat, start.lng];
    return DEFAULT_CENTER;
  }, [position, path, start]);

  const linePositions = useMemo(
    () => path.map((p) => [p.lat, p.lng]),
    [path]
  );

  const planned = useMemo(
    () => plannedLatLng(expectedRoute),
    [expectedRoute]
  );

  const deviationConnector = useMemo(() => {
    if (!isDeviated || position?.lat == null || !planned.length) return null;
    const lastPlanned = planned[planned.length - 1] || planned[0];
    return [lastPlanned, [position.lat, position.lng]];
  }, [isDeviated, position, planned]);

  const accuracy =
    position?.accuracy != null && position.accuracy > 0
      ? Math.min(position.accuracy, 200)
      : null;

  return (
    <div className={`journey-map-shell status-map-${status} ${isDeviated ? "map-deviated" : ""}`}>
      <MapContainer
        center={center}
        zoom={DEFAULT_ZOOM}
        className="journey-map"
        zoomControl={false}
        attributionControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={20}
        />
        <ZoomControl position="bottomright" />
        <MapResizer />

        <FollowUser position={position} followMode={followMode} />
        <FitJourney
          points={path}
          dest={destination}
          user={position || start}
          planned={planned}
        />

        {/* Planned Route (Dashed Blue) */}
        {planned.length >= 2 && (
          <Polyline
            positions={planned}
            pathOptions={{
              color: "#1a73e8",
              weight: 6,
              opacity: 0.55,
              lineJoin: "round",
              lineCap: "round",
              dashArray: "10 8",
            }}
          />
        )}

        {/* Outer Red Glow Stroke when Deviated */}
        {linePositions.length >= 2 && isDeviated && (
          <Polyline
            positions={linePositions}
            pathOptions={{
              color: "#ef4444",
              weight: 12,
              opacity: 0.35,
              lineJoin: "round",
              lineCap: "round",
            }}
          />
        )}

        {/* Traveled Path Polyline (Green when normal, Bold Red #dc2626 when deviated) */}
        {linePositions.length >= 2 && (
          <Polyline
            positions={linePositions}
            pathOptions={{
              color: isDeviated ? "#dc2626" : "#34a853",
              weight: isDeviated ? 6 : 5,
              opacity: 0.95,
              lineJoin: "round",
              lineCap: "round",
            }}
          />
        )}

        {/* Off-Route Deviation Connector Line (Dashed Red) */}
        {deviationConnector && (
          <Polyline
            positions={deviationConnector}
            pathOptions={{
              color: "#dc2626",
              weight: 5,
              opacity: 0.9,
              dashArray: "8 8",
            }}
          />
        )}

        {start?.lat != null && start?.lng != null && (
          <Marker position={[start.lat, start.lng]} icon={startIcon()}>
            <Popup>Start</Popup>
          </Marker>
        )}

        {destination?.lat != null && destination?.lng != null && (
          <Marker
            position={[destination.lat, destination.lng]}
            icon={destIcon()}
          >
            <Popup>{destination.label || "Destination"}</Popup>
          </Marker>
        )}

        {position?.lat != null && position?.lng != null && (
          <>
            {accuracy != null && (
              <Circle
                center={[position.lat, position.lng]}
                radius={accuracy}
                pathOptions={{
                  color: isDeviated ? "#dc2626" : "#1a73e8",
                  fillColor: isDeviated ? "#dc2626" : "#1a73e8",
                  fillOpacity: isDeviated ? 0.25 : 0.12,
                  weight: isDeviated ? 2 : 1,
                }}
              />
            )}
            <Marker position={[position.lat, position.lng]} icon={userIcon(isDeviated)}>
              <Popup>
                {isDeviated ? "🚨 Off-Route Deviation Active!" : "You are here"}
              </Popup>
            </Marker>
          </>
        )}
      </MapContainer>
    </div>
  );
}

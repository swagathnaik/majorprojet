/**
 * Google Maps–style planner map: heatmap, destination pin, scored safer routes.
 */
import { useEffect, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Polyline,
  Popup,
  ZoomControl,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";

const DEFAULT_CENTER = [12.9716, 77.5946];

function userIcon() {
  return L.divIcon({
    className: "sr-user-marker",
    html: `<div class="sr-user-dot-wrap"><div class="sr-user-pulse"></div><div class="sr-user-dot"></div></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function destIcon() {
  return L.divIcon({
    className: "sr-dest-marker",
    html: `<div class="sr-dest-pin"><span></span></div>`,
    iconSize: [28, 40],
    iconAnchor: [14, 40],
  });
}

function HeatLayer({ heat, enabled }) {
  const map = useMap();
  useEffect(() => {
    if (!enabled || !heat?.length) return undefined;
    const layer = L.heatLayer(heat, {
      radius: 28,
      blur: 22,
      maxZoom: 17,
      max: 1.0,
      minOpacity: 0.35,
      gradient: {
        0.2: "#34a853",
        0.45: "#fbbc04",
        0.7: "#ea8600",
        0.9: "#ea4335",
      },
    }).addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, heat, enabled]);
  return null;
}

function FitBounds({ origin, destination, routes, selectedId }) {
  const map = useMap();
  useEffect(() => {
    const latlngs = [];
    if (origin) latlngs.push([origin.lat, origin.lng]);
    if (destination) latlngs.push([destination.lat, destination.lng]);
    const selected = routes?.find((r) => r.id === selectedId);
    (selected?.geometry_latlng || []).forEach((p) => latlngs.push(p));
    if (latlngs.length >= 2) {
      map.fitBounds(latlngs, { padding: [80, 80], maxZoom: 15 });
    } else if (latlngs.length === 1) {
      map.setView(latlngs[0], 14);
    }
  }, [map, origin, destination, routes, selectedId]);
  return null;
}

function routeColor(route, selected) {
  if (!selected) return "#9aa0a6";
  if (route.is_recommended) return "#1a73e8";
  if (route.safety_score >= 75) return "#34a853";
  if (route.safety_score >= 50) return "#fbbc04";
  return "#ea4335";
}

export default function PlannerMap({
  origin,
  destination,
  routes = [],
  selectedRouteId = null,
  heat = [],
  showHeat = true,
  onSelectRoute,
}) {
  const center = useMemo(() => {
    if (origin) return [origin.lat, origin.lng];
    return DEFAULT_CENTER;
  }, [origin]);

  return (
    <div className="planner-map-shell">
      <MapContainer
        center={center}
        zoom={13}
        className="planner-map"
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; OSM &copy; CARTO'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={20}
        />
        <ZoomControl position="bottomright" />
        <HeatLayer heat={heat} enabled={showHeat} />
        <FitBounds
          origin={origin}
          destination={destination}
          routes={routes}
          selectedId={selectedRouteId}
        />

        {routes.map((route) => {
          const selected = route.id === selectedRouteId;
          return (
            <Polyline
              key={route.id}
              positions={route.geometry_latlng}
              pathOptions={{
                color: routeColor(route, selected),
                weight: selected ? 7 : 4,
                opacity: selected ? 0.95 : 0.4,
                lineCap: "round",
                lineJoin: "round",
              }}
              eventHandlers={{
                click: () => onSelectRoute?.(route.id),
              }}
            />
          );
        })}

        {origin && (
          <Marker position={[origin.lat, origin.lng]} icon={userIcon()}>
            <Popup>Your location</Popup>
          </Marker>
        )}
        {destination && (
          <Marker
            position={[destination.lat, destination.lng]}
            icon={destIcon()}
          >
            <Popup>{destination.label || "Destination"}</Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}

/**
 * Google Maps–style planner map using mapcn (MapLibre GL JS).
 * Renders crime heatmap, destination pin, user location, and scored safer routes.
 */
import { useEffect, useMemo } from "react";
import {
  Map,
  MapControls,
  MapMarker,
  MarkerContent,
  MapRoute,
  MapHeatLayer,
  useMap,
} from "./ui/map";

const DEFAULT_CENTER = [77.5946, 12.9716]; // [lng, lat]

function FitBounds({ origin, destination, routes, selectedId }) {
  const { map, isLoaded } = useMap();

  useEffect(() => {
    if (!isLoaded || !map) return;

    const coords = [];
    if (origin) coords.push([origin.lng, origin.lat]);
    if (destination) coords.push([destination.lng, destination.lat]);

    const selected = routes?.find((r) => r.id === selectedId);
    if (selected?.geometry_latlng?.length) {
      selected.geometry_latlng.forEach(([lat, lng]) => coords.push([lng, lat]));
    }

    if (coords.length >= 2) {
      let minLng = coords[0][0],
        maxLng = coords[0][0],
        minLat = coords[0][1],
        maxLat = coords[0][1];

      for (const [lng, lat] of coords) {
        if (lng < minLng) minLng = lng;
        if (lng > maxLng) maxLng = lng;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }

      map.fitBounds(
        [
          [minLng, minLat],
          [maxLng, maxLat],
        ],
        { padding: 80, maxZoom: 15, duration: 800 }
      );
    } else if (coords.length === 1) {
      map.flyTo({ center: coords[0], zoom: 14, duration: 800 });
    }
  }, [map, isLoaded, origin, destination, routes, selectedId]);

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
  onMapClick,
}) {
  const center = useMemo(() => {
    if (origin?.lat != null && origin?.lng != null) {
      return [origin.lng, origin.lat];
    }
    return DEFAULT_CENTER;
  }, [origin]);

  return (
    <div className="planner-map-shell">
      <Map center={center} zoom={13} className="planner-map" onClick={onMapClick}>
        <MapControls
          position="bottom-right"
          showZoom={true}
          showCompass={true}
          showLocate={false}
        />

        <MapHeatLayer heat={heat} enabled={showHeat} />

        <FitBounds
          origin={origin}
          destination={destination}
          routes={routes}
          selectedId={selectedRouteId}
        />

        {routes.map((route) => {
          const selected = route.id === selectedRouteId;
          const coords = (route.geometry_latlng || []).map(([lat, lng]) => [
            lng,
            lat,
          ]);
          return (
            <MapRoute
              key={route.id}
              id={`route-${route.id}`}
              coordinates={coords}
              color={routeColor(route, selected)}
              width={selected ? 7 : 4}
              opacity={selected ? 0.95 : 0.4}
              onClick={() => onSelectRoute?.(route.id)}
            />
          );
        })}

        {origin && (
          <MapMarker longitude={origin.lng} latitude={origin.lat}>
            <MarkerContent>
              <div className="sr-user-dot-wrap">
                <div className="sr-user-pulse"></div>
                <div className="sr-user-dot"></div>
              </div>
            </MarkerContent>
          </MapMarker>
        )}

        {destination && (
          <MapMarker longitude={destination.lng} latitude={destination.lat}>
            <MarkerContent>
              <div className="sr-dest-pin">
                <span></span>
              </div>
            </MarkerContent>
          </MapMarker>
        )}
      </Map>
    </div>
  );
}


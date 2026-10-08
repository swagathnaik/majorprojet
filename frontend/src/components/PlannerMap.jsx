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

    const selected = routes?.find((r) => r.id === selectedId) || routes?.[0];
    if (selected?.coordinates?.length) {
      selected.coordinates.forEach((pt) => coords.push(pt));
    } else if (selected?.geometry_latlng?.length) {
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
  if (selected) {
    return "#2563eb"; // Google Maps vibrant navigation blue
  }
  return "rgba(96, 165, 250, 0.45)"; // Softer blue for alternative routes
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

  const effectiveSelectedId =
    selectedRouteId != null
      ? selectedRouteId
      : routes.find((r) => r.is_recommended)?.id ?? routes[0]?.id;

  const sortedRoutes = useMemo(() => {
    if (!routes || !routes.length) return [];
    return [...routes].sort((a, b) => {
      const aSel = String(a.id) === String(effectiveSelectedId) ? 1 : 0;
      const bSel = String(b.id) === String(effectiveSelectedId) ? 1 : 0;
      return aSel - bSel;
    });
  }, [routes, effectiveSelectedId]);

  const selectedRoute = useMemo(() => {
    return (
      routes.find((r) => String(r.id) === String(effectiveSelectedId)) ||
      routes[0] ||
      null
    );
  }, [routes, effectiveSelectedId]);

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

        {/* Outer casing line for selected route to give clean border */}
        {selectedRoute && (
          <MapRoute
            key={`casing-${selectedRoute.id}`}
            id={`route-casing-${selectedRoute.id}`}
            coordinates={
              selectedRoute.coordinates && selectedRoute.coordinates.length >= 2
                ? selectedRoute.coordinates
                : (selectedRoute.geometry_latlng || []).map(([lat, lng]) => [lng, lat])
            }
            color="#1d4ed8"
            width={10.5}
            opacity={0.65}
          />
        )}

        {sortedRoutes.map((route) => {
          const selected = String(route.id) === String(effectiveSelectedId);
          const coords =
            route.coordinates && route.coordinates.length >= 2
              ? route.coordinates
              : (route.geometry_latlng || []).map(([lat, lng]) => [
                lng,
                lat,
              ]);
          return (
            <MapRoute
              key={route.id}
              id={`route-${route.id}`}
              coordinates={coords}
              color={routeColor(route, selected)}
              width={selected ? 7.5 : 4.5}
              opacity={selected ? 1.0 : 0.45}
              interactive={true}
              onClick={() => onSelectRoute?.(route.id)}
            />
          );
        })}

        {origin && origin.lat != null && origin.lng != null && (
          <MapMarker
            longitude={origin.lng}
            latitude={origin.lat}
            anchor="center"
          >
            <MarkerContent>
              <div className="sr-user-dot-wrap">
                <div className="sr-user-pulse"></div>
                <div className="sr-user-dot"></div>
              </div>
            </MarkerContent>
          </MapMarker>
        )}

        {destination && destination.lat != null && destination.lng != null && (
          <MapMarker
            longitude={destination.lng}
            latitude={destination.lat}
            anchor="bottom"
          >
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


/**
 * Live journey map using mapcn (MapLibre GL JS).
 * Shows planned safer path + live GPS trail with smooth camera following.
 */
import { useEffect, useMemo } from "react";
import {
  Map,
  MapControls,
  MapMarker,
  MarkerContent,
  MapRoute,
  useMap,
} from "./ui/map";

const DEFAULT_CENTER = [77.5946, 12.9716]; // [lng, lat]
const DEFAULT_ZOOM = 16;

function FollowUser({ position, followMode }) {
  const { map, isLoaded } = useMap();

  useEffect(() => {
    if (isLoaded && map && followMode && position?.lat != null && position?.lng != null) {
      map.panTo([position.lng, position.lat], { duration: 500 });
    }
  }, [map, isLoaded, position, followMode]);

  return null;
}

function FitJourney({ points, dest, user, planned }) {
  const { map, isLoaded } = useMap();

  useEffect(() => {
    if (!isLoaded || !map) return;

    const coords = [];
    (planned || []).forEach((p) => coords.push(p));
    points.forEach((p) => coords.push([p.lng, p.lat]));
    if (user?.lat != null && user?.lng != null) coords.push([user.lng, user.lat]);
    if (dest?.lat != null && dest?.lng != null) coords.push([dest.lng, dest.lat]);

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
        { padding: 50, maxZoom: 17, duration: 800 }
      );
    } else if (coords.length === 1) {
      map.flyTo({ center: coords[0], zoom: DEFAULT_ZOOM, duration: 800 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, isLoaded]);

  return null;
}

function plannedLngLat(expectedRoute) {
  if (!expectedRoute?.coordinates?.length) return [];
  // expectedRoute coordinates in GeoJSON format are [lng, lat]
  return expectedRoute.coordinates;
}

export default function JourneyMap({
  position,
  path = [],
  destination = null,
  start = null,
  followMode = true,
  status = "active",
  expectedRoute = null,
}) {
  const center = useMemo(() => {
    if (position?.lat != null && position?.lng != null) {
      return [position.lng, position.lat];
    }
    if (path.length) {
      return [path[path.length - 1].lng, path[path.length - 1].lat];
    }
    if (start?.lat != null && start?.lng != null) {
      return [start.lng, start.lat];
    }
    return DEFAULT_CENTER;
  }, [position, path, start]);

  const linePositions = useMemo(
    () => path.map((p) => [p.lng, p.lat]),
    [path]
  );

  const planned = useMemo(
    () => plannedLngLat(expectedRoute),
    [expectedRoute]
  );

  return (
    <div className={`journey-map-shell status-map-${status}`}>
      <Map center={center} zoom={DEFAULT_ZOOM} className="journey-map">
        <MapControls
          position="bottom-right"
          showZoom={true}
          showCompass={true}
          showLocate={false}
        />

        <FollowUser position={position} followMode={followMode} />
        <FitJourney
          points={path}
          dest={destination}
          user={position || start}
          planned={planned}
        />

        {/* Planned safer route */}
        {planned.length >= 2 && (
          <MapRoute
            id="journey-planned-route"
            coordinates={planned}
            color="#1a73e8"
            width={6}
            opacity={0.55}
            dashArray={[2, 2]}
          />
        )}

        {/* Live traveled path trail */}
        {linePositions.length >= 2 && (
          <MapRoute
            id="journey-traveled-path"
            coordinates={linePositions}
            color="#34a853"
            width={5}
            opacity={0.95}
          />
        )}

        {/* Start Point Marker */}
        {start?.lat != null && start?.lng != null && (
          <MapMarker longitude={start.lng} latitude={start.lat}>
            <MarkerContent>
              <div className="sr-start-dot"></div>
            </MarkerContent>
          </MapMarker>
        )}

        {/* Destination Marker */}
        {destination?.lat != null && destination?.lng != null && (
          <MapMarker longitude={destination.lng} latitude={destination.lat}>
            <MarkerContent>
              <div className="sr-dest-pin">
                <span></span>
              </div>
            </MarkerContent>
          </MapMarker>
        )}

        {/* Live User Location Pulse */}
        {position?.lat != null && position?.lng != null && (
          <MapMarker longitude={position.lng} latitude={position.lat}>
            <MarkerContent>
              <div className="sr-user-dot-wrap">
                <div className="sr-user-pulse"></div>
                <div className="sr-user-dot"></div>
              </div>
            </MarkerContent>
          </MapMarker>
        )}
      </Map>
    </div>
  );
}


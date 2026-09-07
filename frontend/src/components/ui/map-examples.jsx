import { useEffect, useState } from "react";
import {
  Map,
  MapControls,
  MapMarker,
  MarkerContent,
  MarkerLabel,
  MapPopup,
  MapRoute,
} from "./map";
import { Button } from "./button";
import { Card } from "./card";
import { Loader2, Clock, Route } from "lucide-react";

/**
 * 1. Basic Map Example
 */
export function BasicMapExample() {
  return (
    <Card className="h-[420px] w-full p-0 overflow-hidden">
      <Map center={[-74.006, 40.7128]} zoom={12} />
    </Card>
  );
}

/**
 * 2. Map Controls Example
 */
export function MapControlsExample() {
  return (
    <Card className="h-[420px] w-full p-0 overflow-hidden">
      <Map center={[2.3522, 48.8566]} zoom={10}>
        <MapControls
          position="top-right"
          showZoom
          showCompass
          showLocate
          showFullscreen
        />
      </Map>
    </Card>
  );
}

/**
 * 3. Standalone Popup Example
 */
export function StandalonePopupExample() {
  const [showPopup, setShowPopup] = useState(true);

  return (
    <Card className="relative h-[420px] w-full p-0 overflow-hidden">
      <Map center={[-74.006, 40.7128]} zoom={13}>
        {showPopup && (
          <MapPopup
            longitude={-74.006}
            latitude={40.7128}
            onClose={() => setShowPopup(false)}
            closeButton
            focusAfterOpen={false}
            closeOnClick={false}
          >
            <div className="space-y-2">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">
                New York City
              </h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                The city that never sleeps. Population: 8.3 million
              </p>
              <Button
                size="sm"
                variant="outline"
                className="w-full mt-2"
                onClick={() => setShowPopup(false)}
              >
                Close
              </Button>
            </div>
          </MapPopup>
        )}
      </Map>

      {!showPopup && (
        <Button
          size="sm"
          className="absolute bottom-4 left-4 z-10"
          onClick={() => setShowPopup(true)}
        >
          Show Popup
        </Button>
      )}
    </Card>
  );
}

/**
 * 4. OSRM Driving Route Example
 */
const start = { name: "Amsterdam", lng: 4.9041, lat: 52.3676 };
const end = { name: "Rotterdam", lng: 4.4777, lat: 51.9244 };

function formatDuration(seconds) {
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins} min`;
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  return `${hours}h ${remainingMins}m`;
}

function formatDistance(meters) {
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

export function OsrmRouteExample() {
  const [routes, setRoutes] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchRoutes() {
      try {
        const response = await fetch(
          `https://router.project-osrm.org/route/v1/driving/${start.lng},${start.lat};${end.lng},${end.lat}?overview=full&geometries=geojson&alternatives=true`
        );
        const data = await response.json();

        if (data.routes?.length > 0) {
          const routeData = data.routes.map((route) => ({
            coordinates: route.geometry.coordinates,
            duration: route.duration,
            distance: route.distance,
          }));
          setRoutes(routeData);
        }
      } catch (error) {
        console.error("Failed to fetch routes:", error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchRoutes();
  }, []);

  const sortedRoutes = routes
    .map((route, index) => ({ route, index }))
    .sort((a, b) => {
      if (a.index === selectedIndex) return 1;
      if (b.index === selectedIndex) return -1;
      return 0;
    });

  return (
    <Card className="h-[500px] w-full relative p-0 overflow-hidden">
      <Map center={[4.69, 52.14]} zoom={8.5}>
        {sortedRoutes.map(({ route, index }) => {
          const isSelected = index === selectedIndex;
          return (
            <MapRoute
              key={index}
              coordinates={route.coordinates}
              color={isSelected ? "#6366f1" : "#94a3b8"}
              width={isSelected ? 6 : 5}
              opacity={isSelected ? 1 : 0.6}
              interactive
              onClick={() => setSelectedIndex(index)}
            />
          );
        })}

        <MapMarker longitude={start.lng} latitude={start.lat}>
          <MarkerContent>
            <div className="size-5 rounded-full bg-green-500 border-2 border-white shadow-lg" />
            <MarkerLabel position="top">{start.name}</MarkerLabel>
          </MarkerContent>
        </MapMarker>

        <MapMarker longitude={end.lng} latitude={end.lat}>
          <MarkerContent>
            <div className="size-5 rounded-full bg-red-500 border-2 border-white shadow-lg" />
            <MarkerLabel position="bottom">{end.name}</MarkerLabel>
          </MarkerContent>
        </MapMarker>
      </Map>

      {routes.length > 0 && (
        <div className="absolute top-3 left-3 flex flex-col gap-2 z-10">
          {routes.map((route, index) => {
            const isActive = index === selectedIndex;
            const isFastest = index === 0;
            return (
              <Button
                key={index}
                variant={isActive ? "default" : "secondary"}
                size="sm"
                onClick={() => setSelectedIndex(index)}
                className="justify-start gap-3"
              >
                <div className="flex items-center gap-1.5">
                  <Clock className="size-3.5" />
                  <span className="font-medium">
                    {formatDuration(route.duration)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-xs opacity-80">
                  <Route className="size-3" />
                  {formatDistance(route.distance)}
                </div>
                {isFastest && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                    Fastest
                  </span>
                )}
              </Button>
            );
          })}
        </div>
      )}

      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 backdrop-blur-[2px] z-20">
          <Loader2 className="size-6 animate-spin text-white" />
        </div>
      )}
    </Card>
  );
}

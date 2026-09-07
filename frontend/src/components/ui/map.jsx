/**
 * @mapcn/map - Complete MapLibre GL JS React Map Component Suite
 * Implements Map, useMap, MapControls, MapMarker, MarkerContent, MarkerLabel,
 * MarkerPopup, MarkerTooltip, MapPopup, MapRoute, MapArc, MapGeoJSON,
 * MapClusterLayer, and MapHeatLayer.
 */
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  useId,
} from "react";
import { createPortal } from "react-dom";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

// Set web worker for MapLibre GL (local or unpkg CDN fallback)
if (typeof maplibregl.setWorkerUrl === "function") {
  try {
    maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
  } catch {
    maplibregl.setWorkerUrl(
      "https://unpkg.com/maplibre-gl@latest/dist/maplibre-gl-csp-worker.js"
    );
  }
}

// ----------------------------------------------------------------------
// Context
// ----------------------------------------------------------------------
const MapContext = createContext({
  map: null,
  isLoaded: false,
  theme: "light",
  toggleTheme: () => {},
  setTheme: () => {},
  styleVersion: 0,
});

export function useMap() {
  return useContext(MapContext);
}

const MarkerContext = createContext({
  marker: null,
  element: null,
});

// ----------------------------------------------------------------------
// Basemap Styles
// ----------------------------------------------------------------------
export const BLANK_STYLE = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "transparent" },
    },
  ],
};

export const CARTO_LIGHT_STYLE = "https://tiles.openfreemap.org/styles/positron";

export const CARTO_DARK_STYLE = "https://tiles.openfreemap.org/styles/dark";

export const OSM_RASTER_STYLE = {
  version: 8,
  sources: {
    "osm-tiles": {
      type: "raster",
      tiles: [
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [
    {
      id: "osm-tiles-layer",
      type: "raster",
      source: "osm-tiles",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

function detectTheme() {
  if (typeof document === "undefined") return "light";
  if (
    document.documentElement.classList.contains("dark") ||
    document.documentElement.getAttribute("data-theme") === "dark" ||
    document.body.classList.contains("dark")
  ) {
    return "dark";
  }
  if (
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  ) {
    return "dark";
  }
  return "light";
}

// ----------------------------------------------------------------------
// 1. <Map /> Root Component
// ----------------------------------------------------------------------
export function Map({
  center = [-74.006, 40.7128], // [lng, lat]
  zoom = 11,
  pitch = 0,
  bearing = 0,
  theme,
  styles,
  blank = false,
  projection,
  viewport,
  onViewportChange,
  loading = false,
  className = "",
  children,
  onClick,
  ...mapOptions
}) {
  const containerRef = useRef(null);
  const [map, setMap] = useState(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [styleVersion, setStyleVersion] = useState(0);
  const [currentTheme, setCurrentTheme] = useState(() => theme || detectTheme());

  // Listen to system & DOM class theme changes when theme prop is not explicitly passed
  useEffect(() => {
    if (theme) {
      setCurrentTheme(theme);
      return;
    }

    const updateDetectedTheme = () => {
      setCurrentTheme(detectTheme());
    };

    // 1. Watch DOM mutation (e.g. dark class toggle)
    const observer = new MutationObserver(updateDetectedTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "data-theme"],
    });

    // 2. Watch system prefers-color-scheme
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    mediaQuery.addEventListener("change", updateDetectedTheme);

    return () => {
      observer.disconnect();
      mediaQuery.removeEventListener("change", updateDetectedTheme);
    };
  }, [theme]);

  // Determine active style
  const resolveStyle = useCallback(() => {
    if (blank) return BLANK_STYLE;
    if (styles) {
      return (
        (currentTheme === "dark" ? styles.dark : styles.light) ||
        styles.light ||
        styles
      );
    }
    return currentTheme === "dark" ? CARTO_DARK_STYLE : CARTO_LIGHT_STYLE;
  }, [blank, styles, currentTheme]);

  useEffect(() => {
    if (!containerRef.current) return;

    const initialCenter = viewport?.center || center;
    const initialZoom = viewport?.zoom ?? zoom;
    const initialPitch = viewport?.pitch ?? pitch;
    const initialBearing = viewport?.bearing ?? bearing;

    const instance = new maplibregl.Map({
      container: containerRef.current,
      style: resolveStyle(),
      center: initialCenter,
      zoom: initialZoom,
      pitch: initialPitch,
      bearing: initialBearing,
      attributionControl: false,
      ...(projection ? { projection } : {}),
      ...mapOptions,
    });

    instance.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-right"
    );

    instance.on("load", () => {
      setMap(instance);
      setIsLoaded(true);
    });

    instance.on("styledata", () => {
      setStyleVersion((v) => v + 1);
    });

    if (onViewportChange) {
      instance.on("move", () => {
        const c = instance.getCenter();
        onViewportChange({
          longitude: c.lng,
          latitude: c.lat,
          zoom: instance.getZoom(),
          pitch: instance.getPitch(),
          bearing: instance.getBearing(),
        });
      });
    }

    if (onClick) {
      instance.on("click", (e) => {
        onClick({ lngLat: e.lngLat, point: e.point });
      });
    }

    return () => {
      instance.remove();
      setMap(null);
      setIsLoaded(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update style when theme / style prop changes
  useEffect(() => {
    if (!map || !isLoaded) return;
    map.setStyle(resolveStyle());
  }, [map, isLoaded, resolveStyle]);

  // Handle controlled viewport
  useEffect(() => {
    if (!map || !isLoaded || !viewport) return;
    if (viewport.longitude != null && viewport.latitude != null) {
      map.setCenter([viewport.longitude, viewport.latitude]);
    }
    if (viewport.zoom != null) map.setZoom(viewport.zoom);
    if (viewport.pitch != null) map.setPitch(viewport.pitch);
    if (viewport.bearing != null) map.setBearing(viewport.bearing);
  }, [map, isLoaded, viewport]);

  const toggleTheme = useCallback(() => {
    setCurrentTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }, []);

  return (
    <MapContext.Provider
      value={{
        map,
        isLoaded,
        theme: currentTheme,
        toggleTheme,
        setTheme: setCurrentTheme,
        styleVersion,
      }}
    >
      <div
        ref={containerRef}
        className={`mapcn-container relative w-full h-full min-h-[200px] overflow-hidden ${className}`}
      >
        {isLoaded && children}
        {loading && (
          <div className="mapcn-loading absolute inset-0 flex items-center justify-center bg-black/20 backdrop-blur-[2px] z-50 pointer-events-none">
            <div className="size-8 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
          </div>
        )}
      </div>
    </MapContext.Provider>
  );
}

// ----------------------------------------------------------------------
// 2. <MapThemeToggle /> & <MapControls />
// ----------------------------------------------------------------------
export function MapThemeToggle({ className = "" }) {
  const { theme, toggleTheme } = useMap();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={`Switch to ${isDark ? "Light" : "Dark"} Mode`}
      aria-label="Toggle map theme"
      className={`maplibregl-ctrl-icon flex items-center justify-center size-[29px] bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-700 border-0 rounded shadow transition-colors cursor-pointer ${className}`}
    >
      {isDark ? (
        // Sun icon for switching to light
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2" />
          <path d="M12 20v2" />
          <path d="m4.93 4.93 1.41 1.41" />
          <path d="m17.66 17.66 1.41 1.41" />
          <path d="M2 12h2" />
          <path d="M20 12h2" />
          <path d="m6.34 17.66-1.41 1.41" />
          <path d="m19.07 4.93-1.41 1.41" />
        </svg>
      ) : (
        // Moon icon for switching to dark
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
        </svg>
      )}
    </button>
  );
}

export function MapControls({
  position = "bottom-right",
  showZoom = true,
  showCompass = false,
  showLocate = false,
  showFullscreen = false,
  showThemeToggle = true,
  onLocate,
  className = "",
}) {
  const { map, isLoaded, theme, toggleTheme } = useMap();
  const themeControlContainerRef = useRef(null);

  useEffect(() => {
    if (!isLoaded || !map) return;

    const controls = [];

    if (showZoom || showCompass) {
      const navControl = new maplibregl.NavigationControl({
        showZoom,
        showCompass,
        visualizePitch: true,
      });
      map.addControl(navControl, position);
      controls.push(navControl);
    }

    if (showFullscreen) {
      const fsControl = new maplibregl.FullscreenControl();
      map.addControl(fsControl, position);
      controls.push(fsControl);
    }

    if (showLocate) {
      const geolocate = new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: true,
      });
      if (onLocate) {
        geolocate.on("geolocate", (e) => {
          onLocate({
            longitude: e.coords.longitude,
            latitude: e.coords.latitude,
          });
        });
      }
      map.addControl(geolocate, position);
      controls.push(geolocate);
    }

    // Custom theme toggle button inside MapLibre control group
    if (showThemeToggle) {
      const ctrlDiv = document.createElement("div");
      ctrlDiv.className =
        "maplibregl-ctrl maplibregl-ctrl-group mapcn-theme-ctrl-group";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "maplibregl-ctrl-icon flex items-center justify-center";
      btn.title = "Toggle Light / Dark Map Theme";
      btn.setAttribute("aria-label", "Toggle map theme");
      btn.onclick = () => toggleTheme();
      btn.innerHTML = `<span style="font-size:14px;line-height:1;display:flex;align-items:center;justify-content:center;height:100%;">${
        theme === "dark" ? "☀️" : "🌙"
      }</span>`;
      ctrlDiv.appendChild(btn);

      const customControl = {
        onAdd() {
          return ctrlDiv;
        },
        onRemove() {
          ctrlDiv.parentNode?.removeChild(ctrlDiv);
        },
      };

      map.addControl(customControl, position);
      controls.push(customControl);
    }

    return () => {
      controls.forEach((c) => {
        if (map.hasControl(c)) map.removeControl(c);
      });
    };
  }, [
    map,
    isLoaded,
    position,
    showZoom,
    showCompass,
    showLocate,
    showFullscreen,
    showThemeToggle,
    theme,
    toggleTheme,
    onLocate,
  ]);

  return null;
}

// ----------------------------------------------------------------------
// 3. <MapMarker /> & Marker Subcomponents
// ----------------------------------------------------------------------
export function MapMarker({
  longitude,
  latitude,
  children,
  draggable = false,
  onClick,
  onMouseEnter,
  onMouseLeave,
  onDragStart,
  onDrag,
  onDragEnd,
  className = "",
}) {
  const { map, isLoaded } = useMap();
  const markerRef = useRef(null);
  const elementRef = useRef(document.createElement("div"));

  useEffect(() => {
    if (!isLoaded || !map || longitude == null || latitude == null) return;

    const el = elementRef.current;
    el.className = `mapcn-marker ${className}`;
    el.style.cursor = onClick ? "pointer" : "default";

    if (onClick) el.onclick = onClick;
    if (onMouseEnter) el.onmouseenter = onMouseEnter;
    if (onMouseLeave) el.onmouseleave = onMouseLeave;

    const marker = new maplibregl.Marker({
      element: el,
      draggable: draggable,
    })
      .setLngLat([longitude, latitude])
      .addTo(map);

    if (draggable) {
      if (onDragStart) marker.on("dragstart", () => onDragStart(marker.getLngLat()));
      if (onDrag) marker.on("drag", () => onDrag(marker.getLngLat()));
      if (onDragEnd) marker.on("dragend", () => onDragEnd(marker.getLngLat()));
    }

    markerRef.current = marker;

    return () => {
      marker.remove();
      markerRef.current = null;
    };
  }, [
    map,
    isLoaded,
    longitude,
    latitude,
    draggable,
    className,
    onClick,
    onMouseEnter,
    onMouseLeave,
    onDragStart,
    onDrag,
    onDragEnd,
  ]);

  useEffect(() => {
    if (markerRef.current && longitude != null && latitude != null) {
      markerRef.current.setLngLat([longitude, latitude]);
    }
  }, [longitude, latitude]);

  return (
    <MarkerContext.Provider
      value={{ marker: markerRef.current, element: elementRef.current }}
    >
      {createPortal(children || <MarkerContent />, elementRef.current)}
    </MarkerContext.Provider>
  );
}

export function MarkerContent({ children, className = "" }) {
  return (
    <div
      className={`mapcn-marker-content relative flex items-center justify-center ${className}`}
    >
      {children || (
        <div className="size-4 rounded-full bg-blue-600 border-2 border-white shadow-md" />
      )}
    </div>
  );
}

export function MarkerLabel({
  children,
  position = "top",
  className = "",
}) {
  const isBottom = position === "bottom";
  return (
    <div
      className={`mapcn-marker-label absolute left-1/2 -translate-x-1/2 whitespace-nowrap px-1.5 py-0.5 rounded text-xs font-medium bg-background/90 text-foreground shadow border pointer-events-none ${
        isBottom ? "top-full mt-1" : "bottom-full mb-1"
      } ${className}`}
    >
      {children}
    </div>
  );
}

export function MarkerPopup({
  children,
  className = "",
  closeButton = false,
  onClose,
}) {
  const { map } = useMap();
  const { marker } = useContext(MarkerContext);
  const popupRef = useRef(null);
  const contentRef = useRef(document.createElement("div"));

  useEffect(() => {
    if (!marker || !map) return;

    const popup = new maplibregl.Popup({
      offset: 16,
      closeButton: closeButton,
      className: `mapcn-popup-root ${className}`,
    }).setDOMContent(contentRef.current);

    if (onClose) {
      popup.on("close", onClose);
    }

    marker.setPopup(popup);
    popupRef.current = popup;

    return () => {
      marker.setPopup(null);
      popup.remove();
    };
  }, [marker, map, closeButton, className, onClose]);

  return createPortal(
    <div className="mapcn-popup-inner p-2.5 bg-background text-foreground rounded-lg shadow-lg border text-sm max-w-xs">
      {children}
    </div>,
    contentRef.current
  );
}

export function MarkerTooltip({ children, className = "" }) {
  const { map } = useMap();
  const { marker, element } = useContext(MarkerContext);
  const popupRef = useRef(null);
  const contentRef = useRef(document.createElement("div"));

  useEffect(() => {
    if (!marker || !map || !element) return;

    const popup = new maplibregl.Popup({
      offset: 14,
      closeButton: false,
      closeOnClick: false,
      className: `mapcn-tooltip-root ${className}`,
    }).setDOMContent(contentRef.current);

    popupRef.current = popup;

    const showTooltip = () => {
      popup.setLngLat(marker.getLngLat()).addTo(map);
    };
    const hideTooltip = () => {
      popup.remove();
    };

    element.addEventListener("mouseenter", showTooltip);
    element.addEventListener("mouseleave", hideTooltip);

    return () => {
      element.removeEventListener("mouseenter", showTooltip);
      element.removeEventListener("mouseleave", hideTooltip);
      popup.remove();
    };
  }, [marker, map, element, className]);

  return createPortal(
    <div className="mapcn-tooltip-inner px-2 py-1 bg-background/95 text-foreground rounded text-xs shadow border">
      {children}
    </div>,
    contentRef.current
  );
}

// ----------------------------------------------------------------------
// 4. <MapPopup /> Standalone Popup
// ----------------------------------------------------------------------
export function MapPopup({
  longitude,
  latitude,
  children,
  onClose,
  closeButton = false,
  focusAfterOpen = false,
  closeOnClick = true,
  className = "",
}) {
  const { map, isLoaded } = useMap();
  const popupRef = useRef(null);
  const contentRef = useRef(document.createElement("div"));

  useEffect(() => {
    if (!isLoaded || !map || longitude == null || latitude == null) return;

    const popup = new maplibregl.Popup({
      offset: 12,
      closeButton,
      closeOnClick,
      focusAfterOpen,
      className: `mapcn-standalone-popup ${className}`,
    })
      .setLngLat([longitude, latitude])
      .setDOMContent(contentRef.current)
      .addTo(map);

    if (onClose) {
      popup.on("close", onClose);
    }

    popupRef.current = popup;

    return () => {
      popup.remove();
      popupRef.current = null;
    };
  }, [
    map,
    isLoaded,
    longitude,
    latitude,
    closeButton,
    closeOnClick,
    focusAfterOpen,
    className,
    onClose,
  ]);

  useEffect(() => {
    if (popupRef.current && longitude != null && latitude != null) {
      popupRef.current.setLngLat([longitude, latitude]);
    }
  }, [longitude, latitude]);

  return createPortal(
    <div className="p-3 bg-background text-foreground rounded-lg shadow-xl border text-sm min-w-[180px]">
      {children}
    </div>,
    contentRef.current
  );
}

// ----------------------------------------------------------------------
// 5. <MapRoute /> Line Route
// ----------------------------------------------------------------------
export function MapRoute({
  id,
  coordinates = [], // [[lng, lat], ...]
  color = "#4285F4",
  width = 3,
  opacity = 0.8,
  dashArray = null,
  onClick,
  onMouseEnter,
  onMouseLeave,
  interactive = false,
}) {
  const { map, isLoaded } = useMap();
  const generatedId = useId().replace(/:/g, "_");
  const layerId = id || `mapcn-route-${generatedId}`;
  const sourceId = `mapcn-source-${layerId}`;

  useEffect(() => {
    if (!isLoaded || !map || !coordinates || coordinates.length < 2) return;

    const geojson = {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: coordinates,
      },
    };

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: "geojson",
        data: geojson,
      });

      const paint = {
        "line-color": color,
        "line-width": width,
        "line-opacity": opacity,
      };
      if (dashArray) {
        paint["line-dasharray"] = dashArray;
      }

      map.addLayer({
        id: layerId,
        type: "line",
        source: sourceId,
        layout: {
          "line-join": "round",
          "line-cap": "round",
        },
        paint: paint,
      });

      if (interactive || onClick || onMouseEnter || onMouseLeave) {
        if (onClick) map.on("click", layerId, onClick);

        map.on("mouseenter", layerId, (e) => {
          map.getCanvas().style.cursor = "pointer";
          if (onMouseEnter) onMouseEnter(e);
        });

        map.on("mouseleave", layerId, (e) => {
          map.getCanvas().style.cursor = "";
          if (onMouseLeave) onMouseLeave(e);
        });
      }
    } else {
      map.getSource(sourceId).setData(geojson);
      map.setPaintProperty(layerId, "line-color", color);
      map.setPaintProperty(layerId, "line-width", width);
      map.setPaintProperty(layerId, "line-opacity", opacity);
    }

    return () => {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    };
  }, [
    map,
    isLoaded,
    sourceId,
    layerId,
    coordinates,
    color,
    width,
    opacity,
    dashArray,
    interactive,
    onClick,
    onMouseEnter,
    onMouseLeave,
  ]);

  return null;
}

// ----------------------------------------------------------------------
// 6. <MapArc /> Curved Lines in Lon/Lat Space
// ----------------------------------------------------------------------
function getQuadraticBezierPoints(p0, p1, curvature = 0.2, samples = 64) {
  const [x0, y0] = p0;
  const [x1, y1] = p1;

  const dx = x1 - x0;
  const dy = y1 - y0;
  const mx = (x0 + x1) / 2;
  const my = (y0 + y1) / 2;

  // Normal vector perpendicular to chord
  const nx = -dy * curvature;
  const ny = dx * curvature;

  const cx = mx + nx;
  const cy = my + ny;

  const points = [];
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const invT = 1 - t;
    const x = invT * invT * x0 + 2 * invT * t * cx + t * t * x1;
    const y = invT * invT * y0 + 2 * invT * t * cy + t * t * y1;
    points.push([x, y]);
  }
  return points;
}

export function MapArc({
  data = [],
  id = "arcs",
  curvature = 0.2,
  samples = 64,
  paint = { "line-color": "#4285F4", "line-width": 2, "line-opacity": 0.85 },
  layout = { "line-join": "round", "line-cap": "round" },
  hoverPaint,
  onClick,
  onHover,
  interactive = true,
  beforeId,
}) {
  const { map, isLoaded } = useMap();
  const sourceId = `mapcn-arc-source-${id}`;
  const layerId = `mapcn-arc-layer-${id}`;

  useEffect(() => {
    if (!isLoaded || !map || !data?.length) return;

    const features = data.map((arc, index) => {
      const coords = getQuadraticBezierPoints(
        arc.from,
        arc.to,
        arc.curvature ?? curvature,
        samples
      );
      return {
        type: "Feature",
        id: arc.id || index,
        properties: { ...arc },
        geometry: {
          type: "LineString",
          coordinates: coords,
        },
      };
    });

    const geojson = {
      type: "FeatureCollection",
      features,
    };

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: "geojson",
        data: geojson,
      });

      map.addLayer(
        {
          id: layerId,
          type: "line",
          source: sourceId,
          layout: layout,
          paint: paint,
        },
        beforeId
      );

      if (interactive) {
        if (onClick) {
          map.on("click", layerId, (e) => {
            if (e.features?.length) onClick(e.features[0]);
          });
        }

        map.on("mouseenter", layerId, (e) => {
          map.getCanvas().style.cursor = "pointer";
          if (onHover && e.features?.length) onHover(e.features[0]);
        });

        map.on("mouseleave", layerId, () => {
          map.getCanvas().style.cursor = "";
          if (onHover) onHover(null);
        });
      }
    } else {
      map.getSource(sourceId).setData(geojson);
    }

    return () => {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    };
  }, [
    map,
    isLoaded,
    sourceId,
    layerId,
    data,
    curvature,
    samples,
    paint,
    layout,
    interactive,
    onClick,
    onHover,
    beforeId,
  ]);

  return null;
}

// ----------------------------------------------------------------------
// 7. <MapGeoJSON /> Polygons & Boundary Visualizations
// ----------------------------------------------------------------------
export function MapGeoJSON({
  data,
  id = "geojson",
  promoteId,
  fillPaint = { "fill-color": "#3b82f6", "fill-opacity": 0.2 },
  linePaint = { "line-color": "#2563eb", "line-width": 1.5 },
  fillHoverPaint,
  onClick,
  onHover,
  interactive = false,
  beforeId,
}) {
  const { map, isLoaded } = useMap();
  const sourceId = `mapcn-geojson-source-${id}`;
  const fillLayerId = `mapcn-geojson-fill-${id}`;
  const lineLayerId = `mapcn-geojson-line-${id}`;

  useEffect(() => {
    if (!isLoaded || !map || !data) return;

    const sourceConfig = {
      type: "geojson",
      data: data,
      ...(promoteId ? { promoteId } : {}),
    };

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, sourceConfig);

      if (fillPaint !== false) {
        map.addLayer(
          {
            id: fillLayerId,
            type: "fill",
            source: sourceId,
            paint: fillPaint,
          },
          beforeId
        );
      }

      if (linePaint !== false) {
        map.addLayer(
          {
            id: lineLayerId,
            type: "line",
            source: sourceId,
            paint: linePaint,
          },
          beforeId
        );
      }

      if (interactive && fillPaint !== false) {
        if (onClick) {
          map.on("click", fillLayerId, (e) => {
            if (e.features?.length) onClick(e.features[0]);
          });
        }

        map.on("mousemove", fillLayerId, (e) => {
          map.getCanvas().style.cursor = "pointer";
          if (onHover && e.features?.length) onHover(e.features[0]);
        });

        map.on("mouseleave", fillLayerId, () => {
          map.getCanvas().style.cursor = "";
          if (onHover) onHover(null);
        });
      }
    } else {
      map.getSource(sourceId).setData(data);
    }

    return () => {
      if (map.getLayer(fillLayerId)) map.removeLayer(fillLayerId);
      if (map.getLayer(lineLayerId)) map.removeLayer(lineLayerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    };
  }, [
    map,
    isLoaded,
    data,
    sourceId,
    fillLayerId,
    lineLayerId,
    promoteId,
    fillPaint,
    linePaint,
    fillHoverPaint,
    interactive,
    onClick,
    onHover,
    beforeId,
  ]);

  return null;
}

// ----------------------------------------------------------------------
// 8. <MapClusterLayer /> Clustered Point Markers
// ----------------------------------------------------------------------
export function MapClusterLayer({
  data,
  clusterMaxZoom = 14,
  clusterRadius = 50,
  clusterColors = ["#3b82f6", "#1d4ed8", "#1e3a8a"],
  clusterThresholds = [100, 750],
  pointColor = "#3b82f6",
  onPointClick,
  onClusterClick,
}) {
  const { map, isLoaded } = useMap();
  const sourceId = "mapcn-cluster-source";
  const clusterLayerId = "mapcn-clusters";
  const clusterCountLayerId = "mapcn-cluster-count";
  const unclusteredLayerId = "mapcn-unclustered-point";

  useEffect(() => {
    if (!isLoaded || !map || !data) return;

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: "geojson",
        data: data,
        cluster: true,
        clusterMaxZoom: clusterMaxZoom,
        clusterRadius: clusterRadius,
      });

      // Cluster circles
      map.addLayer({
        id: clusterLayerId,
        type: "circle",
        source: sourceId,
        filter: ["has", "point_count"],
        paint: {
          "circle-color": [
            "step",
            ["get", "point_count"],
            clusterColors[0],
            clusterThresholds[0],
            clusterColors[1],
            clusterThresholds[1],
            clusterColors[2],
          ],
          "circle-radius": [
            "step",
            ["get", "point_count"],
            18,
            clusterThresholds[0],
            24,
            clusterThresholds[1],
            30,
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      // Cluster count text
      map.addLayer({
        id: clusterCountLayerId,
        type: "symbol",
        source: sourceId,
        filter: ["has", "point_count"],
        layout: {
          "text-field": "{point_count_abbreviated}",
          "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
          "text-size": 12,
        },
        paint: {
          "text-color": "#ffffff",
        },
      });

      // Individual unclustered points
      map.addLayer({
        id: unclusteredLayerId,
        type: "circle",
        source: sourceId,
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": pointColor,
          "circle-radius": 6,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
        },
      });

      // Cluster click: Zoom in or trigger onClusterClick
      map.on("click", clusterLayerId, (e) => {
        const features = map.queryRenderedFeatures(e.point, {
          layers: [clusterLayerId],
        });
        const clusterId = features[0]?.properties?.cluster_id;
        const count = features[0]?.properties?.point_count;
        const coords = features[0]?.geometry?.coordinates;

        if (onClusterClick) {
          onClusterClick(clusterId, coords, count);
        } else if (clusterId != null) {
          map
            .getSource(sourceId)
            .getClusterExpansionZoom(clusterId, (err, zoomLevel) => {
              if (err) return;
              map.easeTo({
                center: coords,
                zoom: zoomLevel,
              });
            });
        }
      });

      // Unclustered point click
      if (onPointClick) {
        map.on("click", unclusteredLayerId, (e) => {
          if (e.features?.length) {
            onPointClick(e.features[0], e.features[0].geometry.coordinates);
          }
        });
      }

      map.on("mouseenter", clusterLayerId, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", clusterLayerId, () => {
        map.getCanvas().style.cursor = "";
      });
    } else {
      map.getSource(sourceId).setData(data);
    }

    return () => {
      if (map.getLayer(clusterCountLayerId)) map.removeLayer(clusterCountLayerId);
      if (map.getLayer(clusterLayerId)) map.removeLayer(clusterLayerId);
      if (map.getLayer(unclusteredLayerId)) map.removeLayer(unclusteredLayerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    };
  }, [
    map,
    isLoaded,
    data,
    clusterMaxZoom,
    clusterRadius,
    clusterColors,
    clusterThresholds,
    pointColor,
    onPointClick,
    onClusterClick,
  ]);

  return null;
}

// ----------------------------------------------------------------------
// 9. <MapHeatLayer /> Crime/Incident Density Heatmap
// ----------------------------------------------------------------------
export function MapHeatLayer({ heat = [], enabled = true }) {
  const { map, isLoaded } = useMap();

  useEffect(() => {
    if (!isLoaded || !map || !enabled || !heat?.length) return;

    const sourceId = "mapcn-heat-source";
    const layerId = "mapcn-heat-layer";

    const features = heat.map(([lat, lng, intensity]) => ({
      type: "Feature",
      properties: {
        intensity: intensity || 0.5,
      },
      geometry: {
        type: "Point",
        coordinates: [lng, lat],
      },
    }));

    const geojson = {
      type: "FeatureCollection",
      features: features,
    };

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: "geojson",
        data: geojson,
      });

      map.addLayer({
        id: layerId,
        type: "heatmap",
        source: sourceId,
        maxzoom: 17,
        paint: {
          "heatmap-weight": ["get", "intensity"],
          "heatmap-intensity": 1.2,
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0,
            "rgba(0,0,0,0)",
            0.2,
            "#34a853",
            0.5,
            "#fbbc04",
            0.8,
            "#ea8600",
            1.0,
            "#ea4335",
          ],
          "heatmap-radius": 24,
          "heatmap-opacity": 0.65,
        },
      });
    } else {
      map.getSource(sourceId).setData(geojson);
    }

    return () => {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    };
  }, [map, isLoaded, heat, enabled]);

  return null;
}

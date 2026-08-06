/**
 * Google Maps–style Safe Route planner:
 * full map → search destination → crime heatmap → ranked safer routes → start.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { contactsApi, mapsApi } from "../api/client";
import { useGeolocation } from "../hooks/useGeolocation";
import PlannerMap from "./PlannerMap";

export default function SafeRoutePlanner({
  token,
  onStartJourney,
  busy,
  startError = "",
}) {
  const [contacts, setContacts] = useState([]);
  const [contactId, setContactId] = useState("");
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [searching, setSearching] = useState(false);
  const [routing, setRouting] = useState(false);
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [routes, setRoutes] = useState([]);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [heat, setHeat] = useState([]);
  const [showHeat, setShowHeat] = useState(true);
  const [panelOpen, setPanelOpen] = useState(true);
  const [crimeMeta, setCrimeMeta] = useState(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const debounceRef = useRef(null);
  const searchInputRef = useRef(null);

  const displayError = startError || error;

  const { position, error: geoError, requestOnce, permissionState } =
    useGeolocation({ enabled: true });

  useEffect(() => {
    if (position && !origin) {
      setOrigin({
        lat: position.lat,
        lng: position.lng,
        label: "Current location",
      });
    }
  }, [position, origin]);

  useEffect(() => {
    async function boot() {
      try {
        const [c, crime] = await Promise.all([
          contactsApi.list(token),
          mapsApi.crimeHotspots(token),
        ]);
        const list = c.contacts || [];
        setContacts(list);
        const primary = list.find((x) => x.is_primary) || list[0];
        if (primary) setContactId(String(primary.id));
        setHeat(crime.heat || []);
        setCrimeMeta(crime.meta || null);
      } catch (err) {
        setError(err.message || "Failed to load planner.");
      }
    }
    boot();
  }, [token]);

  const locateMe = useCallback(async () => {
    try {
      const pos = await requestOnce();
      setOrigin({ lat: pos.lat, lng: pos.lng, label: "Current location" });
      setStatus("Location updated.");
    } catch (err) {
      setError(err.message || "Could not get GPS.");
    }
  }, [requestOnce]);

  function onSearchChange(e) {
    const value = e.target.value;
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!value.trim()) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await mapsApi.geocode(token, value.trim());
        setSuggestions(data.results || []);
      } catch (err) {
        setSuggestions([]);
        setError(err.message || "Search failed.");
      } finally {
        setSearching(false);
      }
    }, 350);
  }

  async function selectSuggestion(item) {
    setQuery(item.label);
    setSuggestions([]);
    setDestination({ lat: item.lat, lng: item.lng, label: item.label });
    setPanelOpen(true);
    await computeRoutes(item.lat, item.lng, item.label);
  }

  async function computeRoutes(destLat, destLng, destLabel) {
    setRouting(true);
    setError("");
    setStatus("Finding safest routes…");
    try {
      let start = origin;
      if (!start) {
        const pos = await requestOnce();
        start = { lat: pos.lat, lng: pos.lng, label: "Current location" };
        setOrigin(start);
      }
      const data = await mapsApi.saferRoutes(token, {
        start_lat: start.lat,
        start_lng: start.lng,
        dest_lat: destLat,
        dest_lng: destLng,
      });
      setRoutes(data.routes || []);
      const recommended =
        data.routes?.find((r) => r.is_recommended) || data.routes?.[0];
      setSelectedRouteId(recommended ? recommended.id : null);
      setStatus(
        recommended
          ? `Safest path · Safety Score ${recommended.safety_score}`
          : "Routes ready."
      );
      if (destLabel) {
        setDestination((d) =>
          d || { lat: destLat, lng: destLng, label: destLabel }
        );
      }
    } catch (err) {
      setError(err.message || "Could not compute routes.");
      setRoutes([]);
    } finally {
      setRouting(false);
    }
  }

  async function handleStart() {
    if (!destination) {
      setError("Search and select a destination first.");
      searchInputRef.current?.focus();
      return;
    }
    if (!contacts.length) {
      setError("Add an emergency contact first.");
      return;
    }
    const selected =
      routes.find((r) => r.id === selectedRouteId) || routes[0] || null;
    let start = origin;
    if (!start) {
      const pos = await requestOnce();
      start = { lat: pos.lat, lng: pos.lng };
    }
    await onStartJourney({
      dest_label: destination.label || query || "Destination",
      dest_lat: destination.lat,
      dest_lng: destination.lng,
      start_lat: start.lat,
      start_lng: start.lng,
      active_contact_id: Number(contactId),
      expected_route: selected
        ? {
            safety_score: selected.safety_score,
            risk_indicator: selected.risk_indicator,
            coordinates: selected.coordinates,
            distance_m: selected.distance_m,
          }
        : null,
    });
  }

  function clearDestination() {
    setQuery("");
    setDestination(null);
    setRoutes([]);
    setSelectedRouteId(null);
    setSuggestions([]);
    setStatus("");
    searchInputRef.current?.focus();
  }

  const selectedRoute = routes.find((r) => r.id === selectedRouteId);

  return (
    <section className="journey-map-layout planner-layout">
      <div className="map-stage">
        <PlannerMap
          origin={origin}
          destination={destination}
          routes={routes}
          selectedRouteId={selectedRouteId}
          heat={heat}
          showHeat={showHeat}
          onSelectRoute={setSelectedRouteId}
        />

        {/* Google Maps–style floating search */}
        <div className="gmaps-topbar">
          <div className="gmaps-search-box">
            <span className="gmaps-search-icon" aria-hidden>
              ⌕
            </span>
            <input
              ref={searchInputRef}
              value={query}
              onChange={onSearchChange}
              placeholder="Search destination"
              aria-label="Search destination"
              autoComplete="off"
              autoFocus
            />
            {searching && <span className="gmaps-spinner" />}
            {query && !searching && (
              <button
                type="button"
                className="gmaps-clear"
                onClick={clearDestination}
                aria-label="Clear search"
              >
                ×
              </button>
            )}
          </div>

          {suggestions.length > 0 && (
            <ul className="gmaps-suggest">
              {suggestions.map((s) => (
                <li key={`${s.lat}-${s.lng}-${s.label}`}>
                  <button type="button" onClick={() => selectSuggestion(s)}>
                    <span className="gmaps-pin-mini" aria-hidden />
                    <span>{s.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Floating map controls */}
        <div className="gmaps-fabs">
          <button
            type="button"
            className={`gmaps-fab ${showHeat ? "active" : ""}`}
            onClick={() => setShowHeat((v) => !v)}
            title="Crime heatmap"
          >
            Heat
          </button>
          <button
            type="button"
            className="gmaps-fab"
            onClick={locateMe}
            title="My location"
          >
            ◎
          </button>
          <button
            type="button"
            className="gmaps-fab"
            onClick={() => setPanelOpen((v) => !v)}
            title="Directions panel"
          >
            {panelOpen ? "▾" : "▴"}
          </button>
        </div>

        {/* Directions / route panel */}
        {panelOpen && (
          <div className="gmaps-panel">
            <div className="gmaps-panel-inner">
              <div className="gmaps-brand-row">
                <strong>SafeRoute</strong>
                <span className="muted tiny">Safer path planner</span>
              </div>

              <div className="gmaps-legs">
                <div className="gmaps-leg">
                  <span className="leg-dot origin" />
                  <div className="leg-text">
                    <span className="leg-label">From</span>
                    <strong>
                      {origin
                        ? origin.label ||
                          `${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)}`
                        : "Getting GPS…"}
                    </strong>
                  </div>
                  <button type="button" className="link-btn" onClick={locateMe}>
                    GPS
                  </button>
                </div>
                <div className="gmaps-leg-line" />
                <div className="gmaps-leg">
                  <span className="leg-dot dest" />
                  <div className="leg-text">
                    <span className="leg-label">To</span>
                    <strong>
                      {destination?.label ||
                        (query ? query : "Search a place above")}
                    </strong>
                  </div>
                </div>
              </div>

              {contacts.length === 0 ? (
                <div className="alert alert-error">
                  Add a trusted contact first.{" "}
                  <Link to="/contacts">Contacts</Link>
                </div>
              ) : (
                <label className="planner-contact">
                  Alert contact
                  <select
                    value={contactId}
                    onChange={(e) => setContactId(e.target.value)}
                  >
                    {contacts.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                        {c.is_primary ? " (Primary)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <div className="planner-toggles">
                <label className="heat-toggle">
                  <input
                    type="checkbox"
                    checked={showHeat}
                    onChange={(e) => setShowHeat(e.target.checked)}
                  />
                  Crime heatmap
                </label>
                <span className="muted tiny">GPS: {permissionState}</span>
              </div>
              {crimeMeta?.source && (
                <p className="muted tiny heat-source">
                  Heatmap: {crimeMeta.title || "Crime dataset"}
                  {crimeMeta.hotspot_count
                    ? ` · ${crimeMeta.hotspot_count} spots`
                    : ""}
                </p>
              )}

              {displayError && <div className="map-error">{displayError}</div>}
              {geoError && <div className="map-error">{geoError}</div>}
              {status && <div className="map-ok">{status}</div>}
              {routing && (
                <div className="muted tiny">Computing safest paths…</div>
              )}

                {routes.length > 0 && (
                <div className="route-cards">
                  <div className="route-cards-title">
                    {routes.length} route{routes.length === 1 ? "" : "s"} · pick safest
                  </div>
                  {routes.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      className={`route-card ${r.id === selectedRouteId ? "selected" : ""} ${r.is_recommended ? "recommended" : ""}`}
                      onClick={() => setSelectedRouteId(r.id)}
                    >
                      <div className="route-card-top">
                        <strong>
                          {r.is_recommended ? "Safest · " : ""}
                          {r.label}
                        </strong>
                        <span
                          className={`score score-${riskClass(r.safety_score)}`}
                        >
                          {r.safety_score}
                        </span>
                      </div>
                      <div className="route-card-meta">
                        {formatDistance(r.distance_m)}
                        {r.duration_sec != null
                          ? ` · ${Math.round(r.duration_sec / 60)} min`
                          : ""}
                        {" · "}
                        {r.risk_indicator?.replaceAll("_", " ")}
                      </div>
                    </button>
                  ))}
                </div>
              )}

              <button
                type="button"
                className="btn btn-start"
                disabled={busy || routing || !destination || !contacts.length}
                onClick={handleStart}
              >
                {busy
                  ? "Starting…"
                  : selectedRoute
                    ? `START JOURNEY · Score ${selectedRoute.safety_score}`
                    : "START JOURNEY"}
              </button>

              <p className="planner-disclaimer">
                {crimeMeta?.disclaimer ||
                  "Demo crime data + Safety Score are historical risk indicators only — not a guarantee of safety."}
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function formatDistance(m) {
  if (m == null) return "—";
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

function riskClass(score) {
  if (score >= 75) return "good";
  if (score >= 50) return "mid";
  return "low";
}

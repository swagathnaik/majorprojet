/**
 * Public trusted-contact live tracking page (/s/:token).
 * No login — secure share link from Safe Journey start / SOS.
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import JourneyMap from "../components/JourneyMap";
import JourneyBottomSheet from "../components/JourneyBottomSheet";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";

export default function ContactTrack() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/share/${encodeURIComponent(token)}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error || "Could not load journey.");
      setData(body);
      setError("");
    } catch (err) {
      setError(err.message || "Share link unavailable.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  if (loading) {
    return (
      <main className="page center">
        <p className="muted">Loading live tracking…</p>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="page center">
        <section className="panel">
          <h1>Link unavailable</h1>
          <p className="muted">{error || "This tracking link is invalid or expired."}</p>
          <Link className="btn" to="/">
            SafeRoute home
          </Link>
        </section>
      </main>
    );
  }

  const { journey, traveler, locations, monitoring, sos, emergency } = data;
  const last = locations?.length ? locations[locations.length - 1] : null;
  const position = last
    ? { lat: last.lat, lng: last.lng, accuracy: last.accuracy }
    : null;
  const destination =
    journey.dest_lat != null
      ? { lat: journey.dest_lat, lng: journey.dest_lng, label: journey.dest_label }
      : null;
  const start =
    journey.start_lat != null
      ? { lat: journey.start_lat, lng: journey.start_lng }
      : null;

  return (
    <main className="journey-page journey-live contact-track-page">
      <section className="journey-map-layout">
        <div className="map-stage">
          <JourneyMap
            position={position}
            path={locations || []}
            destination={destination}
            start={start}
            followMode={true}
            status={journey.status}
            expectedRoute={journey.expected_route}
          />

          <div className="map-overlay-top">
            <div className="map-chip">
              <span className={`status-pill status-${journey.status}`}>
                {journey.status}
              </span>
              <strong>
                {traveler?.first_name} → {journey.dest_label}
              </strong>
            </div>
            {sos && (
              <a className="sos-btn sos-btn-compact" href="tel:112" title="Call 112">
                112
              </a>
            )}
          </div>

          <JourneyBottomSheet
            isContactView={true}
            journey={journey}
            monitoring={monitoring}
            sosAlert={sos}
            mapPosition={position}
            position={position}
            load={load}
            emergency={emergency}
            traveler={traveler}
            contactName={data.contact?.name}
            locationCount={data.location_count}
          />
        </div>
      </section>
    </main>
  );
}

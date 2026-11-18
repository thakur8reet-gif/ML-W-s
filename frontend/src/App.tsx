import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import type { LatLngBoundsExpression, LatLngExpression } from "leaflet";
import { getHealth, getTrips, predictTrip } from "./lib/api";
import type { HealthResponse, PredictionResponse, TripOption } from "./lib/api";

function FitBounds({ points }: { points: LatLngExpression[] }) {
  const map = useMap();
  useEffect(() => { if (points.length) map.fitBounds(points as LatLngBoundsExpression, { padding: [42, 42], maxZoom: 16 }); }, [map, points]);
  return null;
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [trips, setTrips] = useState<TripOption[]>([]);
  const [selectedTrip, setSelectedTrip] = useState("");
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setError("");
    try {
      const [status, availableTrips] = await Promise.all([getHealth(), getTrips()]);
      setHealth(status);
      setTrips(availableTrips);
      setSelectedTrip((current) => current || availableTrips[0]?.trip_id || "");
    } catch (e) {
      setHealth(null);
      setError(e instanceof Error ? e.message : "Could not connect to the inference API.");
    }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const reconstruct = async () => {
    if (!selectedTrip) return;
    setLoading(true); setError(""); setResult(null);
    try { setResult(await predictTrip(selectedTrip)); }
    catch (e) { setError(e instanceof Error ? e.message : "Route reconstruction failed."); }
    finally { setLoading(false); }
  };

  const gps = result?.gps_trace ?? [];
  const route = result?.predicted_route ?? [];
  const roadNetwork = result?.road_network ?? [];
  const mapPoints: LatLngExpression[] = useMemo(
    () => [...gps, ...route, ...roadNetwork.flat()].map(([lat, lon]) => [lat, lon]),
    [gps, route, roadNetwork]
  );
  const center: LatLngExpression = mapPoints[0] ?? [20.5937, 78.9629];

  return <main className="app-shell">
    <header className="topbar">
      <a className="wordmark" href="/">pathsnap<span>.</span></a>
      <div className="connection"><i className={health ? "online" : "offline"}/>{health ? "CONNECTED" : "DISCONNECTED"}</div>
    </header>
    <section className="workspace">
      <div className="intro">
        <h1>Route reconstruction</h1>
      </div>
      <div className="controls">
        <label htmlFor="trip">TRIP</label>
        <select id="trip" value={selectedTrip} onChange={(e) => { setSelectedTrip(e.target.value); setResult(null); }} disabled={!trips.length || loading}>
          {!trips.length && <option value="">No evaluation trips available</option>}
          {trips.map((trip) => <option key={trip.trip_id} value={trip.trip_id}>{trip.label ?? trip.trip_id}</option>)}
        </select>
        <button onClick={reconstruct} disabled={!health || !selectedTrip || loading}>{loading ? "Reconstructing…" : "Reconstruct route"}</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <section className="map-panel" aria-label="Route map">
        {mapPoints.length > 0 ? <MapContainer center={center} zoom={13} scrollWheelZoom className="map">
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"/>
          <FitBounds points={mapPoints}/>
          {roadNetwork.map((segment, i) => <Polyline key={i} positions={segment} pathOptions={{color:"#666666",weight:2,opacity:.62}}/>)}
          {route.length > 1 && <Polyline positions={route} pathOptions={{color:"#F2EBDD",weight:4,opacity:1,lineCap:"round",lineJoin:"round"}}/>}
          {route.map((node,i) => <CircleMarker key={i} center={node} radius={i===0 || i===route.length-1 ? 5 : 3.5} pathOptions={{color:"#F2EBDD",weight:1.5,fillColor:"#F2EBDD",fillOpacity:1}}/>)}
        </MapContainer> : <div className="map-empty"><span>MAP VIEW</span><p>{health ? "Choose an evaluation trip and reconstruct its route." : "Waiting for the inference API."}</p></div>}
      </section>
      <footer className="map-footer">
        <div className="legend">
          <span><i className="legend-line selected"/>Selected route</span>
          <span><i className="legend-node"/>Route nodes</span>
          <span><i className="legend-line unused"/>Other roads</span>
        </div>
        {result && <span className="result-meta">{route.length} route nodes{result.inference_time_ms != null ? ` · ${Math.round(result.inference_time_ms)} ms` : ""}</span>}
      </footer>
    </section>
  </main>;
}

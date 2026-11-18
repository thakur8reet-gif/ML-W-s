import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertCircle, ArrowUpRight, Check, ChevronDown,
  CircleHelp, Clock3, Cpu, Crosshair, Database, Layers3, LoaderCircle,
  MapPinned, Menu, RefreshCw, Route, Server, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import type { LatLngBoundsExpression, LatLngExpression } from "leaflet";
import { getHealth, getTrips, predictTrip } from "./lib/api";
import type { HealthResponse, PredictionResponse, TripOption } from "./lib/api";

function FitBounds({ points }: { points: LatLngExpression[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length) map.fitBounds(points as LatLngBoundsExpression, { padding: [36, 36], maxZoom: 16 });
  }, [map, points]);
  return null;
}

function formatDuration(ms?: number) {
  if (ms == null) return "—";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
}

function Metric({ label, value, detail, icon: Icon }: {
  label: string; value: string; detail: string; icon: typeof Activity;
}) {
  return <div className="metric-card">
    <div className="metric-top"><span>{label}</span><span className="metric-icon"><Icon size={16}/></span></div>
    <div className="metric-value">{value}</div>
    <div className="metric-detail">{detail}</div>
  </div>;
}

function StatusPill({ online }: { online: boolean }) {
  return <span className={`status-pill ${online ? "online" : "offline"}`}>
    <span className="status-dot"/>{online ? "API connected" : "API disconnected"}
  </span>;
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [trips, setTrips] = useState<TripOption[]>([]);
  const [selectedTrip, setSelectedTrip] = useState("");
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [loadingTrips, setLoadingTrips] = useState(false);
  const [predicting, setPredicting] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeLayer, setActiveLayer] = useState({ gps: true, network: true, predicted: true });

  const refresh = useCallback(async () => {
    setLoadingTrips(true);
    setError("");
    try {
      const [h, t] = await Promise.all([getHealth(), getTrips()]);
      setHealth(h);
      setTrips(t);
      if (!selectedTrip && t.length) setSelectedTrip(t[0].trip_id);
    } catch (e) {
      setHealth(null);
      setError(e instanceof Error ? e.message : "Unable to connect to the PathSnap API.");
    } finally {
      setLoadingTrips(false);
    }
  }, [selectedTrip]);

  useEffect(() => { void refresh(); }, []); // Initial connection check only.

  const runPrediction = async () => {
    if (!selectedTrip) return;
    setPredicting(true);
    setError("");
    setResult(null);
    try {
      setResult(await predictTrip(selectedTrip));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Route reconstruction failed.");
    } finally {
      setPredicting(false);
    }
  };

  const filteredTrips = useMemo(() => trips.filter((trip) =>
    trip.trip_id.toLowerCase().includes(query.toLowerCase())
  ), [trips, query]);

  const gps = result?.gps_trace ?? [];
  const predicted = result?.predicted_route ?? [];
  const allPoints: LatLngExpression[] = [...gps, ...predicted].map(([lat, lon]) => [lat, lon]);
  const center: LatLngExpression = allPoints[0] ?? [20.5937, 78.9629];

  return <div className="app-shell">
    <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
      <div className="brand">
        <div className="brand-mark"><Route size={21}/></div>
        <div><div className="brand-name">pathsnap<span>.</span></div><div className="brand-sub">ROUTE INTELLIGENCE</div></div>
        <button className="icon-button mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close navigation"><X size={18}/></button>
      </div>
      <div className="workspace-label">WORKSPACE</div>
      <nav className="nav-list">
        <button className="nav-item active"><Crosshair size={17}/> Evaluation console <span className="nav-indicator"/></button>
        <button className="nav-item" onClick={() => document.getElementById("map-panel")?.scrollIntoView({ behavior: "smooth" })}><MapPinned size={17}/> Route explorer</button>
        <button className="nav-item" onClick={() => document.getElementById("system-panel")?.scrollIntoView({ behavior: "smooth" })}><Server size={17}/> System status</button>
      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-card">
          <div className="sidebar-card-icon"><ShieldCheck size={17}/></div>
          <div className="sidebar-card-title">Evaluation safe</div>
          <p>Predictions are requested from the connected inference API. No ground-truth labels are shown.</p>
        </div>
        <div className="sidebar-footer"><span className="footer-dot"/> PATHSNAP / BUILD 0.1.0</div>
      </div>
    </aside>

    {sidebarOpen && <button className="mobile-scrim" onClick={() => setSidebarOpen(false)} aria-label="Close navigation"/>}

    <main className="main-content">
      <header className="topbar">
        <div className="topbar-left">
          <button className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Menu size={19}/></button>
          <div className="breadcrumb">Workspace <span>/</span> <strong>Evaluation console</strong></div>
        </div>
        <div className="topbar-right">
          <StatusPill online={Boolean(health)}/>
          <button className="icon-button refresh-button" onClick={() => void refresh()} disabled={loadingTrips} aria-label="Refresh API status"><RefreshCw size={16} className={loadingTrips ? "spin" : ""}/></button>
          <div className="avatar">PS</div>
        </div>
      </header>

      <div className="page-wrap">
        <section className="page-heading">
          <div>
            <div className="eyebrow"><span className="eyebrow-line"/> DISTRIBUTED MAP-MATCHING SYSTEM</div>
            <h1>Evaluation <span>console</span></h1>
            <p className="page-description">Reconstruct a vehicle's path from noisy GPS observations and inspect the predicted road sequence.</p>
          </div>
          <div className="heading-meta"><div className="meta-label">SESSION</div><div className="meta-value"><span className="live-dot"/> READY WHEN YOU ARE</div></div>
        </section>

        {error && <div className="alert alert-error"><AlertCircle size={17}/><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error"><X size={16}/></button></div>}

        <section className="control-panel">
          <div className="control-copy">
            <div className="section-kicker">01 / SELECT INPUT</div>
            <h2>Choose an evaluation trip</h2>
            <p>Select one of the trips exposed by the evaluation API.</p>
          </div>
          <div className="trip-controls">
            <label className="select-label" htmlFor="trip-select">TRIP IDENTIFIER</label>
            <div className="select-wrap">
              <select id="trip-select" value={selectedTrip} onChange={(e) => { setSelectedTrip(e.target.value); setResult(null); }} disabled={!trips.length || predicting}>
                {trips.length === 0 && <option value="">Waiting for API trip list…</option>}
                {trips.map((trip) => <option key={trip.trip_id} value={trip.trip_id}>{trip.label ?? trip.trip_id}</option>)}
              </select><ChevronDown size={16}/>
            </div>
            <button className="primary-button" onClick={runPrediction} disabled={!selectedTrip || predicting || !health}>
              {predicting ? <><LoaderCircle size={17} className="spin"/> Reconstructing</> : <><Sparkles size={17}/> Reconstruct route <ArrowUpRight size={16}/></>}
            </button>
          </div>
        </section>

        <section className="metrics-grid">
          <Metric label="GPS observations" value={result ? gps.length.toLocaleString() : "—"} detail="Points in selected trace" icon={Crosshair}/>
          <Metric label="Predicted road arcs" value={result ? predicted.length.toLocaleString() : "—"} detail="Decoded route sequence" icon={Route}/>
          <Metric label="Inference time" value={formatDuration(result?.inference_time_ms)} detail="Backend-reported duration" icon={Clock3}/>
          <Metric label="Decoder" value={result?.decoder ?? "—"} detail="Active reconstruction method" icon={Cpu}/>
        </section>

        <section className="map-section" id="map-panel">
          <div className="panel-heading">
            <div><div className="section-kicker">02 / GEOSPATIAL OUTPUT</div><h2>Route reconstruction</h2><p>Compare the observed trajectory with the model's predicted road path.</p></div>
            <div className="map-tools"><span className="map-status"><span className="status-dot"/> {result ? "RESULT LOADED" : "AWAITING RESULT"}</span></div>
          </div>
          <div className="map-layout">
            <div className="map-frame">
              {result && (gps.length || predicted.length) ? <MapContainer center={center} zoom={13} scrollWheelZoom className="leaflet-map">
                <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
                <FitBounds points={allPoints}/>
                {activeLayer.gps && gps.length > 0 && <Polyline positions={gps.map(([lat, lon]) => [lat, lon])} pathOptions={{ color: "#49a6ff", weight: 3, opacity: 0.9, dashArray: "5 7" }}/ >}
                {activeLayer.predicted && predicted.length > 0 && <Polyline positions={predicted.map(([lat, lon]) => [lat, lon])} pathOptions={{ color: "#f59e0b", weight: 5, opacity: 0.95 }}/>}
                {activeLayer.gps && gps.length > 0 && <CircleMarker center={gps[0]} radius={6} pathOptions={{ color: "#22c55e", fillColor: "#22c55e", fillOpacity: 1 }} />}
                {activeLayer.gps && gps.length > 1 && <CircleMarker center={gps[gps.length - 1]} radius={6} pathOptions={{ color: "#ef4444", fillColor: "#ef4444", fillOpacity: 1 }} />}
              </MapContainer> : <div className="map-empty">
                <div className="map-empty-grid"/>
                <div className="map-empty-content"><div className="map-empty-icon"><MapPinned size={26}/></div><h3>Your route map will appear here</h3><p>Connect the inference API and reconstruct an evaluation trip to view GPS observations and the predicted route.</p><span className="map-empty-coords">LAT ———— &nbsp; LON ————</span></div>
              </div>}
              <div className="map-attribution">PATHSNAP / GEOSPATIAL VIEW</div>
            </div>
            <aside className="map-side">
              <div className="side-block"><div className="side-title">MAP LAYERS <Layers3 size={15}/></div>
                {[
                  ["gps", "Observed GPS trace", "blue"],
                  ["predicted", "Predicted route", "orange"],
                ].map(([key, label, color]) => <label className="layer-row" key={key}><span className={`layer-swatch ${color}`}/><span>{label}</span><input type="checkbox" checked={activeLayer[key as keyof typeof activeLayer]} onChange={(e) => setActiveLayer((old) => ({ ...old, [key]: e.target.checked }))}/></label>)}
                <div className="layer-row muted-layer"><span className="layer-swatch grey"/><span>Road network</span><span className="layer-note">API data</span></div>
              </div>
              <div className="side-divider"/>
              <div className="side-block"><div className="side-title">ROUTE SUMMARY <Activity size={15}/></div>
                <div className="summary-row"><span>Selected trip</span><strong>{selectedTrip || "—"}</strong></div>
                <div className="summary-row"><span>GPS samples</span><strong>{result ? gps.length : "—"}</strong></div>
                <div className="summary-row"><span>Route segments</span><strong>{result ? predicted.length : "—"}</strong></div>
                <div className="summary-row"><span>Model status</span><strong className={result ? "text-green" : ""}>{result ? "Completed" : "Pending"}</strong></div>
              </div>
              <div className="map-note"><CircleHelp size={15}/><span>Reference ground truth is intentionally not exposed in the evaluator interface.</span></div>
            </aside>
          </div>
        </section>

        <section className="bottom-grid">
          <div className="data-panel">
            <div className="panel-heading compact"><div><div className="section-kicker">03 / INFERENCE TRACE</div><h2>Predicted route sequence</h2></div><span className="count-chip">{predicted.length} ARCS</span></div>
            {predicted.length ? <div className="arc-list">{predicted.slice(0, 12).map((point, index) => <div className="arc-row" key={index}><span className="arc-index">{String(index + 1).padStart(2, "0")}</span><span className="arc-name">Road segment {index + 1}</span><span className="arc-coord">{point[0].toFixed(5)}, {point[1].toFixed(5)}</span><Check size={15} className="arc-check"/></div>)}</div> : <div className="empty-inline"><Route size={19}/><span>Route segments will populate after a successful inference.</span></div>}
          </div>
          <div className="system-panel" id="system-panel">
            <div className="panel-heading compact"><div><div className="section-kicker">04 / CONNECTIVITY</div><h2>System status</h2></div><Activity size={17} className="system-icon"/></div>
            <div className="system-row"><span><Server size={15}/> Inference API</span><strong className={health ? "text-green" : "text-red"}>{health ? "Online" : "Offline"}</strong></div>
            <div className="system-row"><span><Database size={15}/> Evaluation trips</span><strong>{trips.length ? `${trips.length} available` : "Not loaded"}</strong></div>
            <div className="system-row"><span><Cpu size={15}/> Model runtime</span><strong>{health?.model_name ?? "Not reported"}</strong></div>
            <button className="text-button" onClick={() => void refresh()} disabled={loadingTrips}><RefreshCw size={14}/> Refresh connection</button>
          </div>
        </section>
        <footer className="page-footer"><span>PATHSNAP <span className="footer-separator">/</span> DISTRIBUTED MAP-MATCHING</span><span>Built for evaluation · <span className="footer-version">v0.1.0</span></span></footer>
      </div>
    </main>
  </div>;
}

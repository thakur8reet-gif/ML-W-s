const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export interface HealthResponse {
  status: string;
  model_name?: string;
  version?: string;
}

export interface TripOption {
  trip_id: string;
  label?: string;
}

export type LatLon = [number, number];

export interface PredictionResponse {
  trip_id: string;
  gps_trace: LatLon[];
  predicted_route: LatLon[];
  road_network?: LatLon[][];
  inference_time_ms?: number;
  decoder?: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error(`Cannot reach API at ${API_BASE}. Check that the FastAPI server is running and VITE_API_BASE_URL is correct.`);
  }

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`API request failed (${response.status}): ${body || response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function getTrips(): Promise<TripOption[]> {
  const payload = await request<{ trips: TripOption[] }>("/api/evaluation/trips");
  return payload.trips;
}

export async function predictTrip(tripId: string): Promise<PredictionResponse> {
  return request<PredictionResponse>("/api/evaluation/predict", {
    method: "POST",
    body: JSON.stringify({ trip_id: tripId }),
  });
}

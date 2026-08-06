/**
 * API helper – talks to the Flask backend.
 * Base URL comes from VITE_API_BASE_URL in frontend/.env
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";
console.log("API_BASE =", API_BASE);

/**
 * Perform a JSON request to the Flask API.
 * Automatically attaches JWT when available.
 */
export async function apiRequest(path, options = {}) {
  const { method = "GET", body, token, headers = {} } = options;

  const finalHeaders = {
    "Content-Type": "application/json",
    ...headers,
  };

  if (token) {
    finalHeaders.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: finalHeaders,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error(
      "Cannot reach SafeRoute API. Is the Flask server running on port 5000?"
    );
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message = data?.error || `Request failed (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export const authApi = {
  register: (payload) =>
    apiRequest("/auth/register", { method: "POST", body: payload }),
  login: (payload) =>
    apiRequest("/auth/login", { method: "POST", body: payload }),
  me: (token) => apiRequest("/auth/me", { token }),
  updateMe: (token, payload) =>
    apiRequest("/auth/me", { method: "PUT", body: payload, token }),
};

export const contactsApi = {
  list: (token) => apiRequest("/contacts", { token }),
  create: (token, payload) =>
    apiRequest("/contacts", { method: "POST", body: payload, token }),
  update: (token, id, payload) =>
    apiRequest(`/contacts/${id}`, { method: "PUT", body: payload, token }),
  setPrimary: (token, id) =>
    apiRequest(`/contacts/${id}/primary`, { method: "PATCH", token }),
  remove: (token, id) =>
    apiRequest(`/contacts/${id}`, { method: "DELETE", token }),
};

export const journeysApi = {
  active: (token) => apiRequest("/journeys/active", { token }),
  start: (token, payload = {}) =>
    apiRequest("/journeys", { method: "POST", body: payload, token }),
  get: (token, id) => apiRequest(`/journeys/${id}`, { token }),
  pause: (token, id) =>
    apiRequest(`/journeys/${id}/pause`, { method: "POST", token }),
  resume: (token, id) =>
    apiRequest(`/journeys/${id}/resume`, { method: "POST", token }),
  end: (token, id) =>
    apiRequest(`/journeys/${id}/end`, { method: "POST", token }),
  cancel: (token, id) =>
    apiRequest(`/journeys/${id}/cancel`, { method: "POST", token }),
  sos: (token, id, payload = {}) =>
    apiRequest(`/journeys/${id}/sos`, { method: "POST", body: payload, token }),
  postLocation: (token, id, payload) =>
    apiRequest(`/journeys/${id}/locations`, {
      method: "POST",
      body: payload,
      token,
    }),
  listLocations: (token, id) =>
    apiRequest(`/journeys/${id}/locations`, { token }),
  monitoring: (token, id) =>
    apiRequest(`/journeys/${id}/monitoring`, { token }),
  anomalies: (token, id) =>
    apiRequest(`/journeys/${id}/anomalies`, { token }),
  simulateAnomaly: (token, id, type) =>
    apiRequest(`/journeys/${id}/demo/simulate-anomaly`, {
      method: "POST",
      body: { type },
      token,
    }),
};

export const safetyApi = {
  respond: (token, checkId, payload) =>
    apiRequest(`/safety-checks/${checkId}/respond`, {
      method: "POST",
      body: payload,
      token,
    }),
  cancelCountdown: (token, checkId) =>
    apiRequest(`/safety-checks/${checkId}/cancel-countdown`, {
      method: "POST",
      token,
    }),
  timeout: (token, checkId, payload = {}) =>
    apiRequest(`/safety-checks/${checkId}/timeout`, {
      method: "POST",
      body: payload,
      token,
    }),
};

export const mapsApi = {
  crimeHotspots: (token) => apiRequest("/maps/crime-hotspots", { token }),
  geocode: (token, q) =>
    apiRequest(`/maps/geocode?q=${encodeURIComponent(q)}`, { token }),
  saferRoutes: (token, payload) =>
    apiRequest("/maps/safer-routes", { method: "POST", body: payload, token }),
};

export const shareApi = {
  get: (shareToken) => apiRequest(`/share/${encodeURIComponent(shareToken)}`),
};

export const healthApi = {
  check: async () => {
    const healthUrl = API_BASE.startsWith("http")
      ? `${API_BASE.replace(/\/api$/, "")}/api/health`
      : "/api/health";
    const res = await fetch(healthUrl);
    return res.json();
  },
};

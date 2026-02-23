const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export function getToken() {
  return localStorage.getItem("token") || "";
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers || {});
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const requestPath = path.startsWith("/") ? path : `/${path}`;
  const url = API_BASE_URL ? `${API_BASE_URL}${requestPath}` : requestPath;
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail.map((d: { msg?: string }) => d.msg ?? String(d)).join("; ")
      : detail || "Request failed";
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

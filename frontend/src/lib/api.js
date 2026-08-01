export async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") && text ? JSON.parse(text) : text;

  if (!response.ok) {
    const message =
      typeof payload === "object" ? payload.detail || payload.error : payload;
    const error = new Error(message || `Request failed: ${response.status}`);
    error.status = response.status;
    throw error;
  }

  return payload;
}

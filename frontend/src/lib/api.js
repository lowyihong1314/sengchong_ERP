export async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") && text ? JSON.parse(text) : text;

  if (!response.ok) {
    // A rejection from nginx rather than the app -- 413, 502 -- comes back as
    // an HTML error page. Putting that in a status bar shows the user a screen
    // of markup, so anything that is not JSON is reported by status alone.
    const message =
      typeof payload === "object"
        ? payload.detail || payload.error
        : contentType.includes("text/html")
        ? ""
        : payload;
    const error = new Error(message || `Request failed: ${response.status}`);
    error.status = response.status;
    throw error;
  }

  return payload;
}

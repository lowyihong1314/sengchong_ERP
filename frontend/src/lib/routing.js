import { ERP_OWNED_MODULES, moduleKeys } from "../constants.js";
import { MODULES } from "../modules.js";

export function getModuleListPath(moduleKey, options = {}) {
  const refreshQuery = options.refresh ? "?refresh=1" : "";
  const base = ERP_OWNED_MODULES.has(moduleKey) ? "/api" : "/api/autocount";
  return `${base}/${moduleKey}${refreshQuery}`;
}

export function getModuleDetailPath(moduleKey, key, options = {}) {
  const refreshQuery = options.refresh ? "?refresh=1" : "";
  const encodedKey = encodeURIComponent(key);
  const base = ERP_OWNED_MODULES.has(moduleKey) ? "/api" : "/api/autocount";
  return `${base}/${moduleKey}/${encodedKey}${refreshQuery}`;
}

export function getModuleCreatePath(moduleKey) {
  const base = ERP_OWNED_MODULES.has(moduleKey) ? "/api" : "/api/autocount";
  return `${base}/${moduleKey}`;
}

export function getModuleUpdatePath(moduleKey, key) {
  const base = ERP_OWNED_MODULES.has(moduleKey) ? "/api" : "/api/autocount";
  return `${base}/${moduleKey}/${encodeURIComponent(key)}`;
}

export function getLinkedProjectsPath(moduleKey, key) {
  const params = new URLSearchParams({ module: moduleKey, key });
  return `/api/projects/by-document?${params.toString()}`;
}

export function getDetailCacheKey(moduleKey, key) {
  return `${moduleKey}:${key}`;
}

export function getEmptyStage() {
  return {
    rows: [],
    query: "",
    detail: null,
    detailKey: "",
    view: "list",
    status: { tone: "", text: "Ready" },
    formData: null,
    loaded: false,
  };
}

export function normalizeRoute(route = {}) {
  const moduleKey = moduleKeys.includes(route.moduleKey) ? route.moduleKey : "quotations";
  const key = String(route.key || "").trim();
  const supportsDetail = !MODULES[moduleKey]?.system;
  const view = supportsDetail && route.view === "detail" && key ? "detail" : "list";

  // Filters ride in the URL so a filtered list is a link somebody can send:
  // ?module=documents&class=salary is a working address, not a screen state
  // that has to be reproduced by clicking.
  return {
    moduleKey,
    view,
    key: view === "detail" ? key : "",
    query: String(route.query || ""),
    docClass: String(route.docClass || ""),
    docStatus: String(route.docStatus || ""),
  };
}

export function getRouteFromUrl() {
  if (typeof window === "undefined") {
    return normalizeRoute();
  }

  const params = new URLSearchParams(window.location.search);
  const key = params.get("key") || "";
  return normalizeRoute({
    moduleKey: params.get("module") || params.get("m") || "quotations",
    view: params.get("view") || (key ? "detail" : "list"),
    key,
    query: params.get("q") || "",
    docClass: params.get("class") || "",
    docStatus: params.get("status") || "",
  });
}

export function getRouteUrl(route) {
  const normalized = normalizeRoute(route);
  const params = new URLSearchParams();
  params.set("module", normalized.moduleKey);
  if (normalized.view !== "list") params.set("view", normalized.view);
  if (normalized.key) params.set("key", normalized.key);
  if (normalized.query) params.set("q", normalized.query);
  if (normalized.docClass) params.set("class", normalized.docClass);
  if (normalized.docStatus) params.set("status", normalized.docStatus);
  return `${window.location.pathname}?${params.toString()}`;
}

export function replaceRouteUrl(route) {
  if (typeof window === "undefined") return;

  const nextUrl = getRouteUrl(route);
  const currentUrl = `${window.location.pathname}${window.location.search}`;
  if (nextUrl !== currentUrl) {
    window.history.replaceState({ route: normalizeRoute(route) }, "", nextUrl);
  }
}

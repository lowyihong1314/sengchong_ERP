import { isFlagOn, readValue, toNumber } from "./format.js";

export function normalizeRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.rows)) return payload.rows;
  if (Array.isArray(payload?.result)) return payload.result;
  if (payload && typeof payload === "object") return [payload];
  return [];
}

export function normalizeDetail(payload) {
  if (payload?.data && typeof payload.data === "object") return payload.data;
  return payload || null;
}

export function normalizeWebsiteContent(payload) {
  return {
    services: Array.isArray(payload?.services) ? payload.services : [],
    contacts: Array.isArray(payload?.contacts) ? payload.contacts : [],
    footer: payload?.footer && typeof payload.footer === "object" ? payload.footer : {},
  };
}

export function normalizeWebsiteGallery(payload) {
  return normalizeRows(payload).filter((photo) => readValue(photo, "id"));
}

export function normalizeWebsiteAudit(payload) {
  return normalizeRows(payload).filter((entry) => readValue(entry, "id"));
}

export function normalizeWebsitePreview(payload) {
  return {
    services: Array.isArray(payload?.services) ? payload.services : [],
    contacts: Array.isArray(payload?.contacts) ? payload.contacts : [],
    footer: payload?.footer && typeof payload.footer === "object" ? payload.footer : {},
    gallery: Array.isArray(payload?.gallery) ? payload.gallery : [],
    galleryCount: toNumber(payload?.galleryCount, 0),
  };
}

export function normalizeWebsiteAssets(payload) {
  return normalizeRows(payload).filter((asset) => readValue(asset, "filename"));
}

export function getWebsiteGallerySummary(photos) {
  return (photos || []).reduce(
    (summary, photo) => {
      summary.count += 1;
      if (isFlagOn(readValue(photo, "isPublic"))) summary.publicCount += 1;
      if (isFlagOn(readValue(photo, "websiteVisible"))) summary.websiteVisibleCount += 1;
      return summary;
    },
    { count: 0, publicCount: 0, websiteVisibleCount: 0 }
  );
}

export function formatWebsiteAuditAction(action) {
  const labels = {
    legacy_product_imported: "Imported",
    photo_cover_changed: "Cover",
    photo_metadata_changed: "Metadata",
    photo_public_disabled: "Private",
    photo_public_enabled: "Public",
    photo_sort_changed: "Sort",
    photo_website_hidden: "Hidden",
    photo_website_published: "Published",
    website_contact_changed: "Contact",
    website_footer_changed: "Footer",
    website_service_changed: "Service",
  };
  return labels[action] || action || "Updated";
}

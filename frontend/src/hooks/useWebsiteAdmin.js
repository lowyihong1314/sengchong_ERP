import React from "react";

import { requestJson } from "../lib/api.js";
import { clone, isFlagOn, readValue } from "../lib/format.js";
import {
  getWebsiteGallerySummary,
  normalizeWebsiteAssets,
  normalizeWebsiteAudit,
  normalizeWebsiteContent,
  normalizeWebsiteGallery,
  normalizeWebsitePreview,
} from "../lib/normalize.js";

/**
 * Owns every piece of "ERP manages sengchong.com" state: content draft, gallery,
 * audit log, public preview, and service/contact image assets.
 *
 * The caller supplies the shared session plumbing (token, auth headers, status
 * line, module stage cache) and gets back the state plus its loaders/savers.
 */
export function useWebsiteAdmin({
  token,
  activeModuleRef,
  authHeaders,
  handleAuthError,
  setStatus,
  updateModuleStage,
}) {
  const [websiteContent, setWebsiteContent] = React.useState(null);
  const [websiteContentDraft, setWebsiteContentDraft] = React.useState(null);
  const [websiteGallery, setWebsiteGallery] = React.useState([]);
  const [websiteGalleryDraft, setWebsiteGalleryDraft] = React.useState([]);
  const [websiteGalleryLoading, setWebsiteGalleryLoading] = React.useState(false);
  const [websiteAuditLog, setWebsiteAuditLog] = React.useState([]);
  const [websiteAuditLoading, setWebsiteAuditLoading] = React.useState(false);
  const [websitePreview, setWebsitePreview] = React.useState(null);
  const [websitePreviewLoading, setWebsitePreviewLoading] = React.useState(false);
  const [websiteAssets, setWebsiteAssets] = React.useState({ service: [], contact: [] });
  const [websiteAssetsLoading, setWebsiteAssetsLoading] = React.useState(false);
  const [websiteAssetUploading, setWebsiteAssetUploading] = React.useState("");
  const [websiteContentLoading, setWebsiteContentLoading] = React.useState(false);
  const [websiteContentSaving, setWebsiteContentSaving] = React.useState(false);

  const loadWebsiteGallery = React.useCallback(
    async (options = {}) => {
      if (!token) return [];

      try {
        setWebsiteGalleryLoading(true);
        if (options.showStatus !== false) {
          setStatus({ tone: "", text: "Loading website gallery..." });
        }
        const payload = await requestJson("/api/website-gallery", {
          headers: authHeaders(),
        });
        const nextGallery = normalizeWebsiteGallery(payload);
        setWebsiteGallery(nextGallery);
        setWebsiteGalleryDraft(clone(nextGallery));
        if (options.showStatus !== false) {
          const summary = getWebsiteGallerySummary(nextGallery);
          setStatus({
            tone: "ok",
            text: `${summary.websiteVisibleCount} website photo${
              summary.websiteVisibleCount === 1 ? "" : "s"
            }`,
          });
        }
        return nextGallery;
      } catch (error) {
        handleAuthError(error);
        if (options.showStatus !== false) {
          setStatus({ tone: "error", text: error.message });
        }
        return [];
      } finally {
        setWebsiteGalleryLoading(false);
      }
    },
    [authHeaders, handleAuthError, token]
  );

  const loadWebsiteAuditLog = React.useCallback(
    async (options = {}) => {
      if (!token) return [];

      try {
        setWebsiteAuditLoading(true);
        const payload = await requestJson("/api/website-audit-log?limit=80", {
          headers: authHeaders(),
        });
        const nextAudit = normalizeWebsiteAudit(payload);
        setWebsiteAuditLog(nextAudit);
        return nextAudit;
      } catch (error) {
        handleAuthError(error);
        if (options.showStatus !== false) {
          setStatus({ tone: "error", text: error.message });
        }
        return [];
      } finally {
        setWebsiteAuditLoading(false);
      }
    },
    [authHeaders, handleAuthError, token]
  );

  const loadWebsitePreview = React.useCallback(
    async (options = {}) => {
      if (!token) return null;

      try {
        setWebsitePreviewLoading(true);
        if (options.showStatus !== false) {
          setStatus({ tone: "", text: "Loading website preview..." });
        }
        const payload = await requestJson("/public-api/website");
        const nextPreview = normalizeWebsitePreview(payload);
        setWebsitePreview(nextPreview);
        if (options.showStatus !== false) {
          setStatus({
            tone: "ok",
            text: `${nextPreview.galleryCount} public website photo${
              nextPreview.galleryCount === 1 ? "" : "s"
            }`,
          });
        }
        return nextPreview;
      } catch (error) {
        if (options.showStatus !== false) {
          setStatus({ tone: "error", text: error.message });
        }
        return null;
      } finally {
        setWebsitePreviewLoading(false);
      }
    },
    [token]
  );

  const loadWebsiteAssets = React.useCallback(
    async (options = {}) => {
      if (!token) return { service: [], contact: [] };

      try {
        setWebsiteAssetsLoading(true);
        if (options.showStatus !== false) {
          setStatus({ tone: "", text: "Loading website images..." });
        }
        const [servicePayload, contactPayload] = await Promise.all([
          requestJson("/api/website-content/assets/service", {
            headers: authHeaders(),
          }),
          requestJson("/api/website-content/assets/contact", {
            headers: authHeaders(),
          }),
        ]);
        const nextAssets = {
          service: normalizeWebsiteAssets(servicePayload),
          contact: normalizeWebsiteAssets(contactPayload),
        };
        setWebsiteAssets(nextAssets);
        if (options.showStatus !== false) {
          setStatus({
            tone: "ok",
            text: `${nextAssets.service.length} service image${
              nextAssets.service.length === 1 ? "" : "s"
            } / ${nextAssets.contact.length} contact image${
              nextAssets.contact.length === 1 ? "" : "s"
            }`,
          });
        }
        return nextAssets;
      } catch (error) {
        handleAuthError(error);
        if (options.showStatus !== false) {
          setStatus({ tone: "error", text: error.message });
        }
        return { service: [], contact: [] };
      } finally {
        setWebsiteAssetsLoading(false);
      }
    },
    [authHeaders, handleAuthError, token]
  );

  const loadWebsiteContent = React.useCallback(
    async (options = {}) => {
      if (!token) return;

      try {
        setWebsiteContentLoading(true);
        setWebsiteGalleryLoading(true);
        setWebsiteAuditLoading(true);
        setWebsitePreviewLoading(true);
        setWebsiteAssetsLoading(true);
        if (options.showStatus !== false) {
          setStatus({ tone: "", text: "Loading website content..." });
        }
        const [
          payload,
          galleryPayload,
          auditPayload,
          previewPayload,
          serviceAssetsPayload,
          contactAssetsPayload,
        ] = await Promise.all([
          requestJson("/api/website-content", {
            headers: authHeaders(),
          }),
          requestJson("/api/website-gallery", {
            headers: authHeaders(),
          }),
          requestJson("/api/website-audit-log?limit=80", {
            headers: authHeaders(),
          }),
          requestJson("/public-api/website"),
          requestJson("/api/website-content/assets/service", {
            headers: authHeaders(),
          }),
          requestJson("/api/website-content/assets/contact", {
            headers: authHeaders(),
          }),
        ]);
        const nextContent = normalizeWebsiteContent(payload);
        const nextGallery = normalizeWebsiteGallery(galleryPayload);
        const nextAudit = normalizeWebsiteAudit(auditPayload);
        const nextPreview = normalizeWebsitePreview(previewPayload);
        const nextAssets = {
          service: normalizeWebsiteAssets(serviceAssetsPayload),
          contact: normalizeWebsiteAssets(contactAssetsPayload),
        };
        const gallerySummary = getWebsiteGallerySummary(nextGallery);
        const nextStatus = {
          tone: "ok",
          text: `Website content loaded / ${gallerySummary.websiteVisibleCount} website photo${
            gallerySummary.websiteVisibleCount === 1 ? "" : "s"
          }`,
        };
        setWebsiteContent(nextContent);
        setWebsiteContentDraft(clone(nextContent));
        setWebsiteGallery(nextGallery);
        setWebsiteGalleryDraft(clone(nextGallery));
        setWebsiteAuditLog(nextAudit);
        setWebsitePreview(nextPreview);
        setWebsiteAssets(nextAssets);
        updateModuleStage("website-content", {
          rows: [],
          loaded: true,
          status: nextStatus,
        });
        if (activeModuleRef.current === "website-content" && options.showStatus !== false) {
          setStatus(nextStatus);
        }
      } catch (error) {
        handleAuthError(error);
        setStatus({ tone: "error", text: error.message });
      } finally {
        setWebsiteContentLoading(false);
        setWebsiteGalleryLoading(false);
        setWebsiteAuditLoading(false);
        setWebsitePreviewLoading(false);
        setWebsiteAssetsLoading(false);
      }
    },
    [authHeaders, handleAuthError, token, updateModuleStage]
  );

  function applyWebsiteContentPayload(payload, message = "Website content saved") {
    const nextContent = normalizeWebsiteContent(payload);
    setWebsiteContent(nextContent);
    setWebsiteContentDraft(clone(nextContent));
    const nextStatus = { tone: "ok", text: message };
    setStatus(nextStatus);
    updateModuleStage("website-content", {
      rows: [],
      loaded: true,
      status: nextStatus,
    });
  }

  function updateWebsiteFooterField(name, value) {
    setWebsiteContentDraft((current) => {
      const next = normalizeWebsiteContent(current || websiteContent || {});
      return {
        ...next,
        footer: {
          ...next.footer,
          [name]: value,
        },
      };
    });
  }

  function updateWebsiteServiceField(serviceNo, name, value) {
    setWebsiteContentDraft((current) => {
      const next = normalizeWebsiteContent(current || websiteContent || {});
      return {
        ...next,
        services: next.services.map((service) =>
          Number(service.no) === Number(serviceNo) ? { ...service, [name]: value } : service
        ),
      };
    });
  }

  function updateWebsiteContactField(contactNo, name, value) {
    setWebsiteContentDraft((current) => {
      const next = normalizeWebsiteContent(current || websiteContent || {});
      return {
        ...next,
        contacts: next.contacts.map((contact) =>
          Number(contact.no) === Number(contactNo) ? { ...contact, [name]: value } : contact
        ),
      };
    });
  }

  function updateWebsiteGalleryPhotoField(photoId, patch) {
    setWebsiteGalleryDraft((current) =>
      normalizeWebsiteGallery(current || websiteGallery).map((photo) => {
        if (readValue(photo, "id") !== photoId) return photo;
        const next = { ...photo, ...patch };
        if (Object.prototype.hasOwnProperty.call(patch, "isPublic") && !patch.isPublic) {
          next.websiteVisible = false;
        }
        if (patch.websiteVisible) {
          next.isPublic = true;
        }
        return next;
      })
    );
  }

  async function uploadWebsiteAsset(kind, file, ownerNo = "") {
    const assetKind = String(kind || "").trim();
    if (!["service", "contact"].includes(assetKind) || !file) return null;

    const uploadKey = `${assetKind}:${ownerNo || ""}`;
    const formData = new FormData();
    formData.append("image", file);

    try {
      setWebsiteAssetUploading(uploadKey);
      setStatus({ tone: "", text: "Uploading website image..." });
      const asset = await requestJson(`/api/website-content/assets/${assetKind}`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      setWebsiteAssets((current) => ({
        ...current,
        [assetKind]: normalizeWebsiteAssets({
          data: [...(current[assetKind] || []), asset],
        }).sort((left, right) =>
          String(readValue(left, "filename")).localeCompare(String(readValue(right, "filename")))
        ),
      }));
      setStatus({ tone: "ok", text: "Image uploaded; save the row to publish it" });
      return asset;
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      return null;
    } finally {
      setWebsiteAssetUploading("");
    }
  }

  async function saveWebsiteGalleryPhoto(photoId) {
    const photo = normalizeWebsiteGallery(websiteGalleryDraft || websiteGallery).find(
      (item) => readValue(item, "id") === photoId
    );
    if (!photo) return;

    try {
      setWebsiteContentSaving(true);
      setStatus({ tone: "", text: "Saving gallery photo..." });
      await requestJson(`/api/project-photos/${encodeURIComponent(photoId)}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          serviceCategory: readValue(photo, "serviceCategory"),
          caption: readValue(photo, "caption"),
          altText: readValue(photo, "altText"),
          sortOrder: readValue(photo, "sortOrder"),
          isPublic: isFlagOn(readValue(photo, "isPublic")),
          websiteVisible: isFlagOn(readValue(photo, "websiteVisible")),
        }),
      });
      await loadWebsiteGallery({ showStatus: false });
      await loadWebsiteAuditLog({ showStatus: false });
      await loadWebsitePreview({ showStatus: false });
      setStatus({ tone: "ok", text: "Gallery photo saved" });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setWebsiteContentSaving(false);
    }
  }

  async function importLegacyWebsiteGallery() {
    try {
      setWebsiteContentSaving(true);
      setStatus({ tone: "", text: "Importing legacy product images..." });
      const payload = await requestJson("/api/website-gallery/import-legacy-products", {
        method: "POST",
        headers: authHeaders(),
      });
      const nextGallery = normalizeWebsiteGallery(payload.gallery || {});
      setWebsiteGallery(nextGallery);
      setWebsiteGalleryDraft(clone(nextGallery));
      await loadWebsiteAuditLog({ showStatus: false });
      await loadWebsitePreview({ showStatus: false });
      setStatus({
        tone: "ok",
        text: `Imported ${payload.importedCount || 0} photo${
          payload.importedCount === 1 ? "" : "s"
        } / skipped ${payload.skippedCount || 0}`,
      });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setWebsiteContentSaving(false);
    }
  }

  async function saveWebsiteFooter() {
    const content = normalizeWebsiteContent(websiteContentDraft || websiteContent || {});
    try {
      setWebsiteContentSaving(true);
      setStatus({ tone: "", text: "Saving website footer..." });
      const payload = await requestJson("/api/website-content/footer", {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(content.footer),
      });
      applyWebsiteContentPayload(payload, "Website footer saved");
      await loadWebsiteAuditLog({ showStatus: false });
      await loadWebsitePreview({ showStatus: false });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setWebsiteContentSaving(false);
    }
  }

  async function saveWebsiteService(serviceNo) {
    const content = normalizeWebsiteContent(websiteContentDraft || websiteContent || {});
    const service = content.services.find((item) => Number(item.no) === Number(serviceNo));
    if (!service) return;

    try {
      setWebsiteContentSaving(true);
      setStatus({ tone: "", text: "Saving service..." });
      const payload = await requestJson(`/api/website-content/services/${serviceNo}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          service_name: service.service_name,
          bg: service.bg,
        }),
      });
      applyWebsiteContentPayload(payload, `Saved service ${serviceNo}`);
      await loadWebsiteAuditLog({ showStatus: false });
      await loadWebsitePreview({ showStatus: false });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setWebsiteContentSaving(false);
    }
  }

  async function saveWebsiteContact(contactNo) {
    const content = normalizeWebsiteContent(websiteContentDraft || websiteContent || {});
    const contact = content.contacts.find((item) => Number(item.no) === Number(contactNo));
    if (!contact) return;

    try {
      setWebsiteContentSaving(true);
      setStatus({ tone: "", text: "Saving contact..." });
      const payload = await requestJson(`/api/website-content/contacts/${contactNo}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          name: contact.name,
          number: contact.number,
          bg: contact.bg,
        }),
      });
      applyWebsiteContentPayload(payload, `Saved contact ${contactNo}`);
      await loadWebsiteAuditLog({ showStatus: false });
      await loadWebsitePreview({ showStatus: false });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setWebsiteContentSaving(false);
    }
  }

  // Full teardown, used when the workspace is reset (logout, company switch).
  const resetWebsiteAdmin = React.useCallback(() => {
    setWebsiteContent(null);
    setWebsiteContentDraft(null);
    setWebsiteGallery([]);
    setWebsiteGalleryDraft([]);
    setWebsiteGalleryLoading(false);
    setWebsiteAuditLog([]);
    setWebsiteAuditLoading(false);
    setWebsitePreview(null);
    setWebsitePreviewLoading(false);
    setWebsiteAssets({ service: [], contact: [] });
    setWebsiteAssetsLoading(false);
    setWebsiteAssetUploading("");
    setWebsiteContentLoading(false);
    setWebsiteContentSaving(false);
  }, []);

  // Narrower teardown that runs when the token disappears. This deliberately
  // leaves preview/asset state alone, matching the pre-refactor behaviour.
  const clearWebsiteAdminOnSignOut = React.useCallback(() => {
    setWebsiteContent(null);
    setWebsiteContentDraft(null);
    setWebsiteGallery([]);
    setWebsiteGalleryDraft([]);
    setWebsiteGalleryLoading(false);
    setWebsiteAuditLog([]);
    setWebsiteAuditLoading(false);
    setWebsiteContentLoading(false);
    setWebsiteContentSaving(false);
  }, []);

  return {
    websiteAssetUploading,
    websiteAssets,
    websiteAssetsLoading,
    websiteAuditLoading,
    websiteAuditLog,
    websiteContent,
    websiteContentDraft,
    websiteContentLoading,
    websiteContentSaving,
    websiteGallery,
    websiteGalleryDraft,
    websiteGalleryLoading,
    websitePreview,
    websitePreviewLoading,
    clearWebsiteAdminOnSignOut,
    importLegacyWebsiteGallery,
    loadWebsiteAssets,
    loadWebsiteAuditLog,
    loadWebsiteContent,
    loadWebsiteGallery,
    loadWebsitePreview,
    resetWebsiteAdmin,
    saveWebsiteContact,
    saveWebsiteFooter,
    saveWebsiteGalleryPhoto,
    saveWebsiteService,
    updateWebsiteContactField,
    updateWebsiteFooterField,
    updateWebsiteGalleryPhotoField,
    updateWebsiteServiceField,
    uploadWebsiteAsset,
  };
}

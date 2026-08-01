import {
  FileText,
  Globe2,
  Image as ImageIcon,
  RefreshCw,
  Save,
  Upload,
} from "lucide-react";
import { WebsiteAssetField } from "../components/WebsiteAssetField.jsx";
import { WebsitePreviewPanel } from "../components/WebsitePreviewPanel.jsx";
import { PROJECT_SERVICE_CATEGORIES, WEBSITE_FOOTER_FIELDS } from "../constants.js";
import { isFlagOn, readValue } from "../lib/format.js";
import {
  formatWebsiteAuditAction,
  getWebsiteGallerySummary,
  normalizeWebsiteAssets,
  normalizeWebsiteAudit,
  normalizeWebsiteContent,
  normalizeWebsiteGallery,
  normalizeWebsitePreview,
} from "../lib/normalize.js";
import { getProjectPhotoUrl } from "../lib/projects.js";

export function WebsiteContentPage({
  assetUploading,
  assets,
  assetsLoading,
  auditLoading,
  auditLog,
  draft,
  galleryDraft,
  gallerySaving,
  loading,
  preview,
  previewLoading,
  saving,
  status,
  onContactChange,
  onFooterChange,
  onGalleryPhotoChange,
  onImportLegacyGallery,
  onOpenProject,
  onRefresh,
  onRefreshPreview,
  onSaveGalleryPhoto,
  onSaveContact,
  onSaveFooter,
  onSaveService,
  onServiceChange,
  onUploadAsset,
  token,
}) {
  const content = normalizeWebsiteContent(draft);
  const gallery = normalizeWebsiteGallery(galleryDraft);
  const gallerySummary = getWebsiteGallerySummary(gallery);
  const auditEntries = normalizeWebsiteAudit(auditLog);
  const previewData = normalizeWebsitePreview(preview);
  const websiteAssets = {
    service: normalizeWebsiteAssets(assets?.service),
    contact: normalizeWebsiteAssets(assets?.contact),
  };

  return (
    <section className="content-panel item-page website-content-page">
      <div className="detail-page-header">
        <div className="rdp-title">
          <div className="item-hero-icon">
            <ImageIcon aria-hidden="true" size={24} />
          </div>
          <div>
            <h2>Website Content</h2>
            <p>sengchong.com public content</p>
          </div>
        </div>
        <div className="page-header-actions">
          <button className="secondary-button" type="button" onClick={onRefresh}>
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
        </div>
      </div>

      <div className={`status-bar ${status?.tone || ""}`}>
        {loading ? "Loading website content..." : status?.text || "Ready"}
      </div>

      <div className="website-content-layout">
        <WebsitePreviewPanel
          loading={previewLoading}
          preview={previewData}
          onRefresh={onRefreshPreview}
        />

        <section className="item-card item-card-wide website-gallery-panel">
          <div className="item-card-header">
            <div>
              <h3>Website Gallery</h3>
              <span>
                {gallerySummary.websiteVisibleCount} website / {gallerySummary.publicCount} public /{" "}
                {gallerySummary.count} total
              </span>
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={() => window.open("https://sengchong.com/products", "_blank", "noopener")}
            >
              <Globe2 aria-hidden="true" size={16} />
              Public Gallery
            </button>
            <button
              className="secondary-button"
              disabled={gallerySaving}
              type="button"
              onClick={onImportLegacyGallery}
            >
              <Upload aria-hidden="true" size={16} />
              Import Legacy
            </button>
          </div>

          {gallery.length === 0 ? (
            <div className="detail-empty compact-empty">No project photos</div>
          ) : (
            <div className="website-gallery-grid">
              {gallery.map((photo) => {
                const photoId = readValue(photo, "id");
                const projectCode = readValue(photo, "projectCode");
                const isPublic = isFlagOn(readValue(photo, "isPublic"));
                const websiteVisible = isFlagOn(readValue(photo, "websiteVisible"));
                const isCover = isFlagOn(readValue(photo, "isCover"));
                const caption = readValue(photo, "caption");
                const category =
                  readValue(photo, "serviceCategory") ||
                  readValue(photo, "projectServiceCategory");

                return (
                  <article className="website-gallery-card" key={photoId}>
                    <button
                      className="website-gallery-frame"
                      type="button"
                      onClick={() =>
                        window.open(getProjectPhotoUrl(photo, token, ""), "_blank", "noopener")
                      }
                    >
                      <img
                        alt={readValue(photo, "altText") || caption || category || "Project photo"}
                        src={getProjectPhotoUrl(photo, token)}
                      />
                    </button>
                    <div className="website-gallery-card-body">
                      <div className="website-gallery-card-title">
                        <div>
                          <h4>{caption || readValue(photo, "projectTitle") || "Project photo"}</h4>
                          <span>{[projectCode, readValue(photo, "projectStatus")].filter(Boolean).join(" - ")}</span>
                        </div>
                        <div className="photo-badge-list">
                          {isCover && <span className="photo-badge cover">Cover</span>}
                          <span className={`photo-badge ${isPublic ? "public" : ""}`}>
                            {isPublic ? "Public" : "Private"}
                          </span>
                          <span className={`photo-badge ${websiteVisible ? "website" : ""}`}>
                            {websiteVisible ? "Website" : "Hidden"}
                          </span>
                        </div>
                      </div>

                      <div className="website-gallery-fields">
                        <label className="form-field">
                          <span>Category</span>
                          <select
                            value={category || ""}
                            onChange={(event) =>
                              onGalleryPhotoChange(photoId, {
                                serviceCategory: event.target.value,
                              })
                            }
                          >
                            <option value="">No category</option>
                            {PROJECT_SERVICE_CATEGORIES.map((choice) => (
                              <option key={choice} value={choice}>
                                {choice}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="form-field">
                          <span>Sort</span>
                          <input
                            type="number"
                            value={readValue(photo, "sortOrder") || 0}
                            onChange={(event) =>
                              onGalleryPhotoChange(photoId, {
                                sortOrder: event.target.value,
                              })
                            }
                          />
                        </label>
                        <label className="form-field span-2">
                          <span>Caption</span>
                          <input
                            value={caption || ""}
                            onChange={(event) =>
                              onGalleryPhotoChange(photoId, {
                                caption: event.target.value,
                              })
                            }
                          />
                        </label>
                        <label className="form-field span-2">
                          <span>Alt Text</span>
                          <input
                            value={readValue(photo, "altText") || ""}
                            onChange={(event) =>
                              onGalleryPhotoChange(photoId, {
                                altText: event.target.value,
                              })
                            }
                          />
                        </label>
                      </div>

                      <div className="website-gallery-actions">
                        <label className="check-field compact-check">
                          <input
                            checked={isPublic}
                            type="checkbox"
                            onChange={(event) => {
                              const nextPublic = event.target.checked;
                              onGalleryPhotoChange(photoId, {
                                isPublic: nextPublic,
                                ...(nextPublic ? {} : { websiteVisible: false }),
                              });
                            }}
                          />
                          <span>Public</span>
                        </label>
                        <label className="check-field compact-check">
                          <input
                            checked={websiteVisible}
                            type="checkbox"
                            onChange={(event) => {
                              const nextVisible = event.target.checked;
                              onGalleryPhotoChange(photoId, {
                                websiteVisible: nextVisible,
                                ...(nextVisible ? { isPublic: true } : {}),
                              });
                            }}
                          />
                          <span>Website</span>
                        </label>
                        <button
                          className="secondary-button"
                          disabled={gallerySaving}
                          type="button"
                          onClick={() => onOpenProject(projectCode)}
                        >
                          <FileText aria-hidden="true" size={16} />
                          Project
                        </button>
                        <button
                          className="primary-button"
                          disabled={gallerySaving}
                          type="button"
                          onClick={() => onSaveGalleryPhoto(photoId)}
                        >
                          <Save aria-hidden="true" size={16} />
                          {gallerySaving ? "Saving..." : "Save"}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="item-card item-card-wide website-audit-panel">
          <div className="item-card-header">
            <div>
              <h3>Publish Audit</h3>
              <span>{auditEntries.length} recent change{auditEntries.length === 1 ? "" : "s"}</span>
            </div>
          </div>
          <div className="website-audit-list">
            {auditLoading ? (
              <div className="detail-empty compact-empty">Loading audit log...</div>
            ) : auditEntries.length === 0 ? (
              <div className="detail-empty compact-empty">No publish changes</div>
            ) : (
              auditEntries.slice(0, 20).map((entry) => (
                <div className="website-audit-row" key={readValue(entry, "id")}>
                  <div>
                    <strong>{formatWebsiteAuditAction(readValue(entry, "action"))}</strong>
                    <span>
                      {[readValue(entry, "projectCode"), readValue(entry, "fieldName")]
                        .filter(Boolean)
                        .join(" - ")}
                    </span>
                  </div>
                  <div>
                    <span>{readValue(entry, "oldValue") || "-"}</span>
                    <strong>{readValue(entry, "newValue") || "-"}</strong>
                  </div>
                  <div>
                    <span>{readValue(entry, "username") || "-"}</span>
                    <strong>{readValue(entry, "createdAt") || "-"}</strong>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Services</h3>
          </div>
          <div className="website-edit-list">
            {content.services.map((service) => (
              <div className="website-edit-row" key={service.no}>
                <span className="website-row-index">{service.no}</span>
                <label className="form-field">
                  <span>Service Name</span>
                  <input
                    value={service.service_name || ""}
                    onChange={(event) =>
                      onServiceChange(service.no, "service_name", event.target.value)
                    }
                  />
                </label>
                <WebsiteAssetField
                  assets={websiteAssets.service}
                  kind="service"
                  loading={assetsLoading}
                  uploading={assetUploading === `service:${service.no}`}
                  value={service.bg || ""}
                  onChange={(value) => onServiceChange(service.no, "bg", value)}
                  onUpload={(kind, file) => onUploadAsset(kind, file, service.no)}
                />
                <button
                  className="secondary-button"
                  disabled={saving}
                  type="button"
                  onClick={() => onSaveService(service.no)}
                >
                  <Save aria-hidden="true" size={16} />
                  Save
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Contacts</h3>
          </div>
          <div className="website-edit-list">
            {content.contacts.map((contact) => (
              <div className="website-edit-row" key={contact.no}>
                <span className="website-row-index">{contact.no}</span>
                <label className="form-field">
                  <span>Name</span>
                  <input
                    value={contact.name || ""}
                    onChange={(event) => onContactChange(contact.no, "name", event.target.value)}
                  />
                </label>
                <label className="form-field">
                  <span>Number</span>
                  <input
                    value={contact.number || ""}
                    onChange={(event) => onContactChange(contact.no, "number", event.target.value)}
                  />
                </label>
                <WebsiteAssetField
                  assets={websiteAssets.contact}
                  kind="contact"
                  loading={assetsLoading}
                  uploading={assetUploading === `contact:${contact.no}`}
                  value={contact.bg || ""}
                  onChange={(value) => onContactChange(contact.no, "bg", value)}
                  onUpload={(kind, file) => onUploadAsset(kind, file, contact.no)}
                />
                <button
                  className="secondary-button"
                  disabled={saving}
                  type="button"
                  onClick={() => onSaveContact(contact.no)}
                >
                  <Save aria-hidden="true" size={16} />
                  Save
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Footer</h3>
          </div>
          <div className="website-footer-form">
            {WEBSITE_FOOTER_FIELDS.map(([name, label, kind]) => (
              <label
                className={`form-field ${kind === "textarea" ? "span-2" : ""}`}
                key={name}
              >
                <span>{label}</span>
                {kind === "textarea" ? (
                  <textarea
                    rows={4}
                    value={content.footer[name] || ""}
                    onChange={(event) => onFooterChange(name, event.target.value)}
                  />
                ) : (
                  <input
                    value={content.footer[name] || ""}
                    onChange={(event) => onFooterChange(name, event.target.value)}
                  />
                )}
              </label>
            ))}
          </div>
          <div className="website-footer-actions">
            <button
              className="primary-button"
              disabled={saving}
              type="button"
              onClick={onSaveFooter}
            >
              <Save aria-hidden="true" size={16} />
              {saving ? "Saving..." : "Save Footer"}
            </button>
          </div>
        </section>
      </div>
    </section>
  );
}

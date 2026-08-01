import {
  Globe2,
  RefreshCw,
} from "lucide-react";
import { readValue } from "../lib/format.js";

export function WebsitePreviewPanel({ loading, preview, onRefresh }) {
  const services = Array.isArray(preview?.services) ? preview.services : [];
  const contacts = Array.isArray(preview?.contacts) ? preview.contacts : [];
  const gallery = Array.isArray(preview?.gallery) ? preview.gallery : [];
  const footer = preview?.footer || {};
  const companyName = footer.company_name || "Seng Chong Interior Design";

  return (
    <section className="item-card item-card-wide website-preview-panel">
      <div className="item-card-header">
        <div>
          <h3>Website Preview</h3>
          <span>
            {services.length} services / {gallery.length} photos / {contacts.length} contacts
          </span>
        </div>
        <div className="website-preview-actions">
          <button className="secondary-button" disabled={loading} type="button" onClick={onRefresh}>
            <RefreshCw aria-hidden="true" size={16} />
            {loading ? "Refreshing..." : "Refresh Preview"}
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => window.open("https://sengchong.com/", "_blank", "noopener")}
          >
            <Globe2 aria-hidden="true" size={16} />
            Public Home
          </button>
        </div>
      </div>

      <div className="website-preview-shell">
        <div className="website-preview-hero">
          <div>
            <strong>{companyName}</strong>
            <span>{footer.registration_no || ""}</span>
          </div>
          <div>
            <span>{footer.phone || ""}</span>
            <span>{footer.business_hours || ""}</span>
          </div>
        </div>

        <div className="website-preview-section">
          <div className="website-preview-section-title">
            <h4>Services</h4>
          </div>
          <div className="website-preview-services">
            {services.slice(0, 9).map((service) => (
              <div className="website-preview-service" key={readValue(service, "no")}>
                <img
                  alt={readValue(service, "serviceName") || "Service"}
                  src={readValue(service, "imageUrl")}
                />
                <span>{readValue(service, "serviceName")}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="website-preview-section">
          <div className="website-preview-section-title">
            <h4>Gallery</h4>
            <span>{gallery.length} public photo{gallery.length === 1 ? "" : "s"}</span>
          </div>
          <div className="website-preview-gallery">
            {gallery.slice(0, 12).map((photo) => (
              <img
                alt={
                  readValue(photo, "altText") ||
                  readValue(photo, "caption") ||
                  readValue(photo, "serviceCategory") ||
                  "Project photo"
                }
                key={readValue(photo, "id")}
                src={readValue(photo, "thumbnailUrl")}
              />
            ))}
          </div>
        </div>

        <div className="website-preview-footer">
          <div>
            <strong>Contact</strong>
            {contacts.map((contact) => (
              <span key={readValue(contact, "no")}>
                {[readValue(contact, "name"), readValue(contact, "number")]
                  .filter(Boolean)
                  .join(" - ")}
              </span>
            ))}
          </div>
          <div>
            <strong>Footer</strong>
            <span>{footer.address || ""}</span>
            <span>{footer.contact_person || ""}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

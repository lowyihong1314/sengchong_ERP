import React from "react";
import {
  Eye,
  EyeOff,
  Globe2,
  Star,
  Trash2,
  Upload,
} from "lucide-react";
import { PROJECT_SERVICE_CATEGORIES } from "../constants.js";
import { isFlagOn, readValue } from "../lib/format.js";
import { getProjectPhotoUrl } from "../lib/projects.js";

export function ProjectPhotosPanel({
  detail,
  saving,
  token,
  onDeletePhoto,
  onUpdatePhoto,
  onUploadPhotos,
}) {
  const photos = detail?.photos || [];
  const fileInputRef = React.useRef(null);
  const [selectedFiles, setSelectedFiles] = React.useState([]);
  const [draft, setDraft] = React.useState({
    serviceCategory: readValue(detail, "serviceCategory") || PROJECT_SERVICE_CATEGORIES[0],
    caption: "",
    altText: "",
    isPublic: false,
    websiteVisible: false,
  });

  React.useEffect(() => {
    setSelectedFiles([]);
    setDraft({
      serviceCategory: readValue(detail, "serviceCategory") || PROJECT_SERVICE_CATEGORIES[0],
      caption: "",
      altText: "",
      isPublic: false,
      websiteVisible: false,
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, [detail?.projectCode]);

  const updateDraft = (name, value) => {
    setDraft((current) => {
      const next = { ...current, [name]: value };
      if (name === "isPublic" && !value) {
        next.websiteVisible = false;
      }
      if (name === "websiteVisible" && value) {
        next.isPublic = true;
      }
      return next;
    });
  };

  const submitUpload = async (event) => {
    event.preventDefault();
    if (!selectedFiles.length || !onUploadPhotos) return;

    const ok = await onUploadPhotos(selectedFiles, draft);
    if (ok !== false) {
      setSelectedFiles([]);
      setDraft((current) => ({
        ...current,
        caption: "",
        altText: "",
        isPublic: false,
        websiteVisible: false,
      }));
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const togglePublic = (photo) => {
    const isPublic = isFlagOn(readValue(photo, "isPublic"));
    onUpdatePhoto?.(readValue(photo, "id"), { isPublic: !isPublic });
  };

  const toggleWebsiteVisible = (photo) => {
    const websiteVisible = isFlagOn(readValue(photo, "websiteVisible"));
    onUpdatePhoto?.(
      readValue(photo, "id"),
      websiteVisible
        ? { websiteVisible: false }
        : { isPublic: true, websiteVisible: true }
    );
  };

  const markCover = (photo) => {
    onUpdatePhoto?.(readValue(photo, "id"), { isCover: true });
  };

  const deletePhoto = (photo) => {
    const photoId = readValue(photo, "id");
    if (!photoId || !window.confirm("Delete this project photo?")) return;
    onDeletePhoto?.(photoId);
  };

  return (
    <section className="project-photos-panel">
      <div className="related-section-header">
        <h3>Project Photos</h3>
        <span>{photos.length} photo{photos.length === 1 ? "" : "s"}</span>
      </div>

      <form className="project-photo-upload" onSubmit={submitUpload}>
        <label className="form-field span-2">
          <span>Images</span>
          <input
            accept="image/*"
            multiple
            ref={fileInputRef}
            type="file"
            onChange={(event) => setSelectedFiles(Array.from(event.target.files || []))}
          />
        </label>
        <label className="form-field">
          <span>Category</span>
          <select
            value={draft.serviceCategory}
            onChange={(event) => updateDraft("serviceCategory", event.target.value)}
          >
            {PROJECT_SERVICE_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Caption</span>
          <input
            value={draft.caption}
            onChange={(event) => updateDraft("caption", event.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Alt Text</span>
          <input
            value={draft.altText}
            onChange={(event) => updateDraft("altText", event.target.value)}
          />
        </label>
        <label className="check-field compact-check">
          <input
            checked={draft.isPublic}
            type="checkbox"
            onChange={(event) => updateDraft("isPublic", event.target.checked)}
          />
          <span>Public</span>
        </label>
        <label className="check-field compact-check">
          <input
            checked={draft.websiteVisible}
            type="checkbox"
            onChange={(event) => updateDraft("websiteVisible", event.target.checked)}
          />
          <span>Website</span>
        </label>
        <div className="project-photo-upload-actions">
          <span>{selectedFiles.length} selected</span>
          <button
            className="primary-button"
            disabled={saving || selectedFiles.length === 0}
            type="submit"
          >
            <Upload aria-hidden="true" size={16} />
            {saving ? "Uploading..." : "Upload"}
          </button>
        </div>
      </form>

      {photos.length === 0 ? (
        <div className="detail-empty compact-empty">No project photos</div>
      ) : (
        <div className="project-photo-grid">
          {photos.map((photo) => {
            const photoId = readValue(photo, "id");
            const isPublic = isFlagOn(readValue(photo, "isPublic"));
            const websiteVisible = isFlagOn(readValue(photo, "websiteVisible"));
            const isCover = isFlagOn(readValue(photo, "isCover"));
            const caption = readValue(photo, "caption");
            const category = readValue(photo, "serviceCategory");
            return (
              <article className="project-photo-card" key={photoId}>
                <button
                  className="project-photo-frame"
                  type="button"
                  onClick={() => window.open(getProjectPhotoUrl(photo, token, ""), "_blank", "noopener")}
                >
                  <img
                    alt={readValue(photo, "altText") || caption || category || "Project photo"}
                    src={getProjectPhotoUrl(photo, token)}
                  />
                </button>
                <div className="project-photo-card-body">
                  <div>
                    <h4>{caption || category || "Project photo"}</h4>
                    <p>{category || "No category"}</p>
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
                  <div className="project-photo-actions">
                    <button
                      className={`photo-flag-button ${isPublic ? "on" : ""}`}
                      disabled={saving}
                      type="button"
                      onClick={() => togglePublic(photo)}
                    >
                      {isPublic ? <Eye aria-hidden="true" size={15} /> : <EyeOff aria-hidden="true" size={15} />}
                      Public
                    </button>
                    <button
                      className={`photo-flag-button ${websiteVisible ? "on" : ""}`}
                      disabled={saving}
                      type="button"
                      onClick={() => toggleWebsiteVisible(photo)}
                    >
                      <Globe2 aria-hidden="true" size={15} />
                      Website
                    </button>
                    <button
                      className={`photo-flag-button ${isCover ? "on" : ""}`}
                      disabled={saving || isCover}
                      type="button"
                      onClick={() => markCover(photo)}
                    >
                      <Star aria-hidden="true" size={15} />
                      Cover
                    </button>
                    <button
                      className="icon-button danger-button"
                      disabled={saving}
                      title="Delete photo"
                      type="button"
                      onClick={() => deletePhoto(photo)}
                    >
                      <Trash2 aria-hidden="true" size={15} />
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

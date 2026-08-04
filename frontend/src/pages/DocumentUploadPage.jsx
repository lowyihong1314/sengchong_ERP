import React from "react";
import { Camera, CheckCircle2, FolderOpen, ListChecks, Loader2 } from "lucide-react";

/**
 * Upload only. Photograph a document or drop files, and go.
 *
 * Built for a phone first: this is used standing in front of a pile of
 * delivery orders, not at a desk. Two thumb-sized targets, a progress bar,
 * and a receipt of what happened -- no table, no filters, nothing to read.
 *
 * The upload returns before anything has been read, so what comes back is
 * "filed", never "classified". Whoever wants to know what the model made of it
 * goes to the listing.
 */
export function DocumentUploadPage({
  uploading,
  uploadProgress,
  lastResult,
  status,
  onUpload,
  onOpenListing,
}) {
  const fileRef = React.useRef(null);
  const cameraRef = React.useRef(null);
  const [dragging, setDragging] = React.useState(false);

  function send(fileList) {
    const files = Array.from(fileList || []);
    if (files.length) onUpload(files);
  }

  const percent = uploadProgress.total
    ? Math.round((uploadProgress.done / uploadProgress.total) * 100)
    : 0;

  return (
    <section className="content-panel upload-page">
      <div className="upload-hero">
        <h2>Upload Documents</h2>
        <p>
          Invoices, delivery orders, payslips, site photos. Anything else is
          kept too, it just is not read.
        </p>
      </div>

      {/* capture= makes a phone open the camera directly instead of the file
          browser. Kept as a separate input because the same input cannot both
          force the camera and allow picking existing files. */}
      <input
        accept="image/*"
        capture="environment"
        hidden
        multiple
        ref={cameraRef}
        type="file"
        onChange={(event) => {
          send(event.target.files);
          event.target.value = "";
        }}
      />
      <input
        hidden
        multiple
        ref={fileRef}
        type="file"
        onChange={(event) => {
          send(event.target.files);
          event.target.value = "";
        }}
      />

      <div
        className={`upload-targets${dragging ? " dragging" : ""}`}
        onDragLeave={() => setDragging(false)}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          send(event.dataTransfer?.files);
        }}
      >
        <button
          className="upload-target primary"
          disabled={uploading}
          type="button"
          onClick={() => cameraRef.current?.click()}
        >
          <Camera aria-hidden="true" size={34} />
          <strong>Take Photo</strong>
          <span>Camera</span>
        </button>
        <button
          className="upload-target"
          disabled={uploading}
          type="button"
          onClick={() => fileRef.current?.click()}
        >
          <FolderOpen aria-hidden="true" size={34} />
          <strong>Choose Files</strong>
          <span>Or drag them here</span>
        </button>
      </div>

      {uploading && (
        <div className="upload-progress">
          <div className="upload-progress-head">
            <Loader2 aria-hidden="true" className="spin" size={16} />
            <span>
              Uploading {uploadProgress.done} of {uploadProgress.total}
            </span>
          </div>
          <div className="upload-bar">
            <div className="upload-bar-fill" style={{ width: `${percent}%` }} />
          </div>
        </div>
      )}

      {lastResult && !uploading && (
        <div className="upload-receipt">
          <CheckCircle2 aria-hidden="true" size={18} />
          <div>
            <strong>{lastResult.stored} filed</strong>
            <span>
              {[
                lastResult.skipped ? `${lastResult.skipped} kept but not read` : "",
                lastResult.duplicates ? `${lastResult.duplicates} already on record` : "",
                lastResult.rejected ? `${lastResult.rejected} rejected` : "",
              ]
                .filter(Boolean)
                .join(" - ") || "Being read now"}
            </span>
          </div>
          <button className="ghost-button" type="button" onClick={onOpenListing}>
            <ListChecks aria-hidden="true" size={15} />
            View
          </button>
        </div>
      )}

      <p className="upload-note">
        Reading happens after the upload, so you can close this page. Nothing
        here is posted to accounts or payroll -- documents are filed and read,
        and what to do with them is a separate decision.
      </p>

      <div className={`status-bar ${status.tone}`}>{status.text}</div>
    </section>
  );
}

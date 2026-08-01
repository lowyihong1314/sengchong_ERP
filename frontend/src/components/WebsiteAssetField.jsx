import React from "react";
import {
  Image as ImageIcon,
  Upload,
} from "lucide-react";
import { readValue } from "../lib/format.js";

export function WebsiteAssetField({
  kind,
  value,
  assets,
  loading,
  uploading,
  onChange,
  onUpload,
}) {
  const fileInputRef = React.useRef(null);
  const selectedAsset = (assets || []).find((asset) => readValue(asset, "filename") === value);
  const previewUrl = selectedAsset?.url || (value ? `/static/images/${kind}/${value}` : "");

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file || !onUpload) return;
    const asset = await onUpload(kind, file);
    if (asset?.filename) {
      onChange(asset.filename);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="form-field website-asset-field">
      <span>Image</span>
      <div className="website-asset-control">
        <div className="website-asset-preview">
          {previewUrl ? (
            <img alt={value || "Website asset"} src={previewUrl} />
          ) : (
            <ImageIcon aria-hidden="true" size={18} />
          )}
        </div>
        <select disabled={loading || uploading} value={value || ""} onChange={(event) => onChange(event.target.value)}>
          <option value="">{loading ? "Loading images..." : "No image"}</option>
          {(assets || []).map((asset) => (
            <option key={readValue(asset, "filename")} value={readValue(asset, "filename")}>
              {readValue(asset, "filename")}
            </option>
          ))}
        </select>
        <button
          className="secondary-button"
          disabled={uploading}
          type="button"
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload aria-hidden="true" size={16} />
          {uploading ? "Uploading..." : "Upload"}
        </button>
        <input
          ref={fileInputRef}
          hidden
          accept="image/*"
          type="file"
          onChange={handleUpload}
        />
      </div>
    </div>
  );
}

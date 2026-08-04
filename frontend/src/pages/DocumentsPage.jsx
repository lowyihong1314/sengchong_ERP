import React from "react";
import { AlertTriangle, Copy, Download, RefreshCw, Trash2, Upload } from "lucide-react";

import { formatValue } from "../lib/format.js";

const CLASS_LABELS = {
  sales: "Sales",
  purchase: "Purchase",
  project_image: "Project Image",
  salary: "Salary",
  other: "Other",
  unclassified: "Not read",
};

const STATUS_LABELS = {
  pending: "Queued",
  analysing: "Reading",
  analysed: "Read",
  failed: "Failed",
  skipped: "Not read",
};

/**
 * Everything filed, and what was read from it.
 *
 * Reading happens in a worker after the upload has already returned, so a row
 * arrives as "Queued" and fills in later -- which is why the caller polls this
 * while anything is outstanding. Uploading lives on its own page: this one is
 * for looking, and is no use on the phone that took the photographs.
 */
export function DocumentsPage({
  documents,
  detail,
  counts,
  loading,
  status,
  filterClass,
  filterStatus,
  query,
  onSelect,
  onReanalyse,
  onDelete,
  onRefresh,
  onFilterClass,
  onFilterStatus,
  onQuery,
  onOpenUpload,
}) {
  const byClass = counts?.byClass || {};
  const queued = counts?.queued || 0;

  return (
    <section className="content-panel documents-page">
      <div className="detail-page-header">
        <div>
          <h2>Documents</h2>
          <p>
            {counts?.total ? `${counts.total} filed` : "Nothing filed yet"}
            {queued ? ` - ${queued} still being read` : ""}
          </p>
        </div>
        <div className="topbar-actions">
          <button className="ghost-button" disabled={loading} type="button" onClick={onRefresh}>
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
          <button className="primary-button" type="button" onClick={onOpenUpload}>
            <Upload aria-hidden="true" size={16} />
            Upload
          </button>
        </div>
      </div>

      <div className="toolbar">
        <label className="form-field">
          <span>Class</span>
          <select value={filterClass} onChange={(event) => onFilterClass(event.target.value)}>
            <option value="">All</option>
            {Object.entries(CLASS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
                {byClass[value] ? ` (${byClass[value]})` : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Status</span>
          <select value={filterStatus} onChange={(event) => onFilterStatus(event.target.value)}>
            <option value="">All</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="form-field grow">
          <span>Search</span>
          <input
            placeholder="Issuer, document number, filename"
            value={query}
            onChange={(event) => onQuery(event.target.value)}
          />
        </label>
      </div>

      <div className="documents-split">
        <div className="table-wrap">
          <table className="documents-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Class</th>
                <th>Issuer</th>
                <th>Doc No</th>
                <th>Date</th>
                <th className="number">Total</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={8}>{loading ? "Loading..." : "Nothing filed yet."}</td>
                </tr>
              ) : (
                documents.map((row) => (
                  <tr
                    className={detail?.id === row.id ? "selected" : ""}
                    key={row.id}
                    onClick={() => onSelect(row.id)}
                  >
                    <td>
                      <strong>{row.filename || row.id}</strong>
                      <span>
                        {row.summary || `${(row.byteSize / 1024).toFixed(0)} KB`}
                      </span>
                    </td>
                    <td>
                      <span className={`doc-chip ${row.docClass}`}>
                        {CLASS_LABELS[row.docClass] || row.docClass}
                      </span>
                    </td>
                    <td>{row.issuer || "-"}</td>
                    <td>
                      {row.docNo || "-"}
                      {row.duplicateOf && (
                        <span className="dupe-flag" title="Same issuer and number as an earlier document">
                          <Copy aria-hidden="true" size={12} /> repeat
                        </span>
                      )}
                    </td>
                    <td>{row.docDate || "-"}</td>
                    <td className="number">
                      {row.total === null ? "-" : formatValue(row.total, "money")}
                    </td>
                    <td>
                      <span className={`doc-status ${row.status}`}>
                        {STATUS_LABELS[row.status] || row.status}
                      </span>
                    </td>
                    <td className="number">
                      <button
                        aria-label={`Delete ${row.filename}`}
                        className="icon-button"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onDelete(row.id);
                        }}
                      >
                        <Trash2 aria-hidden="true" size={14} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <aside className="document-detail">
          {!detail ? (
            <p className="muted">Select a document to see what was read from it.</p>
          ) : (
            <>
              <header>
                <strong>{detail.filename}</strong>
                <span>
                  {STATUS_LABELS[detail.status] || detail.status}
                  {detail.model ? ` - ${detail.model}` : ""}
                  {detail.tokensIn
                    ? ` - ${detail.tokensIn + detail.tokensOut} tokens`
                    : ""}
                </span>
              </header>

              {detail.error && (
                <div className="status-bar error">
                  <AlertTriangle aria-hidden="true" size={14} /> {detail.error}
                </div>
              )}
              {detail.duplicateOf && (
                <div className="status-bar warn">
                  Same issuer and document number as an earlier upload. Kept, not merged.
                </div>
              )}

              {detail.previewPath && (
                <img
                  alt={`Preview of ${detail.filename}`}
                  className="document-preview"
                  src={`/api/documents/${detail.id}/preview`}
                />
              )}

              <div className="detail-actions">
                <a
                  className="secondary-button"
                  href={`/api/documents/${detail.id}/file`}
                  rel="noreferrer"
                >
                  <Download aria-hidden="true" size={15} />
                  Original
                </a>
                {detail.status !== "skipped" && (
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => onReanalyse(detail.id)}
                  >
                    <RefreshCw aria-hidden="true" size={15} />
                    Read Again
                  </button>
                )}
              </div>

              {/* The extraction verbatim. Nothing downstream consumes it yet --
                  this page files and reads, and stops there. */}
              <label className="raw-json-label">Extracted data</label>
              <pre className="raw-json">
                {detail.raw ? JSON.stringify(detail.raw, null, 2) : "Not read yet."}
              </pre>
            </>
          )}
        </aside>
      </div>

      <div className={`status-bar ${status.tone}`}>{status.text}</div>
    </section>
  );
}

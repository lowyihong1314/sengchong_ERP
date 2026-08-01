import React from "react";
import {
  FileText,
  Plus,
  RefreshCw,
  Save,
  Search,
  Trash2,
} from "lucide-react";
import { requestJson } from "../lib/api.js";
import { getDocumentList } from "../lib/documents.js";
import { formatValue, readValue } from "../lib/format.js";
import { normalizeDetail, normalizeRows } from "../lib/normalize.js";
import {
  getLinkedDocumentAmount,
  getProjectCostRows,
  getProjectCostSummary,
  getProjectFinancialSummary,
} from "../lib/projects.js";
import { getModuleDetailPath, getModuleListPath } from "../lib/routing.js";
import { getDocumentCurrency } from "../lib/totals.js";

export function ProjectLinksPanel({
  detail,
  token,
  syncingFinancials,
  unlinkingDocument,
  onLinkDocument,
  onOpenDocument,
  onRefreshProject,
  onSyncFinancials,
  onUnlinkDocument,
}) {
  const groups = [
    {
      title: "Quotation",
      moduleKey: "quotations",
      values: getDocumentList(readValue(detail, "quotationDocNos") || readValue(detail, "quotationDocNo")),
    },
    {
      title: "Invoice",
      moduleKey: "invoices",
      values: getDocumentList(readValue(detail, "invoiceDocNos") || readValue(detail, "invoiceDocNo")),
    },
    {
      title: "AR Payment",
      moduleKey: "ar-payments",
      values: getDocumentList(readValue(detail, "arPaymentDocNos")),
    },
    {
      title: "Purchase Order",
      moduleKey: "purchase-orders",
      values: getDocumentList(readValue(detail, "purchaseOrderDocNos")),
    },
    {
      title: "AP Invoice",
      moduleKey: "ap-invoices",
      values: getDocumentList(readValue(detail, "apInvoiceDocNos")),
    },
  ].filter((group) => group.values.length > 0);

  const documents = groups.flatMap((group) =>
    group.values.map((value) => ({
      label: group.title,
      moduleKey: group.moduleKey,
      docNo: value,
      key: `${group.moduleKey}:${value}`,
    }))
  );
  const documentSignature = documents.map((document) => document.key).join("|");
  const [documentDetails, setDocumentDetails] = React.useState({});
  const [loadingDetails, setLoadingDetails] = React.useState(false);
  const [detailError, setDetailError] = React.useState("");
  const [apPickerOpen, setApPickerOpen] = React.useState(false);
  const [apInvoiceRows, setApInvoiceRows] = React.useState([]);
  const [apInvoiceLoading, setApInvoiceLoading] = React.useState(false);
  const [apInvoiceError, setApInvoiceError] = React.useState("");
  const [apInvoiceQuery, setApInvoiceQuery] = React.useState("");
  const [selectedApInvoice, setSelectedApInvoice] = React.useState("");
  const [linkingApInvoice, setLinkingApInvoice] = React.useState(false);
  const financialSummary = getProjectFinancialSummary(documents, documentDetails);
  const costRows = getProjectCostRows(documents, documentDetails);
  const costSummary = getProjectCostSummary(costRows);
  const linkedApInvoiceKeys = new Set(
    getDocumentList(readValue(detail, "apInvoiceDocNos")).map((value) => value.toLowerCase())
  );
  const apInvoiceChoices = apInvoiceRows
    .filter((row) => !linkedApInvoiceKeys.has(String(readValue(row, "docNo")).toLowerCase()))
    .filter((row) => {
      const needle = apInvoiceQuery.trim().toLowerCase();
      if (!needle) return true;
      return [
        "docNo",
        "docDate",
        "creditorCode",
        "creditorName",
        "supplierInvoiceNo",
        "description",
      ].some((key) => String(readValue(row, key)).toLowerCase().includes(needle));
    })
    .slice(0, 25);

  async function loadLinkedDocumentDetails(force = false) {
    if (!documents.length || !token) return;

    try {
      setLoadingDetails(true);
      setDetailError("");
      const nextDetails = {};
      for (const document of documents) {
        try {
          const payload = await requestJson(
            getModuleDetailPath(document.moduleKey, document.docNo, { refresh: force }),
            {
              headers: { Authorization: `Bearer ${token}` },
            }
          );
          nextDetails[document.key] = normalizeDetail(payload);
        } catch (error) {
          nextDetails[document.key] = { __error: error.message };
        }
      }
      setDocumentDetails(nextDetails);
    } catch (error) {
      setDetailError(error.message);
    } finally {
      setLoadingDetails(false);
    }
  }

  React.useEffect(() => {
    loadLinkedDocumentDetails(false);
    // documentSignature deliberately tracks the flattened linked document keys.
  }, [documentSignature, token]);

  async function loadApInvoiceChoices(force = false) {
    if (!token || (apInvoiceRows.length && !force)) return;

    try {
      setApInvoiceLoading(true);
      setApInvoiceError("");
      const payload = await requestJson(getModuleListPath("ap-invoices", { refresh: force }), {
        headers: { Authorization: `Bearer ${token}` },
      });
      setApInvoiceRows(normalizeRows(payload));
    } catch (error) {
      setApInvoiceError(error.message);
    } finally {
      setApInvoiceLoading(false);
    }
  }

  function openApPicker() {
    setApPickerOpen(true);
    loadApInvoiceChoices(false);
  }

  async function submitApInvoiceLink(event) {
    event.preventDefault();
    const docNo = String(selectedApInvoice || "").trim();
    if (!docNo || !onLinkDocument) return;

    try {
      setLinkingApInvoice(true);
      const ok = await onLinkDocument("ap-invoices", docNo);
      if (ok !== false) {
        setSelectedApInvoice("");
        setApInvoiceQuery("");
        setApPickerOpen(false);
      }
    } finally {
      setLinkingApInvoice(false);
    }
  }

  if (groups.length === 0 && !onLinkDocument) return null;

  return (
    <section className="project-link-panel">
      <div className="related-section-header">
        <div>
          <h3>Linked Documents</h3>
          <span>{documents.length} link{documents.length === 1 ? "" : "s"}</span>
        </div>
        <div className="project-link-header-actions">
          {onLinkDocument && (
            <button className="secondary-button" type="button" onClick={openApPicker}>
              <Plus aria-hidden="true" size={16} />
              Add AP Invoice
            </button>
          )}
          {onSyncFinancials && (
            <button
              className="primary-button"
              disabled={syncingFinancials || loadingDetails || financialSummary.sourceCount === 0}
              type="button"
              onClick={() => onSyncFinancials(financialSummary)}
            >
              <Save aria-hidden="true" size={16} />
              {syncingFinancials ? "Syncing..." : "Sync Financials"}
            </button>
          )}
          <button
            className="ghost-button"
            disabled={loadingDetails}
            type="button"
            onClick={() => loadLinkedDocumentDetails(true)}
          >
            <RefreshCw aria-hidden="true" size={16} />
            {loadingDetails ? "Refreshing..." : "Refresh Status"}
          </button>
          {onRefreshProject && (
            <button className="ghost-button" type="button" onClick={onRefreshProject}>
              <RefreshCw aria-hidden="true" size={16} />
              Refresh Project
            </button>
          )}
        </div>
      </div>
      {detailError && <div className="project-link-error">{detailError}</div>}
      {apPickerOpen && (
        <form className="project-ap-link-form" onSubmit={submitApInvoiceLink}>
          <label className="form-field" htmlFor="project-ap-invoice-search">
            <span>Search AP Invoice</span>
            <input
              id="project-ap-invoice-search"
              value={apInvoiceQuery}
              onChange={(event) => setApInvoiceQuery(event.target.value)}
              placeholder="Doc no, supplier, supplier invoice"
            />
          </label>
          <label className="form-field" htmlFor="project-ap-invoice-select">
            <span>AP Invoice</span>
            <select
              id="project-ap-invoice-select"
              value={selectedApInvoice}
              onChange={(event) => setSelectedApInvoice(event.target.value)}
              required
            >
              <option value="">
                {apInvoiceLoading ? "Loading AP invoices" : "Select AP invoice"}
              </option>
              {apInvoiceChoices.map((row) => {
                const docNo = readValue(row, "docNo");
                const creditorName = readValue(row, "creditorName");
                const supplierInvoiceNo = readValue(row, "supplierInvoiceNo");
                const amount = formatValue(
                  readValue(row, "netTotal"),
                  "money",
                  getDocumentCurrency(row)
                );
                return (
                  <option key={docNo} value={docNo}>
                    {[docNo, supplierInvoiceNo, creditorName, amount].filter(Boolean).join(" - ")}
                  </option>
                );
              })}
            </select>
          </label>
          <div className="project-ap-link-actions">
            <button
              className="secondary-button"
              disabled={apInvoiceLoading}
              type="button"
              onClick={() => loadApInvoiceChoices(true)}
            >
              <RefreshCw aria-hidden="true" size={16} />
              Refresh
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                setApPickerOpen(false);
                setSelectedApInvoice("");
              }}
            >
              Cancel
            </button>
            <button
              className="primary-button"
              disabled={linkingApInvoice || apInvoiceLoading || !selectedApInvoice}
              type="submit"
            >
              <Plus aria-hidden="true" size={16} />
              {linkingApInvoice ? "Linking..." : "Link"}
            </button>
          </div>
          {apInvoiceError && <div className="project-link-error">{apInvoiceError}</div>}
        </form>
      )}
      <div className="project-financial-summary">
        {[
          ["Quoted", financialSummary.quoted],
          ["Invoiced", financialSummary.invoiced],
          ["Paid", financialSummary.paid],
          ["Outstanding", financialSummary.outstanding],
          ["Purchase Cost", financialSummary.purchaseCost],
          ["Gross Margin", financialSummary.grossMargin],
        ].map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{formatValue(value, "money", getDocumentCurrency(detail))}</strong>
          </div>
        ))}
      </div>
      {costRows.length > 0 && (
        <section className="project-cost-panel">
          <div className="related-section-header">
            <div>
              <h3>Cost</h3>
              <span>
                {costSummary.invoiceCount} AP invoice{costSummary.invoiceCount === 1 ? "" : "s"} /{" "}
                {costSummary.supplierCount} supplier{costSummary.supplierCount === 1 ? "" : "s"}
              </span>
            </div>
            <div className="project-cost-summary">
              <div>
                <span>Cost</span>
                <strong>{formatValue(costSummary.cost, "money", getDocumentCurrency(detail))}</strong>
              </div>
              <div>
                <span>Paid</span>
                <strong>{formatValue(costSummary.paid, "money", getDocumentCurrency(detail))}</strong>
              </div>
              <div>
                <span>Outstanding</span>
                <strong>{formatValue(costSummary.outstanding, "money", getDocumentCurrency(detail))}</strong>
              </div>
            </div>
          </div>
          <div className="project-cost-table">
            <table>
              <thead>
                <tr>
                  <th>AP Invoice</th>
                  <th>Supplier</th>
                  <th>Date</th>
                  <th>Supplier Inv</th>
                  <th>Cost</th>
                  <th>Paid</th>
                  <th>Outstanding</th>
                  <th>Payments</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {costRows.map((row) => {
                  const hasError = Boolean(row.detail.__error);
                  const unlinking = unlinkingDocument === row.key;
                  return (
                    <tr key={row.key}>
                      <td>
                        <strong>{row.docNo}</strong>
                        {hasError && <span>{row.detail.__error}</span>}
                      </td>
                      <td>{row.supplier || "-"}</td>
                      <td>{readValue(row.detail, "docDate") || "-"}</td>
                      <td>{row.supplierInvoiceNo || "-"}</td>
                      <td className="number">{formatValue(row.amount, "money", row.currencyCode)}</td>
                      <td className="number">{formatValue(row.paid, "money", row.currencyCode)}</td>
                      <td className="number">
                        {formatValue(row.outstanding, "money", row.currencyCode)}
                      </td>
                      <td>{hasError ? "-" : row.paymentCount}</td>
                      <td>
                        <div className="project-link-row-actions">
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => onOpenDocument?.(row.moduleKey, row.docNo)}
                          >
                            <FileText aria-hidden="true" size={16} />
                            Open
                          </button>
                          <button
                            className="secondary-button danger-button"
                            disabled={unlinking}
                            type="button"
                            onClick={() => onUnlinkDocument?.(row.moduleKey, row.docNo)}
                          >
                            <Trash2 aria-hidden="true" size={16} />
                            {unlinking ? "Removing..." : "Unlink"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <div className="project-link-review">
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Document</th>
              <th>Date</th>
              <th>Status</th>
              <th>Amount</th>
              <th>Outstanding</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {documents.length === 0 ? (
              <tr className="empty-row">
                <td colSpan={7}>No linked documents</td>
              </tr>
            ) : (
              documents.map((document) => {
              const documentDetail = documentDetails[document.key] || {};
              const hasError = Boolean(documentDetail.__error);
              const currencyCode = getDocumentCurrency(documentDetail);
              const unlinking = unlinkingDocument === document.key;
              return (
                <tr key={document.key}>
                  <td>{document.label}</td>
                  <td>
                    <strong>{document.docNo}</strong>
                    {hasError && <span>{documentDetail.__error}</span>}
                  </td>
                  <td>{readValue(documentDetail, "docDate") || "-"}</td>
                  <td>{readValue(documentDetail, "status") || "-"}</td>
                  <td className="number">
                    {formatValue(getLinkedDocumentAmount(document, documentDetail), "money", currencyCode)}
                  </td>
                  <td className="number">
                    {formatValue(readValue(documentDetail, "outstanding"), "money", currencyCode)}
                  </td>
                  <td>
                    <div className="project-link-row-actions">
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => onOpenDocument?.(document.moduleKey, document.docNo)}
                      >
                        <FileText aria-hidden="true" size={16} />
                        Open
                      </button>
                      <button
                        className="secondary-button danger-button"
                        disabled={unlinking}
                        type="button"
                        onClick={() => onUnlinkDocument?.(document.moduleKey, document.docNo)}
                      >
                        <Trash2 aria-hidden="true" size={16} />
                        {unlinking ? "Removing..." : "Unlink"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

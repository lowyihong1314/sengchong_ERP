import {
  ArrowLeft,
  Download,
  Plus,
  RefreshCw,
  Users,
} from "lucide-react";
import { ItemFieldList, ItemFlag } from "../components/ItemFields.jsx";
import { hasValue, readValue } from "../lib/format.js";
import { getPdfExportLabel } from "../lib/pdf.js";

export function DebtorDetailPage({
  detail,
  exportingPdf,
  loading,
  status,
  onBack,
  onCreateProject,
  onExportStatement,
  onRefresh,
}) {
  const pageTitle = detail ? readValue(detail, "debtorCode") : "Debtor";
  const activeValue = readValue(detail, "isActive");
  const canExportStatement = Boolean(detail && onExportStatement);
  const chips = [
    ["Currency", readValue(detail, "currencyCode")],
    ["Term", readValue(detail, "displayTerm")],
    ["Agent", readValue(detail, "agent")],
  ].filter(([, value]) => hasValue(value));

  return (
    <section className="content-panel item-page">
      <div className="detail-page-header">
        <button className="secondary-button" type="button" onClick={onBack}>
          <ArrowLeft aria-hidden="true" size={16} />
          Back
        </button>
        <div>
          <h2>{pageTitle}</h2>
          <p>Customer account master</p>
        </div>
        <div className="page-header-actions">
          {detail && onCreateProject && (
            <button className="secondary-button" type="button" onClick={onCreateProject}>
              <Plus aria-hidden="true" size={16} />
              New Project
            </button>
          )}
          {canExportStatement && (
            <button
              className="secondary-button"
              disabled={exportingPdf}
              type="button"
              onClick={onExportStatement}
            >
              <Download aria-hidden="true" size={16} />
              {getPdfExportLabel("debtors", exportingPdf)}
            </button>
          )}
          <button className="icon-button" type="button" onClick={onRefresh} title="Refresh debtor">
            <RefreshCw aria-hidden="true" size={17} />
          </button>
        </div>
      </div>
      <div className={`status-bar ${status?.tone || ""}`}>{status?.text || "Ready"}</div>

      {loading ? (
        <div className="detail-empty">Loading...</div>
      ) : !detail ? (
        <div className="detail-empty">No debtor selected</div>
      ) : (
        <>
          <section className="item-hero">
            <div className="item-hero-icon">
              <Users aria-hidden="true" size={26} />
            </div>
            <div className="item-hero-main">
              <span>Debtor Master</span>
              <h2>{readValue(detail, "debtorCode")}</h2>
              <p>{readValue(detail, "debtorName") || readValue(detail, "companyName") || "No debtor name"}</p>
            </div>
            <div className="item-hero-flags">
              {hasValue(activeValue) && <ItemFlag label="Active" value={activeValue} />}
              {chips.map(([label, value]) => (
                <span className="item-flag" key={label}>
                  {label}: {value}
                </span>
              ))}
            </div>
          </section>

          <div className="item-detail-layout">
            <section className="item-card">
              <div className="item-card-header">
                <h3>Profile</h3>
              </div>
              <ItemFieldList
                detail={detail}
                fields={[
                  ["debtorCode", "Debtor Code"],
                  ["debtorName", "Debtor Name"],
                  ["companyName", "Company Name"],
                  ["displayTerm", "Payment Term"],
                  ["currencyCode", "Currency"],
                  ["creditLimit", "Credit Limit", "number"],
                ]}
              />
            </section>

            <section className="item-card">
              <div className="item-card-header">
                <h3>Sales</h3>
              </div>
              <ItemFieldList
                detail={detail}
                fields={[
                  ["agent", "Agent"],
                  ["area", "Area"],
                  ["isActive", "Active"],
                ]}
              />
            </section>

            <section className="item-card">
              <div className="item-card-header">
                <h3>Contact</h3>
              </div>
              <ItemFieldList
                detail={detail}
                fields={[
                  ["phone", "Phone"],
                  ["phone2", "Phone 2"],
                  ["fax", "Fax"],
                  ["email", "Email"],
                ]}
              />
            </section>

            <section className="item-card">
              <div className="item-card-header">
                <h3>Address</h3>
              </div>
              <ItemFieldList
                detail={detail}
                fields={[
                  ["address1", "Address 1"],
                  ["address2", "Address 2"],
                  ["address3", "Address 3"],
                  ["address4", "Address 4"],
                ]}
              />
            </section>
          </div>
        </>
      )}
    </section>
  );
}

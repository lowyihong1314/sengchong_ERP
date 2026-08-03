import {
  ArrowLeft,
  Download,
  Pencil,
  RefreshCw,
} from "lucide-react";
import { ArPaymentsPanel } from "../components/ArPaymentsPanel.jsx";
import { DebtorInfo } from "../components/DebtorInfo.jsx";
import { DetailDataTable } from "../components/DetailDataTable.jsx";
import { DocumentProjectsPanel } from "../components/DocumentProjectsPanel.jsx";
import { ProjectLinksPanel } from "../components/ProjectLinksPanel.jsx";
import { ProjectPhotosPanel } from "../components/ProjectPhotosPanel.jsx";
import { TotalSummary } from "../components/TotalSummary.jsx";
import { PROJECT_LINK_MODULES } from "../constants.js";
import {
  getCashBookLinkRows,
  getDebtorInfo,
  getDetailLineDocumentTarget,
  openDocumentTableRow,
} from "../lib/documents.js";
import { formatValue, getDetailLines, readValue } from "../lib/format.js";
import { getPdfExportLabel } from "../lib/pdf.js";
import { getDetailSummary, getDocumentCurrency } from "../lib/totals.js";

export function DetailPage({
  module,
  moduleKey,
  detail,
  detailKey,
  loading,
  status,
  debtors,
  exportingPdf,
  exportingPaymentRequest,
  onBack,
  onExportPdf,
  onExportPaymentRequest,
  onCreatePayment,
  onPaymentFormOpen,
  onOpenPayment,
  onOpenProject,
  onOpenDocument,
  onEditProject,
  onLinkProject,
  onLoadProjects,
  onCreateProjectFromDocument,
  onDeleteProjectPhoto,
  onLinkProjectDocument,
  onUpdateProjectPhoto,
  onUploadProjectPhotos,
  projectChoices,
  projectChoicesLoading,
  projectPhotoSaving,
  projectFinancialSyncing,
  projectDocumentUnlinking,
  paymentMethods,
  creatingPayment,
  token,
  onRefresh,
  onSyncProjectFinancials,
  onUnlinkProjectDocument,
}) {
  const lines = getDetailLines(module, detail);
  const pageTitle = detail ? readValue(detail, module.rowKey) : module.singular;
  const debtorInfo = getDebtorInfo(detail, debtors);
  const detailSummary = detail ? getDetailSummary(module, detail) : [];
  const canExportPdf = Boolean(detail && onExportPdf);
  const currencyCode = getDocumentCurrency(detail);
  const linkedProjects = detail?.projects || [];
  const showLines = (module.detailLineColumns || []).length > 0;
  const cashBookLinks = getCashBookLinkRows(moduleKey, detail);

  return (
    <section className="content-panel detail-page">
      <div className="detail-page-header">
        <button className="secondary-button" type="button" onClick={onBack}>
          <ArrowLeft aria-hidden="true" size={16} />
          Back
        </button>
        <div>
          <h2>{pageTitle}</h2>
          <p>{module.singular} detail</p>
        </div>
        <div className="page-header-actions">
          {module.editable && detail && onEditProject && (
            <button className="secondary-button" type="button" onClick={onEditProject}>
              <Pencil aria-hidden="true" size={16} />
              Edit {module.singular}
            </button>
          )}
          {canExportPdf && (
            <button
              className="secondary-button"
              disabled={exportingPdf}
              type="button"
              onClick={onExportPdf}
            >
              <Download aria-hidden="true" size={16} />
              {getPdfExportLabel(moduleKey, exportingPdf)}
            </button>
          )}
          <button className="icon-button" type="button" onClick={onRefresh} title="Refresh detail">
            <RefreshCw aria-hidden="true" size={17} />
          </button>
        </div>
      </div>
      <div className={`status-bar ${status?.tone || ""}`}>{status?.text || "Ready"}</div>

      {loading ? (
        <div className="detail-empty">Loading...</div>
      ) : !detail ? (
        <div className="detail-empty">No record selected</div>
      ) : (
        <>
          <DebtorInfo debtor={debtorInfo} />

          <dl className="detail-grid">
            {module.detailFields.map(([key, label, kind]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>{formatValue(readValue(detail, key), kind, currencyCode)}</dd>
              </div>
            ))}
          </dl>

          {moduleKey === "projects" && (
            <>
              <ProjectLinksPanel
                detail={detail}
                token={token}
                onLinkDocument={onLinkProjectDocument}
                syncingFinancials={projectFinancialSyncing}
                unlinkingDocument={projectDocumentUnlinking}
                onOpenDocument={onOpenDocument}
                onRefreshProject={onRefresh}
                onSyncFinancials={onSyncProjectFinancials}
                onUnlinkDocument={onUnlinkProjectDocument}
              />
              <ProjectPhotosPanel
                detail={detail}
                saving={projectPhotoSaving}
                token={token}
                onDeletePhoto={onDeleteProjectPhoto}
                onUpdatePhoto={onUpdateProjectPhoto}
                onUploadPhotos={onUploadProjectPhotos}
              />
            </>
          )}

          {PROJECT_LINK_MODULES.has(moduleKey) && (
            <DocumentProjectsPanel
              availableProjects={projectChoices}
              currencyCode={currencyCode}
              linkedProjects={linkedProjects}
              loadingProjects={projectChoicesLoading}
              onCreateProject={moduleKey === "ap-invoices" ? null : onCreateProjectFromDocument}
              onLinkProject={onLinkProject}
              onLoadProjects={onLoadProjects}
              onOpenProject={onOpenProject}
            />
          )}

          {module.title === "Invoices" && (
            <ArPaymentsPanel
              creatingPayment={creatingPayment}
              detail={detail}
              exportingPaymentRequest={exportingPaymentRequest}
              paymentMethods={paymentMethods}
              onCreatePayment={onCreatePayment}
              onExportPaymentRequest={onExportPaymentRequest}
              onOpenPayment={onOpenPayment}
              onPrepareCreate={onPaymentFormOpen}
            />
          )}

          {module.sourceDocumentColumns && (
            <DetailDataTable
              columns={module.sourceDocumentColumns}
              currencyCode={currencyCode}
              emptyText="No source documents"
              onRowClick={
                onOpenDocument ? (row) => openDocumentTableRow(row, onOpenDocument) : null
              }
              rows={detail.sourceDocuments || []}
              title={module.sourceDocumentTitle || "Source Documents"}
            />
          )}

          {cashBookLinks.length > 0 && (
            <DetailDataTable
              columns={[
                ["documentType", "Type"],
                ["docNo", "Doc No"],
                ["docDate", "Date"],
                ["accountCode", "Account"],
                ["accountName", "Name"],
                ["description", "Description"],
                ["amount", "Amount", "money"],
                ["localAmount", "Local", "money"],
                ["status", "Status"],
              ]}
              currencyCode={currencyCode}
              emptyText="No cash book linked"
              onRowClick={
                onOpenDocument ? (row) => openDocumentTableRow(row, onOpenDocument) : null
              }
              rows={cashBookLinks}
              title="Linked Cash Book"
            />
          )}

          {module.paymentLineColumns && (
            <DetailDataTable
              columns={module.paymentLineColumns}
              currencyCode={currencyCode}
              emptyText="No payment lines"
              rows={detail.paymentLines || []}
              title={module.paymentLineTitle || "Payment Lines"}
            />
          )}

          {module.refundLineColumns && (
            <DetailDataTable
              columns={module.refundLineColumns}
              currencyCode={currencyCode}
              emptyText="No refunds"
              rows={detail.refundLines || []}
              title={module.refundLineTitle || "Refunds"}
            />
          )}

          {module.forfeitLineColumns && (
            <DetailDataTable
              columns={module.forfeitLineColumns}
              currencyCode={currencyCode}
              emptyText="No forfeits"
              rows={detail.forfeitLines || []}
              title={module.forfeitLineTitle || "Forfeits"}
            />
          )}

          {module.bankTransactionColumns && (
            <DetailDataTable
              columns={module.bankTransactionColumns}
              currencyCode={currencyCode}
              emptyText="No bank transactions"
              rows={detail.bankTransactions || []}
              title={module.bankTransactionTitle || "Bank Transactions"}
            />
          )}

          {showLines && (
            <>
              <div className="line-table-title">{module.detailLineTitle || "Lines"}</div>
              <div className="detail-lines">
                <table>
                  <thead>
                    <tr>
                      {module.detailLineColumns.map(([, label]) => (
                        <th key={`${detailKey}-${label}`}>{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {lines.length === 0 ? (
                      <tr className="empty-row">
                        <td colSpan={module.detailLineColumns.length}>No lines</td>
                      </tr>
                    ) : (
                      lines.map((line, index) => {
                        const target = getDetailLineDocumentTarget(moduleKey, line);
                        const clickable = Boolean(target && onOpenDocument);
                        return (
                          <tr
                            className={clickable ? "clickable-row" : ""}
                            key={line.dtlKey || line.seq || `${detailKey}-${index}`}
                            onClick={
                              clickable
                                ? () => onOpenDocument(target.moduleKey, target.key)
                                : undefined
                            }
                          >
                            {module.detailLineColumns.map(([key, , kind]) => (
                              <td
                                className={kind === "number" || kind === "money" ? "number" : ""}
                                key={key}
                              >
                                {formatValue(readValue(line, key), kind, currencyCode)}
                              </td>
                            ))}
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {detailSummary.length > 0 && <TotalSummary items={detailSummary} />}
        </>
      )}
    </section>
  );
}

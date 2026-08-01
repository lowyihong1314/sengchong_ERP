import {
  Eye,
  Save,
} from "lucide-react";
import { BANK_RECON_FILTERS } from "../constants.js";
import { formatValue, readValue } from "../lib/format.js";

export function BankingListControls({
  accountChoices,
  actualBalance,
  commitLoading,
  filters,
  previewLoading,
  reconcileDraft,
  selectedCount,
  statementDate,
  summary,
  visibleSummary,
  onActualBalanceChange,
  onClearSelection,
  onCommitReconcile,
  onFilterChange,
  onPreviewReconcile,
  onSelectVisibleOpen,
  onStatementDateChange,
}) {
  const selectedAccount = filters.account || "";
  const selectedRecon = filters.recon || "all";
  const previewRows = Array.isArray(reconcileDraft?.data) ? reconcileDraft.data : [];
  const missingKeys = Array.isArray(reconcileDraft?.missingKeys) ? reconcileDraft.missingKeys : [];

  return (
    <section className="banking-panel">
      <div className="banking-filters">
        <label className="form-field" htmlFor="bank-account-filter">
          <span>Bank Account</span>
          <select
            id="bank-account-filter"
            value={selectedAccount}
            onChange={(event) => onFilterChange("account", event.target.value)}
          >
            <option value="">All accounts</option>
            {accountChoices.map((choice) => (
              <option key={choice.value} value={choice.value}>
                {choice.label}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field" htmlFor="bank-recon-filter">
          <span>Recon Status</span>
          <select
            id="bank-recon-filter"
            value={selectedRecon}
            onChange={(event) => onFilterChange("recon", event.target.value)}
          >
            {BANK_RECON_FILTERS.map((filter) => (
              <option key={filter.value} value={filter.value}>
                {filter.label}
              </option>
            ))}
          </select>
        </label>
        <div className="banking-visible-summary">
          <div>
            <span>Visible</span>
            <strong>{visibleSummary.count}</strong>
          </div>
          <div>
            <span>Open</span>
            <strong>{formatValue(visibleSummary.open, "money")}</strong>
          </div>
          <div>
            <span>Reconciled</span>
            <strong>{formatValue(visibleSummary.reconciled, "money")}</strong>
          </div>
        </div>
      </div>

      <div className="bank-reconcile-draft">
        <div className="bank-reconcile-controls">
          <div className="bank-reconcile-count">
            <span>Selected</span>
            <strong>{selectedCount}</strong>
          </div>
          <label className="form-field" htmlFor="bank-reconcile-statement-date">
            <span>Statement Date</span>
            <input
              id="bank-reconcile-statement-date"
              type="date"
              value={statementDate}
              onChange={(event) => onStatementDateChange(event.target.value)}
            />
          </label>
          <label className="form-field" htmlFor="bank-reconcile-actual-balance">
            <span>Statement Balance</span>
            <input
              id="bank-reconcile-actual-balance"
              type="number"
              step="0.01"
              value={actualBalance}
              onChange={(event) => onActualBalanceChange(event.target.value)}
            />
          </label>
          <div className="bank-reconcile-actions">
            <button className="secondary-button" type="button" onClick={onSelectVisibleOpen}>
              Select Visible Open
            </button>
            <button
              className="secondary-button"
              disabled={selectedCount === 0}
              type="button"
              onClick={onClearSelection}
            >
              Clear
            </button>
            <button
              className="primary-button"
              disabled={previewLoading || selectedCount === 0 || !statementDate}
              type="button"
              onClick={onPreviewReconcile}
            >
              <Eye aria-hidden="true" size={16} />
              {previewLoading ? "Previewing..." : "Preview Reconcile"}
            </button>
            <button
              className="primary-button"
              disabled={commitLoading || !reconcileDraft || !actualBalance}
              type="button"
              onClick={onCommitReconcile}
            >
              <Save aria-hidden="true" size={16} />
              {commitLoading ? "Committing..." : "Commit AutoCount"}
            </button>
          </div>
        </div>

        {reconcileDraft && (
          <div className="bank-reconcile-preview">
            <div className="bank-reconcile-preview-header">
              <div>
                <strong>{reconcileDraft.matchedCount || 0} matched</strong>
                <span>
                  {formatValue(reconcileDraft.totalAmount, "money")} / {reconcileDraft.statementDate}
                </span>
              </div>
              <div className="bank-reconcile-mode">
                {reconcileDraft.writeEnabled ? "Ready" : "API write required"}
              </div>
            </div>
            {missingKeys.length > 0 && (
              <div className="bank-reconcile-missing">
                Missing: {missingKeys.join(", ")}
              </div>
            )}
            <div className="bank-reconcile-table">
              <table>
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>Cash Book</th>
                    <th>Bank</th>
                    <th>Amount</th>
                    <th>Current</th>
                    <th>Next</th>
                    <th>Statement</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRows.length === 0 ? (
                    <tr className="empty-row">
                      <td colSpan={7}>No preview rows</td>
                    </tr>
                  ) : (
                    previewRows.map((row) => (
                      <tr key={readValue(row, "bankTransKey")}>
                        <td>{readValue(row, "bankTransKey")}</td>
                        <td>{readValue(row, "cashBookDocNo") || readValue(row, "docNo")}</td>
                        <td>{readValue(row, "bankAccount")}</td>
                        <td className="number">{formatValue(readValue(row, "bankAmount"), "money")}</td>
                        <td>{readValue(row, "currentReconStatusLabel")}</td>
                        <td>{readValue(row, "nextReconStatusLabel")}</td>
                        <td>{readValue(row, "nextBankStatementDate") || "-"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div className="bank-account-summary">
        {summary.accounts.length === 0 ? (
          <div className="bank-account-empty">No bank transactions loaded</div>
        ) : (
          summary.accounts.map((account) => {
            const active = selectedAccount === account.account;
            return (
              <button
                className={`bank-account-chip ${active ? "active" : ""}`}
                key={account.account}
                type="button"
                onClick={() => onFilterChange("account", active ? "" : account.account)}
              >
                <span>{account.account}</span>
                <strong>{formatValue(account.open, "money")}</strong>
                <small>
                  {account.openCount} open / {account.reconciledCount} reconciled
                </small>
              </button>
            );
          })
        )}
      </div>
    </section>
  );
}

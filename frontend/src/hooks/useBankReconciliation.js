import React from "react";

import { today } from "../constants.js";
import { requestJson } from "../lib/api.js";
import {
  filterBankTransactions,
  getBankAccountChoices,
  getBankReconState,
  getBankTransactionKey,
  getBankTransactionSummary,
} from "../lib/banking.js";
import { getDetailCacheKey } from "../lib/routing.js";

/**
 * Bank transaction filtering, selection, and the two-step AutoCount
 * reconciliation flow (preview, then commit through BankRecon.Save).
 *
 * Also owns displayedRows, because on the bank-transactions module the visible
 * list is the account/recon-filtered slice rather than the raw search result.
 */
export function useBankReconciliation({
  activeModule,
  rows,
  filteredRows,
  authHeaders,
  handleAuthError,
  setStatus,
  loadModule,
  detailCacheRef,
  moduleStageRef,
}) {
  const [bankFilters, setBankFilters] = React.useState({ account: "", recon: "all" });
  const [selectedBankTransKeys, setSelectedBankTransKeys] = React.useState([]);
  const [bankReconcileStatementDate, setBankReconcileStatementDate] = React.useState(() => today());
  const [bankReconcileActualBalance, setBankReconcileActualBalance] = React.useState("");
  const [bankReconcileDraft, setBankReconcileDraft] = React.useState(null);
  const [bankReconcilePreviewLoading, setBankReconcilePreviewLoading] = React.useState(false);
  const [bankReconcileSaving, setBankReconcileSaving] = React.useState(false);

  const bankAccountChoices = React.useMemo(
    () => (activeModule === "bank-transactions" ? getBankAccountChoices(rows) : []),
    [activeModule, rows]
  );
  const bankSummary = React.useMemo(
    () => (activeModule === "bank-transactions" ? getBankTransactionSummary(rows) : null),
    [activeModule, rows]
  );
  const displayedRows = React.useMemo(
    () =>
      activeModule === "bank-transactions"
        ? filterBankTransactions(filteredRows, bankFilters)
        : filteredRows,
    [activeModule, bankFilters, filteredRows]
  );
  const visibleBankSummary = React.useMemo(
    () =>
      activeModule === "bank-transactions"
        ? getBankTransactionSummary(displayedRows)
        : null,
    [activeModule, displayedRows]
  );
  const selectedBankTransSet = React.useMemo(
    () => new Set(selectedBankTransKeys),
    [selectedBankTransKeys]
  );
  const visibleOpenBankTransKeys = React.useMemo(
    () =>
      activeModule === "bank-transactions"
        ? displayedRows
            .filter((row) => getBankReconState(row) === "open")
            .map((row) => getBankTransactionKey(row))
            .filter(Boolean)
        : [],
    [activeModule, displayedRows]
  );

  function updateBankFilter(name, value) {
    setBankFilters((current) => ({ ...current, [name]: value }));
  }

  function toggleBankTransSelection(key, checked) {
    const normalizedKey = String(key || "").trim();
    if (!normalizedKey) return;

    setSelectedBankTransKeys((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(normalizedKey);
      } else {
        next.delete(normalizedKey);
      }
      return Array.from(next);
    });
    setBankReconcileDraft(null);
  }

  function toggleVisibleOpenBankTransSelection(checked) {
    if (checked) {
      setSelectedBankTransKeys((current) =>
        Array.from(new Set([...current, ...visibleOpenBankTransKeys]))
      );
    } else {
      const visibleKeys = new Set(visibleOpenBankTransKeys);
      setSelectedBankTransKeys((current) => current.filter((key) => !visibleKeys.has(key)));
    }
    setBankReconcileDraft(null);
  }

  function selectVisibleOpenBankTransactions() {
    toggleVisibleOpenBankTransSelection(true);
  }

  function clearBankTransSelection() {
    setSelectedBankTransKeys([]);
    setBankReconcileDraft(null);
  }

  async function previewBankReconciliation() {
    if (selectedBankTransKeys.length === 0) {
      setStatus({ tone: "error", text: "Select bank transactions first" });
      return;
    }
    if (!bankReconcileStatementDate) {
      setStatus({ tone: "error", text: "Statement date is required" });
      return;
    }

    try {
      setBankReconcilePreviewLoading(true);
      setStatus({ tone: "", text: "Preparing reconciliation preview..." });
      const payload = await requestJson("/api/autocount/bank-transactions/reconcile-preview", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          bankTransKeys: selectedBankTransKeys,
          statementDate: bankReconcileStatementDate,
          reconStatus: "reconciled",
        }),
      });
      setBankReconcileDraft(payload);
      setStatus({
        tone: "ok",
        text: `Previewed ${payload.matchedCount || 0} bank transaction${
          payload.matchedCount === 1 ? "" : "s"
        }`,
      });
    } catch (error) {
      handleAuthError(error);
      setBankReconcileDraft(null);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setBankReconcilePreviewLoading(false);
    }
  }

  async function commitBankReconciliation() {
    if (!bankReconcileDraft || selectedBankTransKeys.length === 0) {
      setStatus({ tone: "error", text: "Preview reconciliation first" });
      return;
    }
    const actualBalance = Number(bankReconcileActualBalance);
    if (!Number.isFinite(actualBalance)) {
      setStatus({ tone: "error", text: "Statement balance is required" });
      return;
    }
    if (
      !window.confirm(
        `Commit ${selectedBankTransKeys.length} bank transaction${
          selectedBankTransKeys.length === 1 ? "" : "s"
        } to AutoCount?`
      )
    ) {
      return;
    }

    try {
      setBankReconcileSaving(true);
      setStatus({ tone: "", text: "Committing bank reconciliation..." });
      const payload = await requestJson("/api/autocount/bank-transactions/reconcile", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          bankTransKeys: selectedBankTransKeys,
          statementDate: bankReconcileStatementDate,
          actualBankStatementBalance: bankReconcileActualBalance,
        }),
      });

      selectedBankTransKeys.forEach((key) => {
        detailCacheRef.current.delete(getDetailCacheKey("bank-transactions", key));
      });
      moduleStageRef.current.delete("bank-transactions");
      moduleStageRef.current.delete("cash-book");
      setSelectedBankTransKeys([]);
      setBankReconcileDraft(null);
      await loadModule("bank-transactions", { refresh: true });
      setStatus({
        tone: "ok",
        text: `Committed ${payload.matchedCount || 0} bank transaction${
          payload.matchedCount === 1 ? "" : "s"
        }`,
      });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setBankReconcileSaving(false);
    }
  }

  // Full teardown, used when the whole workspace resets (logout, company switch).
  const resetBankReconciliation = React.useCallback(() => {
    setBankFilters({ account: "", recon: "all" });
    setSelectedBankTransKeys([]);
    setBankReconcileStatementDate(today());
    setBankReconcileActualBalance("");
    setBankReconcileDraft(null);
    setBankReconcilePreviewLoading(false);
    setBankReconcileSaving(false);
  }, []);

  // Narrower teardown that runs when the token disappears. The set of fields
  // cleared here is deliberately kept identical to the pre-refactor behaviour.
  const clearBankReconciliationOnSignOut = React.useCallback(() => {
    setBankFilters({ account: "", recon: "all" });
    setSelectedBankTransKeys([]);
    setBankReconcileStatementDate(today());
    setBankReconcileActualBalance("");
    setBankReconcileDraft(null);
    setBankReconcilePreviewLoading(false);
    setBankReconcileSaving(false);
  }, []);

  return {
    bankAccountChoices,
    bankFilters,
    bankReconcileActualBalance,
    bankReconcileDraft,
    bankReconcilePreviewLoading,
    bankReconcileSaving,
    bankReconcileStatementDate,
    bankSummary,
    displayedRows,
    selectedBankTransKeys,
    selectedBankTransSet,
    visibleBankSummary,
    visibleOpenBankTransKeys,
    clearBankReconciliationOnSignOut,
    clearBankTransSelection,
    commitBankReconciliation,
    previewBankReconciliation,
    resetBankReconciliation,
    selectVisibleOpenBankTransactions,
    setBankReconcileActualBalance,
    setBankReconcileDraft,
    setBankReconcileStatementDate,
    toggleBankTransSelection,
    toggleVisibleOpenBankTransSelection,
    updateBankFilter,
  };
}

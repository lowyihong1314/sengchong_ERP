import React from "react";
import {
  Download,
  Plus,
  Save,
} from "lucide-react";
import { DetailDataTable } from "./DetailDataTable.jsx";
import { REQUEST_AMOUNT_PERCENTAGES, today } from "../constants.js";
import {
  formatValue,
  hasValue,
  isFlagOn,
  readValue,
  toNumber,
} from "../lib/format.js";
import { getDocumentCurrency } from "../lib/totals.js";

export function ArPaymentsPanel({
  detail,
  paymentMethods,
  creatingPayment,
  exportingPaymentRequest,
  onCreatePayment,
  onExportPaymentRequest,
  onOpenPayment,
  onPrepareCreate,
}) {
  const payments = detail?.arPayments || [];
  const currencyCode = getDocumentCurrency(detail);
  const [showForm, setShowForm] = React.useState(false);
  const [showRequestForm, setShowRequestForm] = React.useState(false);
  const [draft, setDraft] = React.useState(null);
  const [requestDraft, setRequestDraft] = React.useState({ amount: "" });
  const invoicePaymentAmount = readValue(detail, "paymentAmt");
  const paidAmount = hasValue(invoicePaymentAmount)
    ? invoicePaymentAmount
    : payments.reduce((sum, payment) => {
      return sum + toNumber(readValue(payment, "paidAmount"), 0);
  }, 0);
  const outstandingAmount = Math.max(toNumber(readValue(detail, "outstanding"), 0), 0);
  const hasOutstanding = outstandingAmount > 0;
  const invoiceTotalAmount = Math.max(
    toNumber(
      readValue(detail, "total"),
      toNumber(
        readValue(detail, "netTotal"),
        toNumber(readValue(detail, "finalTotal"), outstandingAmount)
      )
    ),
    0
  );
  const requestPercentBase = invoiceTotalAmount > 0 ? invoiceTotalAmount : outstandingAmount;
  const requestAmount = Math.min(Math.max(toNumber(requestDraft.amount, 0), 0), outstandingAmount);
  const requestBalanceAfter =
    requestAmount > 0 ? Math.max(outstandingAmount - requestAmount, 0) : outstandingAmount;
  const selectedPaymentMethod = (paymentMethods || []).find(
    (method) => readValue(method, "paymentMethod") === draft?.paymentMethod
  );
  React.useEffect(() => {
    if (!showForm || !draft || !paymentMethods?.length) return;
    const hasMethod = paymentMethods.some(
      (method) => readValue(method, "paymentMethod") === draft.paymentMethod
    );
    if (hasMethod) return;

    const firstMethod = paymentMethods[0];
    setDraft((current) => ({
      ...(current || {}),
      paymentMethod: readValue(firstMethod, "paymentMethod"),
      paymentBy: readValue(firstMethod, "paymentBy"),
    }));
  }, [draft, paymentMethods, showForm]);
  const openPayment = (payment) => {
    const paymentKey = readValue(payment, "paymentDocNo") || readValue(payment, "paymentDocKey");
    if (paymentKey && onOpenPayment) {
      onOpenPayment(paymentKey);
    }
  };
  const openForm = () => {
    if (onPrepareCreate) onPrepareCreate();
    const firstMethod = (paymentMethods || [])[0] || {};
    setDraft({
      amount: "",
      docDate: today(),
      paymentMethod: readValue(firstMethod, "paymentMethod") || "CASH",
      paymentBy: readValue(firstMethod, "paymentBy"),
      chequeNo: "",
      description: `Payment for ${readValue(detail, "docNo")}`,
    });
    setShowForm(true);
  };
  const updateDraft = (name, value) => {
    setDraft((current) => {
      const next = { ...(current || {}), [name]: value };
      if (name === "paymentMethod") {
        const method = (paymentMethods || []).find(
          (item) => readValue(item, "paymentMethod") === value
        );
        next.paymentBy = method ? readValue(method, "paymentBy") : "";
      }
      return next;
    });
  };
  const submitPayment = async (event) => {
    event.preventDefault();
    if (!draft || !onCreatePayment) return;
    await onCreatePayment({
      invoiceDocKey: readValue(detail, "docKey"),
      invoiceDocNo: readValue(detail, "docNo"),
      debtorCode: readValue(detail, "debtorCode"),
      amount: draft.amount,
      docDate: draft.docDate,
      paymentMethod: draft.paymentMethod,
      paymentBy: draft.paymentBy,
      chequeNo: draft.chequeNo,
      description: draft.description,
    });
    setShowForm(false);
  };
  const openRequestForm = () => {
    setRequestDraft({ amount: "" });
    setShowRequestForm(true);
  };
  const clampRequestAmountInput = (value) => {
    if (value === "") return "";

    const amount = toNumber(value, 0);
    if (amount < 0) return "";
    if (hasOutstanding && amount > outstandingAmount) return outstandingAmount.toFixed(2);
    return value;
  };
  const setRequestAmount = (value) => {
    setRequestDraft({ amount: clampRequestAmountInput(value) });
  };
  const setRequestPercent = (percent) => {
    if (!hasOutstanding) {
      setRequestDraft({ amount: "" });
      return;
    }

    const amount = requestPercentBase * (percent / 100);
    setRequestDraft({ amount: Math.min(amount, outstandingAmount).toFixed(2) });
  };
  const submitPaymentRequest = async (event) => {
    event.preventDefault();
    if (!onExportPaymentRequest) return;
    const clampedAmount = requestAmount > 0 ? requestAmount.toFixed(2) : requestDraft.amount;
    setRequestDraft({ amount: clampedAmount });
    const ok = await onExportPaymentRequest(clampedAmount);
    if (ok !== false) {
      setShowRequestForm(false);
    }
  };

  return (
    <section className="ar-related-block">
      <div className="ar-related-summary">
        <div>
          <span>AR Paid</span>
          <strong>{formatValue(paidAmount, "money", currencyCode)}</strong>
        </div>
        <div>
          <span>Payment Records</span>
          <strong>{payments.length}</strong>
        </div>
        <div>
          <span>Outstanding</span>
          <strong>{formatValue(readValue(detail, "outstanding"), "money", currencyCode) || "-"}</strong>
        </div>
      </div>

      <div className="ar-payment-toolbar">
        <button className="secondary-button" type="button" onClick={openForm}>
          <Plus aria-hidden="true" size={16} />
          New AR Payment
        </button>
        {onExportPaymentRequest && (
          <button className="secondary-button" type="button" onClick={openRequestForm}>
            <Download aria-hidden="true" size={16} />
            Payment Request
          </button>
        )}
      </div>

      {showForm && (
        <form className="ar-payment-form" onSubmit={submitPayment}>
          <label className="form-field">
            <span>Amount</span>
            <input
              min="0.01"
              step="0.01"
              type="number"
              value={draft?.amount ?? ""}
              onChange={(event) => updateDraft("amount", event.target.value)}
              required
            />
          </label>
          <label className="form-field">
            <span>Date</span>
            <input
              type="date"
              value={draft?.docDate ?? today()}
              onChange={(event) => updateDraft("docDate", event.target.value)}
              required
            />
          </label>
          <label className="form-field">
            <span>Payment Method</span>
            <select
              value={draft?.paymentMethod ?? ""}
              onChange={(event) => updateDraft("paymentMethod", event.target.value)}
              required
            >
              {(paymentMethods || []).length === 0 && <option value="CASH">CASH</option>}
              {(paymentMethods || []).map((method) => {
                const value = readValue(method, "paymentMethod");
                return (
                  <option key={value} value={value}>
                    {value}
                  </option>
                );
              })}
            </select>
          </label>
          <label className="form-field">
            <span>Reference</span>
            <input
              value={draft?.chequeNo ?? ""}
              onChange={(event) => updateDraft("chequeNo", event.target.value)}
              placeholder={isFlagOn(readValue(selectedPaymentMethod, "acceptChequeNo")) ? "Cheque / transfer ref" : ""}
            />
          </label>
          <label className="form-field span-2">
            <span>Description</span>
            <input
              value={draft?.description ?? ""}
              onChange={(event) => updateDraft("description", event.target.value)}
            />
          </label>
          <div className="ar-payment-form-actions">
            <button className="secondary-button" type="button" onClick={() => setShowForm(false)}>
              Cancel
            </button>
            <button className="primary-button" disabled={creatingPayment} type="submit">
              <Save aria-hidden="true" size={16} />
              {creatingPayment ? "Saving..." : "Save Payment"}
            </button>
          </div>
        </form>
      )}

      {showRequestForm && (
        <form className="ar-payment-form" onSubmit={submitPaymentRequest}>
          <div className="form-field request-amount-field">
            <span>Request Amount</span>
            <input
              min="0.01"
              max={outstandingAmount || undefined}
              step="0.01"
              type="number"
              value={requestDraft.amount}
              onChange={(event) => setRequestAmount(event.target.value)}
              required
            />
            <div className="amount-percent-buttons" aria-label="Quick request amount">
              {REQUEST_AMOUNT_PERCENTAGES.map((percent) => (
                <button
                  className="percent-button"
                  disabled={!hasOutstanding || exportingPaymentRequest}
                  key={percent}
                  onClick={() => setRequestPercent(percent)}
                  type="button"
                >
                  {percent}%
                </button>
              ))}
            </div>
          </div>
          <div className="form-field">
            <span>Invoice Total</span>
            <strong>{formatValue(requestPercentBase, "money", currencyCode)}</strong>
          </div>
          <div className="form-field">
            <span>Outstanding</span>
            <strong>{formatValue(outstandingAmount, "money", currencyCode)}</strong>
          </div>
          <div className="form-field">
            <span>Balance After Request</span>
            <strong>{formatValue(requestBalanceAfter, "money", currencyCode)}</strong>
          </div>
          <div className="ar-payment-form-actions">
            <button className="secondary-button" type="button" onClick={() => setShowRequestForm(false)}>
              Cancel
            </button>
            <button
              className="primary-button"
              disabled={exportingPaymentRequest || !hasOutstanding || requestAmount <= 0}
              type="submit"
            >
              <Download aria-hidden="true" size={16} />
              {exportingPaymentRequest ? "Preparing..." : "Print Request"}
            </button>
          </div>
        </form>
      )}

      <DetailDataTable
        columns={[
          ["paymentDocNo", "Payment"],
          ["paymentDate", "Date"],
          ["paymentDescription", "Description"],
          ["paymentMethod", "Method"],
          ["chequeNo", "Cheque No"],
          ["paidAmount", "Paid", "money"],
          ["discountAmount", "Discount", "money"],
          ["status", "Status"],
        ]}
        currencyCode={currencyCode}
        emptyText="No AR payment linked to this invoice"
        onRowClick={onOpenPayment ? openPayment : null}
        rows={payments}
        title="AR Payments"
      />
    </section>
  );
}

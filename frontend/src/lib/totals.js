import { getDetailLines, readValue, toNumber } from "./format.js";

export function applyDiscount(amount, discount) {
  if (discount === null || discount === undefined || discount === "") return amount;
  const text = String(discount).trim();
  if (!text) return amount;

  if (text.endsWith("%")) {
    const rate = toNumber(text.slice(0, -1), 0);
    return amount - amount * (rate / 100);
  }

  return amount - toNumber(text, 0);
}

export function getDocumentCurrency(source) {
  return readValue(source, "currencyCode") || "MYR";
}

export function getLineGross(module, line) {
  if (!line) return 0;

  if (module.rowKey === "itemCode") {
    return toNumber(readValue(line, "price"), 0);
  }

  if (module.title === "Invoices") {
    return toNumber(
      readValue(line, "amount"),
      toNumber(readValue(line, "subTotal"), toNumber(readValue(line, "netAmount"), 0))
    );
  }

  return toNumber(readValue(line, "qty"), 0) * toNumber(readValue(line, "unitPrice"), 0);
}

export function getLineNetBeforeTax(module, line) {
  if (!line) return 0;

  if (module.title === "Invoices") {
    return toNumber(readValue(line, "amount"), toNumber(readValue(line, "netAmount"), 0));
  }

  const discount = readValue(line, "discount");
  if (discount !== "") {
    return applyDiscount(getLineGross(module, line), discount);
  }

  const existingSubtotal = readValue(line, "subTotal");
  if (existingSubtotal !== "") return toNumber(existingSubtotal, 0);

  return applyDiscount(getLineGross(module, line), readValue(line, "discount"));
}

export function getLineDiscount(module, line) {
  return Math.max(0, getLineGross(module, line) - getLineNetBeforeTax(module, line));
}

export function getLineTax(line) {
  return toNumber(readValue(line, "tax"), 0);
}

export function getLineTotal(module, line) {
  if (!line) return 0;

  if (module.rowKey === "itemCode") {
    return toNumber(readValue(line, "price"), 0);
  }

  if (module.rowKey === "docNo" && module.title === "Invoices") {
    return toNumber(readValue(line, "netAmount"), toNumber(readValue(line, "amount"), 0));
  }

  const existingSubtotal = readValue(line, "subTotal");
  if (existingSubtotal !== "") return toNumber(existingSubtotal, 0);

  const amount = toNumber(readValue(line, "qty"), 0) * toNumber(readValue(line, "unitPrice"), 0);
  return applyDiscount(amount, readValue(line, "discount"));
}

export function getFormLineTotal(module, line) {
  if (module.rowKey === "itemCode") {
    return toNumber(line?.price, 0);
  }

  if (module.title === "Invoices") {
    return toNumber(line?.amount, 0);
  }

  const amount = toNumber(line?.qty, 0) * toNumber(line?.unitPrice, 0);
  return applyDiscount(amount, line?.discount);
}

export function getFormLineGross(module, line) {
  if (module.rowKey === "itemCode") {
    return toNumber(line?.price, 0);
  }

  if (module.title === "Invoices") {
    return toNumber(line?.amount, 0);
  }

  return toNumber(line?.qty, 0) * toNumber(line?.unitPrice, 0);
}

export function getFormLineDiscount(module, line) {
  return Math.max(0, getFormLineGross(module, line) - getFormLineTotal(module, line));
}

export function getFormLineTax(line) {
  return toNumber(line?.tax, 0);
}

export function getDetailSummary(module, detail) {
  const lines = getDetailLines(module, detail);

  if (module.rowKey === "projectCode") {
    return [
      ["Quoted", readValue(detail, "quotedTotal"), "number"],
      ["Collected", readValue(detail, "collectedTotal"), "number"],
      ["Outstanding", readValue(detail, "outstandingAmount"), "number"],
      ["Actual Cost", readValue(detail, "actualCost"), "number"],
      ["Margin", readValue(detail, "margin"), "number"],
    ];
  }

  if (module.rowKey === "itemCode") {
    const lineTotal = lines.reduce((sum, line) => sum + getLineTotal(module, line), 0);
    const primary = lines[0] || {};
    return [
      ["UOM Rows", lines.length],
      ["Primary Price", readValue(primary, "price"), "number"],
      ["Cost", readValue(primary, "cost"), "number"],
      ["Rate", readValue(primary, "rate"), "number"],
    ];
  }

  const currencyCode = getDocumentCurrency(detail);
  const lineTotal = lines.reduce((sum, line) => sum + getLineGross(module, line), 0);
  const discount = lines.reduce((sum, line) => sum + getLineDiscount(module, line), 0);
  const taxValue = readValue(detail, "tax");
  const tax =
    taxValue !== "" ? toNumber(taxValue, 0) : lines.reduce((sum, line) => sum + getLineTax(line), 0);
  const officialTotal =
    readValue(detail, "finalTotal") ||
    readValue(detail, "netTotal") ||
    readValue(detail, "total") ||
    "";
  const grandTotal =
    officialTotal !== "" ? toNumber(officialTotal, 0) : lineTotal - discount + tax;

  if (module.title === "Invoices") {
    return [
      ["Line Total", lineTotal, "number"],
      ["Tax", tax, "number"],
      [`Invoice Total (${currencyCode})`, grandTotal, "number"],
      ["Paid", readValue(detail, "paymentAmt"), "number"],
      ["Outstanding", readValue(detail, "outstanding"), "number"],
    ];
  }

  if (module.title === "AR Payments") {
    return [
      ["Payment", readValue(detail, "paymentAmt"), "number"],
      ["Local Payment", readValue(detail, "localPaymentAmt"), "number"],
      ["Knock-off", readValue(detail, "knockOffAmt"), "number"],
      ["Refund", readValue(detail, "refundAmount"), "number"],
      ["Unapplied", readValue(detail, "unappliedAmount"), "number"],
    ];
  }

  if (module.title === "AR Deposits") {
    return [
      ["Deposit", readValue(detail, "paymentAmt"), "number"],
      ["Transferred", readValue(detail, "transferredAmt"), "number"],
      ["Outstanding", readValue(detail, "outstanding"), "number"],
      ["Payment Lines", (detail.paymentLines || []).length, "number"],
      ["Applied Payments", (detail.lines || []).length, "number"],
    ];
  }

  if (module.title === "AP Deposits") {
    return [
      ["Deposit", readValue(detail, "paymentAmt"), "number"],
      ["Transferred", readValue(detail, "transferredAmt"), "number"],
      ["Outstanding", readValue(detail, "outstanding"), "number"],
      ["Payment Lines", (detail.paymentLines || []).length, "number"],
      ["Applied Payments", (detail.lines || []).length, "number"],
    ];
  }

  if (module.title === "AP Invoices") {
    return [
      [`AP Total (${currencyCode})`, readValue(detail, "netTotal"), "number"],
      ["Paid", readValue(detail, "paymentAmt"), "number"],
      ["Outstanding", readValue(detail, "outstanding"), "number"],
      ["Tax", readValue(detail, "tax"), "number"],
    ];
  }

  if (module.title === "AP Payments") {
    return [
      ["Payment", readValue(detail, "paymentAmt"), "number"],
      ["Local Payment", readValue(detail, "localPaymentAmt"), "number"],
      ["Knock-off", readValue(detail, "knockOffAmt"), "number"],
      ["Refund", readValue(detail, "refundAmount"), "number"],
      ["Unapplied", readValue(detail, "unappliedAmount"), "number"],
    ];
  }

  if (module.title === "Creditors") {
    return [
      ["AP Invoices", readValue(detail, "invoiceCount"), "number"],
      ["Outstanding", readValue(detail, "outstanding"), "number"],
      ["Credit Limit", readValue(detail, "creditLimit"), "number"],
    ];
  }

  if (module.title === "Cash Book") {
    return [
      ["Payment", readValue(detail, "totalPayment"), "number"],
      ["Local Total", readValue(detail, "localTotal"), "number"],
      ["Bank Amount", readValue(detail, "bankAmount"), "number"],
      ["Tax", readValue(detail, "tax"), "number"],
    ];
  }

  if (module.title === "Bank Transactions") {
    return [
      ["Bank Amount", readValue(detail, "bankAmount"), "number"],
      ["Cash Book", readValue(detail, "cashBookDocNo") || readValue(detail, "docNo")],
      ["Recon", readValue(detail, "bankReconStatusLabel")],
      ["Statement Date", readValue(detail, "bankStatementDate")],
    ];
  }

  return [
    ["Line Total", lineTotal, "number"],
    ["Discount", discount, "number"],
    ["Tax", tax, "number"],
    [`Grand Total (${currencyCode})`, grandTotal, "number"],
  ];
}

export function getFormSummary(module, data) {
  if (module.rowKey === "projectCode") {
    const collected = toNumber(data?.collectedTotal, 0);
    const cost = toNumber(data?.actualCost, 0);
    return [
      ["Quoted", toNumber(data?.quotedTotal, 0), "number"],
      ["Collected", collected, "number"],
      ["Outstanding", toNumber(data?.outstandingAmount, 0), "number"],
      ["Actual Cost", cost, "number"],
      ["Margin", collected - cost, "number"],
    ];
  }

  if (module.rowKey === "itemCode") {
    const price = toNumber(data?.price, 0);
    const cost = toNumber(data?.cost, 0);
    return [
      ["Primary Price", price, "number"],
      ["Cost", cost, "number"],
      ["Margin", price - cost, "number"],
      ["UOM Rate", toNumber(data?.uomRate, 1), "number"],
    ];
  }

  // Master-data forms (employees, debtors, timesheet rows ...) have no lines
  // and no document totals. Returning nothing keeps a row of zeroed
  // Line Total / Discount / Tax / Grand Total off a form that has no money.
  if (!module.lineFields?.length) return [];

  const lines = data?.lines || [];
  const currencyCode = getDocumentCurrency(data);
  const lineTotal = lines.reduce((sum, line) => sum + getFormLineGross(module, line), 0);
  const discount = lines.reduce((sum, line) => sum + getFormLineDiscount(module, line), 0);
  const tax = lines.reduce((sum, line) => sum + getFormLineTax(line), 0);
  const grandTotal = lineTotal - discount + tax;

  return [
    ["Line Total", lineTotal, "number"],
    ["Discount", discount, "number"],
    ["Tax", tax, "number"],
    [`Grand Total (${currencyCode})`, grandTotal, "number"],
  ];
}

import { PROJECT_SERVICE_CATEGORIES } from "../constants.js";
import {
  appendDocumentValue,
  cleanFormPayload,
  getDocumentList,
  removeDocumentValue,
} from "./documents.js";
import { readValue, roundMoney, toNumber } from "./format.js";
import { getDocumentCurrency } from "./totals.js";
import { MODULES } from "../modules.js";

export function getProjectFormFromDetail(detail) {
  return {
    ...MODULES.projects.payload(),
    projectCode: readValue(detail, "projectCode"),
    title: readValue(detail, "title"),
    status: readValue(detail, "status") || "Lead",
    debtorCode: readValue(detail, "debtorCode"),
    debtorName: readValue(detail, "debtorName"),
    serviceCategory: readValue(detail, "serviceCategory") || PROJECT_SERVICE_CATEGORIES[0],
    contactPerson: readValue(detail, "contactPerson"),
    phone: readValue(detail, "phone"),
    siteAddress: readValue(detail, "siteAddress"),
    quotationDocNo: getDocumentList(
      readValue(detail, "quotationDocNos") || readValue(detail, "quotationDocNo")
    ).join(", "),
    invoiceDocNo: getDocumentList(
      readValue(detail, "invoiceDocNos") || readValue(detail, "invoiceDocNo")
    ).join(", "),
    purchaseOrderDocNos: getDocumentList(readValue(detail, "purchaseOrderDocNos")).join(", "),
    arPaymentDocNos: getDocumentList(readValue(detail, "arPaymentDocNos")).join(", "),
    apInvoiceDocNos: getDocumentList(readValue(detail, "apInvoiceDocNos")).join(", "),
    expectedInstallDate: readValue(detail, "expectedInstallDate"),
    completionDate: readValue(detail, "completionDate"),
    quotedTotal: readValue(detail, "quotedTotal"),
    collectedTotal: readValue(detail, "collectedTotal"),
    outstandingAmount: readValue(detail, "outstandingAmount"),
    estimatedCost: readValue(detail, "estimatedCost"),
    actualCost: readValue(detail, "actualCost"),
    notes: readValue(detail, "notes"),
    lines: [],
    __mode: "edit",
    __editKey: readValue(detail, "projectCode"),
  };
}

export function getProjectFormFromDocument(moduleKey, detail) {
  const docNo = readValue(detail, "docNo");
  const debtorName = readValue(detail, "debtorName") || readValue(detail, "creditorName");
  const debtorCode = readValue(detail, "debtorCode") || readValue(detail, "creditorCode");
  const description = readValue(detail, "description");
  const titleParts = [debtorName, description || docNo].filter(Boolean);
  const draft = {
    ...MODULES.projects.payload(),
    title: titleParts.join(" - "),
    debtorCode,
    debtorName,
    notes: docNo ? `Created from ${MODULES[moduleKey]?.singular || moduleKey} ${docNo}` : "",
    lines: [],
    __mode: "create",
    __sourceModule: moduleKey,
    __sourceKey: docNo,
  };

  if (moduleKey === "quotations") {
    draft.status = "Quoted";
    draft.quotationDocNo = docNo;
    draft.quotedTotal = readValue(detail, "finalTotal") || readValue(detail, "total");
  }
  if (moduleKey === "invoices") {
    draft.status = "Confirmed";
    draft.invoiceDocNo = docNo;
    draft.quotedTotal =
      readValue(detail, "total") || readValue(detail, "netTotal") || readValue(detail, "finalTotal");
    draft.collectedTotal = readValue(detail, "paymentAmt");
    draft.outstandingAmount = readValue(detail, "outstanding");
  }
  if (moduleKey === "ar-payments") {
    draft.status = "In Progress";
    draft.arPaymentDocNos = docNo;
    draft.collectedTotal = readValue(detail, "paymentAmt");
  }
  if (moduleKey === "purchase-orders") {
    draft.status = "In Progress";
    draft.purchaseOrderDocNos = docNo;
    draft.estimatedCost = readValue(detail, "finalTotal") || readValue(detail, "total");
  }
  if (moduleKey === "ap-invoices") {
    draft.status = "In Progress";
    draft.apInvoiceDocNos = docNo;
    draft.estimatedCost = readValue(detail, "netTotal") || readValue(detail, "total");
    draft.actualCost = readValue(detail, "netTotal") || readValue(detail, "total");
  }

  return draft;
}

export function getProjectFormFromDebtorDraft(draft) {
  const next = getProjectFormFromDraft(draft);
  next.__sourceModule = "debtors";
  next.__sourceKey = readValue(draft, "debtorCode");
  return next;
}

export function getProjectFormFromDraft(draft) {
  return {
    ...MODULES.projects.payload(),
    ...cleanFormPayload(draft),
    serviceCategory: readValue(draft, "serviceCategory") || PROJECT_SERVICE_CATEGORIES[0],
    status: readValue(draft, "status") || "Lead",
    lines: [],
    __mode: "create",
    __sourceModule: readValue(draft, "__sourceModule") || "projects",
    __sourceKey:
      readValue(draft, "__sourceKey") ||
      readValue(draft, "docNo") ||
      readValue(draft, "debtorCode"),
  };
}

export function mergeProjectDraft(current, draft) {
  const base = getProjectFormFromDebtorDraft(draft);
  const next = { ...(current || {}) };
  Object.entries(base).forEach(([key, value]) => {
    if (key.startsWith("__")) {
      next[key] = value || next[key];
      return;
    }
    if (key === "lines") {
      next.lines = next.lines || [];
      return;
    }
    if ((next[key] === "" || next[key] === null || next[key] === undefined) && value !== "") {
      next[key] = value;
    }
  });
  next.debtorCode = readValue(draft, "debtorCode") || next.debtorCode;
  next.debtorName = readValue(draft, "debtorName") || next.debtorName;
  return next;
}

export function getProjectDocumentPatch(moduleKey, project, docNo) {
  const value = String(docNo || "").trim();
  if (!value) return null;

  if (moduleKey === "quotations") {
    return { quotationDocNo: value };
  }
  if (moduleKey === "invoices") {
    return { invoiceDocNo: value };
  }
  if (moduleKey === "ar-payments") {
    return {
      arPaymentDocNos: appendDocumentValue(readValue(project, "arPaymentDocNos"), value),
    };
  }
  if (moduleKey === "purchase-orders") {
    return {
      purchaseOrderDocNos: appendDocumentValue(readValue(project, "purchaseOrderDocNos"), value),
    };
  }
  if (moduleKey === "ap-invoices") {
    return {
      apInvoiceDocNos: appendDocumentValue(readValue(project, "apInvoiceDocNos"), value),
    };
  }

  return null;
}

export function getProjectDocumentUnlinkPatch(moduleKey, project, docNo) {
  const value = String(docNo || "").trim();
  if (!value) return null;

  if (moduleKey === "quotations") {
    return { quotationDocNo: "" };
  }
  if (moduleKey === "invoices") {
    return { invoiceDocNo: "" };
  }
  if (moduleKey === "ar-payments") {
    return {
      arPaymentDocNos: removeDocumentValue(readValue(project, "arPaymentDocNos"), value),
    };
  }
  if (moduleKey === "purchase-orders") {
    return {
      purchaseOrderDocNos: removeDocumentValue(readValue(project, "purchaseOrderDocNos"), value),
    };
  }
  if (moduleKey === "ap-invoices") {
    return {
      apInvoiceDocNos: removeDocumentValue(readValue(project, "apInvoiceDocNos"), value),
    };
  }

  return null;
}

export function getProjectPrimaryDocumentField(moduleKey) {
  if (moduleKey === "quotations") return "quotationDocNo";
  if (moduleKey === "invoices") return "invoiceDocNo";
  return "";
}

export function getRecommendedProjectCode(candidate) {
  return readValue(candidate?.recommendedProject, "projectCode");
}

export function getRecommendedProjectScore(candidate) {
  return toNumber(readValue(candidate?.recommendedProject, "matchScore"), 0);
}

export function getLinkedDocumentAmount(document, documentDetail) {
  if (document.moduleKey === "ar-payments") {
    return readValue(documentDetail, "paymentAmt");
  }
  if (document.moduleKey === "invoices") {
    return (
      readValue(documentDetail, "netTotal") ||
      readValue(documentDetail, "total") ||
      readValue(documentDetail, "finalTotal")
    );
  }
  if (document.moduleKey === "ap-invoices") {
    return readValue(documentDetail, "netTotal") || readValue(documentDetail, "total");
  }
  return readValue(documentDetail, "finalTotal") || readValue(documentDetail, "total");
}

export function getProjectFinancialSummary(documents, documentDetails) {
  const summary = {
    quoted: 0,
    invoiced: 0,
    invoicePaid: 0,
    paymentPaid: 0,
    paid: 0,
    outstanding: 0,
    purchaseCost: 0,
    grossMargin: 0,
    sourceCount: 0,
  };

  documents.forEach((document) => {
    const documentDetail = documentDetails[document.key] || {};
    if (documentDetail.__error) return;

    const amount = toNumber(getLinkedDocumentAmount(document, documentDetail), 0);
    if (document.moduleKey === "quotations") {
      summary.quoted += amount;
      summary.sourceCount += 1;
    }
    if (document.moduleKey === "invoices") {
      summary.invoiced += amount;
      summary.invoicePaid += toNumber(readValue(documentDetail, "paymentAmt"), 0);
      summary.outstanding += toNumber(readValue(documentDetail, "outstanding"), 0);
      summary.sourceCount += 1;
    }
    if (document.moduleKey === "ar-payments") {
      summary.paymentPaid += amount;
      summary.sourceCount += 1;
    }
    if (document.moduleKey === "purchase-orders" || document.moduleKey === "ap-invoices") {
      summary.purchaseCost += amount;
      summary.sourceCount += 1;
    }
  });

  summary.paid = summary.paymentPaid > 0 ? summary.paymentPaid : summary.invoicePaid;
  summary.grossMargin = summary.paid - summary.purchaseCost;
  return summary;
}

export function getProjectFinancialPatch(summary) {
  const quotedTotal = summary.quoted > 0 ? summary.quoted : summary.invoiced;
  return {
    quotedTotal: roundMoney(quotedTotal),
    collectedTotal: roundMoney(summary.paid),
    outstandingAmount: roundMoney(summary.outstanding),
    estimatedCost: roundMoney(summary.purchaseCost),
    actualCost: roundMoney(summary.purchaseCost),
  };
}

export function getProjectCostRows(documents, documentDetails) {
  return documents
    .filter((document) => document.moduleKey === "ap-invoices")
    .map((document) => {
      const detail = documentDetails[document.key] || {};
      const amount = toNumber(getLinkedDocumentAmount(document, detail), 0);
      const paid = toNumber(readValue(detail, "paymentAmt"), 0);
      const outstanding = toNumber(readValue(detail, "outstanding"), 0);

      return {
        ...document,
        detail,
        amount,
        paid,
        outstanding,
        supplier: readValue(detail, "creditorName") || readValue(detail, "creditorCode"),
        currencyCode: getDocumentCurrency(detail),
        supplierInvoiceNo: readValue(detail, "supplierInvoiceNo"),
        paymentCount: Array.isArray(detail.paymentLines) ? detail.paymentLines.length : 0,
      };
    });
}

export function getProjectCostSummary(costRows) {
  const supplierKeys = new Set();
  const summary = {
    supplierCount: 0,
    invoiceCount: costRows.length,
    cost: 0,
    paid: 0,
    outstanding: 0,
  };

  costRows.forEach((row) => {
    const supplierKey = String(row.supplier || "").trim().toLowerCase();
    if (supplierKey) supplierKeys.add(supplierKey);
    summary.cost += row.amount;
    summary.paid += row.paid;
    summary.outstanding += row.outstanding;
  });
  summary.supplierCount = supplierKeys.size;
  return summary;
}

export function getProjectPhotoUrl(photo, token, size = "thumbnail") {
  const photoId = readValue(photo, "id");
  if (!photoId) return "";

  const params = new URLSearchParams();
  if (size) params.set("size", size);
  if (token) params.set("token", token);
  const queryString = params.toString();
  const path = `/api/project-photos/${encodeURIComponent(photoId)}/file`;
  return queryString ? `${path}?${queryString}` : path;
}

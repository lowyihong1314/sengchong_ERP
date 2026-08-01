import { readValue } from "./format.js";

export function getDocumentCandidateKey(candidate) {
  return `${readValue(candidate, "module")}:${readValue(candidate, "docNo")}`;
}

export function cleanFormPayload(data) {
  const payload = {};
  Object.entries(data || {}).forEach(([key, value]) => {
    if (!key.startsWith("__")) {
      payload[key] = value;
    }
  });
  return payload;
}

export function hasDebtorField(module) {
  return (module.formFields || []).some((field) => field.name === "debtorCode");
}

export function hasItemLineField(module) {
  return (module.lineFields || []).some((field) => field.name === "itemCode");
}

export function findItem(items, code) {
  const target = String(code || "").trim().toLowerCase();
  if (!target) return null;

  return (
    items.find((item) => String(readValue(item, "itemCode")).trim().toLowerCase() === target) ||
    null
  );
}

export function getItemOptions(items, currentCodes = []) {
  const options = items.map((item) => {
    const itemCode = readValue(item, "itemCode");
    const description = readValue(item, "description");

    return {
      value: itemCode,
      label: description ? `${itemCode} - ${description}` : itemCode,
    };
  });
  const seen = new Set(options.map((option) => String(option.value)));

  currentCodes.forEach((code) => {
    const current = String(code || "");
    if (current && !seen.has(current)) {
      options.unshift({ value: current, label: current });
      seen.add(current);
    }
  });

  return options;
}

export function getLineTemplate(module) {
  const line = {};
  (module.lineFields || []).forEach((field) => {
    line[field.name] = "";
  });

  if (hasItemLineField(module)) {
    line.qty = 1;
    line.uom = "";
    line.unitPrice = "";
  }

  return line;
}

export function getItemUom(module, item) {
  if (module.title === "Purchase Orders") {
    return readValue(item, "purchaseUom") || readValue(item, "baseUom") || readValue(item, "salesUom");
  }

  return readValue(item, "salesUom") || readValue(item, "baseUom") || readValue(item, "purchaseUom");
}

export function getItemUnitPrice(module, item) {
  if (module.title === "Purchase Orders") {
    return readValue(item, "cost") || readValue(item, "price");
  }

  return readValue(item, "price");
}

export function applyItemToLine(module, line, itemCode, items) {
  const item = findItem(items, itemCode);
  const nextLine = { ...line, itemCode };
  if (!item) return nextLine;

  return {
    ...nextLine,
    description: readValue(item, "description") || nextLine.description || "",
    uom: getItemUom(module, item) || nextLine.uom || "",
    unitPrice: getItemUnitPrice(module, item) || nextLine.unitPrice || "",
  };
}

export function findDebtor(debtors, code) {
  const target = String(code || "").trim().toLowerCase();
  if (!target) return null;

  return (
    debtors.find(
      (debtor) => String(readValue(debtor, "debtorCode")).trim().toLowerCase() === target
    ) || null
  );
}

export function getDebtorOptions(debtors, currentCode) {
  const options = debtors.map((debtor) => {
    const debtorCode = readValue(debtor, "debtorCode");
    const debtorName = readValue(debtor, "debtorName");

    return {
      value: debtorCode,
      label: debtorName ? `${debtorCode} - ${debtorName}` : debtorCode,
    };
  });

  const current = String(currentCode || "");
  if (current && !options.some((option) => String(option.value) === current)) {
    options.unshift({
      value: current,
      label: current,
    });
  }

  return options;
}

export function getProjectOptions(projects, currentCode) {
  const options = projects.map((project) => {
    const projectCode = readValue(project, "projectCode");
    const title = readValue(project, "title");
    const debtorName = readValue(project, "debtorName");
    const labelParts = [projectCode, title || debtorName].filter(Boolean);

    return {
      value: projectCode,
      label: labelParts.join(" - "),
    };
  });

  const current = String(currentCode || "");
  if (current && !options.some((option) => String(option.value) === current)) {
    options.unshift({
      value: current,
      label: current,
    });
  }

  return options;
}

export function getDebtorInfo(source, debtors) {
  const code = readValue(source, "debtorCode");
  if (!code) return null;

  const lookup = findDebtor(debtors, code) || {};
  return {
    code,
    name:
      readValue(source, "debtorName") ||
      readValue(lookup, "debtorName") ||
      readValue(lookup, "companyName"),
    phone: readValue(lookup, "phone"),
    area: readValue(lookup, "area"),
    agent: readValue(lookup, "agent"),
    currencyCode: readValue(source, "currencyCode") || readValue(lookup, "currencyCode"),
    displayTerm:
      readValue(source, "paymentTerm") ||
      readValue(source, "displayTerm") ||
      readValue(lookup, "displayTerm"),
  };
}

export function openDocumentTableRow(row, onOpenDocument) {
  const moduleKey = readValue(row, "moduleKey");
  const key = readValue(row, "docNo") || readValue(row, "docKey");
  if (moduleKey && key && onOpenDocument) {
    onOpenDocument(moduleKey, key);
  }
}

export function getCashBookLinkRows(moduleKey, detail) {
  if (!["ar-payments", "ar-deposits", "ap-payments", "ap-deposits"].includes(moduleKey) || !detail) {
    return [];
  }

  const docNo = readValue(detail, "cashBookDocNo");
  const docKey = readValue(detail, "cashBookKey") || readValue(detail, "cbKey");
  if (!docNo && !docKey) return [];

  return [
    {
      moduleKey: "cash-book",
      documentType: "Cash Book",
      docNo: docNo || docKey,
      docKey,
      docDate: readValue(detail, "docDate"),
      accountCode: readValue(detail, "debtorCode") || readValue(detail, "creditorCode"),
      accountName: readValue(detail, "debtorName") || readValue(detail, "creditorName"),
      description: readValue(detail, "description"),
      amount: readValue(detail, "paymentAmt"),
      localAmount: readValue(detail, "localPaymentAmt"),
      status: readValue(detail, "status"),
    },
  ];
}

export function getDetailLineDocumentTarget(moduleKey, line) {
  if (moduleKey === "ar-payments") {
    const key = readValue(line, "invoiceDocNo") || readValue(line, "invoiceDocKey");
    return key ? { moduleKey: "invoices", key } : null;
  }
  if (moduleKey === "ar-deposits") {
    const key = readValue(line, "paymentDocNo") || readValue(line, "paymentDocKey");
    return key ? { moduleKey: "ar-payments", key } : null;
  }
  if (moduleKey === "ap-payments") {
    const key = readValue(line, "invoiceDocNo") || readValue(line, "invoiceDocKey");
    return key ? { moduleKey: "ap-invoices", key } : null;
  }
  if (moduleKey === "ap-deposits") {
    const key = readValue(line, "paymentDocNo") || readValue(line, "paymentDocKey");
    return key ? { moduleKey: "ap-payments", key } : null;
  }
  if (moduleKey === "bank-transactions") {
    const key = readValue(line, "docNo") || readValue(line, "docKey");
    return key ? { moduleKey: "cash-book", key } : null;
  }
  return null;
}

export function getDocumentList(value) {
  if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
  return String(value || "")
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function appendDocumentValue(currentValue, nextValue) {
  const value = String(nextValue || "").trim();
  if (!value) return getDocumentList(currentValue).join(", ");

  const documents = getDocumentList(currentValue);
  const normalized = value.toLowerCase();
  if (!documents.some((item) => item.toLowerCase() === normalized)) {
    documents.push(value);
  }
  return documents.join(", ");
}

export function removeDocumentValue(currentValue, removeValue) {
  const target = String(removeValue || "").trim().toLowerCase();
  return getDocumentList(currentValue)
    .filter((item) => item.toLowerCase() !== target)
    .join(", ");
}

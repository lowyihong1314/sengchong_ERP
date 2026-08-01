export function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export function readValue(row, key) {
  if (!row) return "";
  if (row[key] !== undefined) return row[key];

  const pascal = key.charAt(0).toUpperCase() + key.slice(1);
  if (row[pascal] !== undefined) return row[pascal];

  const upper = key.toUpperCase();
  if (row[upper] !== undefined) return row[upper];

  return "";
}

export function formatValue(value, kind, currencyCode = "") {
  if (value === null || value === undefined) return "";
  if ((kind === "number" || kind === "money") && value !== "") {
    const number = Number(value);
    if (!Number.isNaN(number)) {
      const formattedNumber = number.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
      if (kind === "money" && currencyCode) {
        return `${currencyCode} ${formattedNumber}`;
      }
      return formattedNumber;
    }
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

export function toNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function roundMoney(value) {
  return Math.round(toNumber(value, 0) * 100) / 100;
}

export function getDownloadFilename(response, fallback) {
  const disposition = response.headers.get("content-disposition") || "";
  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch) {
    return decodeURIComponent(encodedMatch[1].replace(/"/g, ""));
  }

  const match = disposition.match(/filename="?([^";]+)"?/i);
  if (match) {
    return match[1];
  }

  return fallback;
}

export function isAbortError(error) {
  return error?.name === "AbortError";
}

export function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export function getRowKey(row, module) {
  return readValue(row, module.rowKey);
}

export function getDetailLines(module, detail) {
  if (!detail) return [];
  if (module.rowKey === "itemCode") return detail.uoms || [];
  return detail.lines || [];
}

export function isFlagOn(value) {
  const text = String(value ?? "").trim().toLowerCase();
  return value === true || ["t", "true", "yes", "y", "1"].includes(text);
}

export function getRelatedRowKey(row, index) {
  return (
    readValue(row, "projectCode") ||
    readValue(row, "moduleKey") + readValue(row, "docNo") ||
    readValue(row, "id") ||
    readValue(row, "autoKey") ||
    readValue(row, "bankTransKey") ||
    readValue(row, "docKey") ||
    readValue(row, "dtlKey") ||
    readValue(row, "knockOffKey") ||
    readValue(row, "paymentDocKey") ||
    readValue(row, "paymentDocNo") ||
    readValue(row, "invoiceDocKey") ||
    readValue(row, "invoiceDocNo") ||
    index
  );
}

export function hasValue(value) {
  return value !== "" && value !== null && value !== undefined;
}

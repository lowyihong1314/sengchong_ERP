import { readValue, toNumber } from "./format.js";

export function getBankReconState(row) {
  const raw = readValue(row, "bankReconStatus");
  const label = String(readValue(row, "bankReconStatusLabel") || "").trim().toLowerCase();
  return Number(raw) === 1 || label === "reconciled" ? "reconciled" : "open";
}

export function getBankAccountKey(row) {
  return String(readValue(row, "bankAccount") || "").trim();
}

export function getBankTransactionKey(row) {
  return String(readValue(row, "bankTransKey") || "").trim();
}

export function getBankAccountChoices(rows) {
  const byAccount = new Map();
  rows.forEach((row) => {
    const account = getBankAccountKey(row);
    if (!account || byAccount.has(account)) return;
    const accountName = readValue(row, "bankAccountName");
    byAccount.set(account, {
      value: account,
      label: accountName ? `${account} - ${accountName}` : account,
    });
  });
  return Array.from(byAccount.values()).sort((left, right) =>
    left.value.localeCompare(right.value)
  );
}

export function getBankTransactionSummary(rows) {
  const summary = {
    count: 0,
    total: 0,
    openCount: 0,
    open: 0,
    reconciledCount: 0,
    reconciled: 0,
    accounts: [],
  };
  const accounts = new Map();

  rows.forEach((row) => {
    const amount = toNumber(readValue(row, "bankAmount"), 0);
    const reconState = getBankReconState(row);
    const account = getBankAccountKey(row) || "-";
    const accountName = readValue(row, "bankAccountName");
    const accountSummary =
      accounts.get(account) ||
      {
        account,
        accountName,
        count: 0,
        total: 0,
        openCount: 0,
        open: 0,
        reconciledCount: 0,
        reconciled: 0,
      };

    summary.count += 1;
    summary.total += amount;
    accountSummary.count += 1;
    accountSummary.total += amount;

    if (reconState === "reconciled") {
      summary.reconciledCount += 1;
      summary.reconciled += amount;
      accountSummary.reconciledCount += 1;
      accountSummary.reconciled += amount;
    } else {
      summary.openCount += 1;
      summary.open += amount;
      accountSummary.openCount += 1;
      accountSummary.open += amount;
    }

    accounts.set(account, accountSummary);
  });

  summary.accounts = Array.from(accounts.values()).sort((left, right) =>
    left.account.localeCompare(right.account)
  );
  return summary;
}

export function filterBankTransactions(rows, filters) {
  const account = String(filters?.account || "").trim();
  const recon = String(filters?.recon || "all");
  return rows.filter((row) => {
    if (account && getBankAccountKey(row) !== account) return false;
    if (recon !== "all" && getBankReconState(row) !== recon) return false;
    return true;
  });
}

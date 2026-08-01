export function getPdfExportLabel(moduleKey, exporting) {
  if (exporting) return "Exporting...";
  if (moduleKey === "ar-payments") return "Print Official Receipt";
  if (moduleKey === "debtors") return "Print Statement of Account";
  return "Export PDF";
}

export function getPdfExportStatus(moduleKey, done = false) {
  if (moduleKey === "ar-payments") {
    return done ? "Official receipt exported" : "Preparing official receipt...";
  }
  if (moduleKey === "debtors") {
    return done ? "Statement of account exported" : "Preparing statement of account...";
  }
  return done ? "PDF exported" : "Preparing PDF...";
}

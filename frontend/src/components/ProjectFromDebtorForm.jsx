import { Plus } from "lucide-react";

import { getDebtorOptions } from "../lib/documents.js";

/** Small picker that seeds a new Project from an existing AutoCount debtor. */
export function ProjectFromDebtorForm({
  debtorCode,
  debtors,
  debtorsLoaded,
  loading,
  onCancel,
  onDebtorCodeChange,
  onSubmit,
}) {
  return (
    <form className="project-from-debtor-form" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Debtor</span>
        <select
          required
          value={debtorCode}
          onChange={(event) => onDebtorCodeChange(event.target.value)}
        >
          <option value="">{debtorsLoaded ? "Select debtor" : "Loading debtors..."}</option>
          {getDebtorOptions(debtors, debtorCode).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <div className="project-from-debtor-actions">
        <button className="ghost-button" disabled={loading} type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="primary-button" disabled={loading || !debtorCode} type="submit">
          <Plus aria-hidden="true" size={16} />
          {loading ? "Preparing..." : "Create Project"}
        </button>
      </div>
    </form>
  );
}

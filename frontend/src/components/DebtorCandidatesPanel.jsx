import { Plus, RefreshCw } from "lucide-react";

import { readValue } from "../lib/format.js";

/**
 * Lists AutoCount debtors that do not have a Project yet, so a job can be
 * opened straight from the debtor master instead of being typed twice.
 */
export function DebtorCandidatesPanel({ candidates, loading, onClose, onCreate, onRefresh }) {
  return (
    <section className="project-candidates-panel">
      <div className="project-candidates-header">
        <div>
          <h3>Debtor Candidates</h3>
          <span>
            {loading
              ? "Scanning AutoCount debtor master"
              : `${candidates.length} debtor${
                  candidates.length === 1 ? "" : "s"
                } without Project`}
          </span>
        </div>
        <div className="project-candidates-actions">
          <button className="ghost-button" disabled={loading} type="button" onClick={onRefresh}>
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
          <button className="ghost-button" disabled={loading} type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>

      {!loading && candidates.length === 0 ? (
        <div className="project-candidates-empty">No debtor candidates found.</div>
      ) : (
        <div className="project-candidates-table">
          <table>
            <thead>
              <tr>
                <th>Debtor</th>
                <th>Phone</th>
                <th>Area</th>
                <th>Address</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => {
                const debtorCode = readValue(candidate, "debtorCode");
                const debtorName = readValue(candidate, "debtorName");
                return (
                  <tr key={debtorCode}>
                    <td>
                      <strong>{debtorName || debtorCode}</strong>
                      <span>{debtorCode}</span>
                    </td>
                    <td>{readValue(candidate, "phone") || "-"}</td>
                    <td>{readValue(candidate, "area") || "-"}</td>
                    <td>
                      <div className="project-candidate-address">
                        {readValue(candidate, "siteAddress") || "-"}
                      </div>
                    </td>
                    <td>
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => onCreate(candidate)}
                      >
                        <Plus aria-hidden="true" size={16} />
                        Create
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

import { FileText, Plus, RefreshCw } from "lucide-react";

import { AUTO_LINK_RECOMMENDED_MIN_SCORE } from "../constants.js";
import { getDocumentCandidateKey, getProjectOptions } from "../lib/documents.js";
import { formatValue, readValue } from "../lib/format.js";

/**
 * Lists AutoCount quotations/invoices that are not linked to a Project yet.
 *
 * Each row shows the best-scoring recommended Project so a document can be
 * attached with one click, or bulk-attached through the auto-link button.
 */
export function DocumentCandidatesPanel({
  autoLinking,
  candidates,
  linkingKey,
  links,
  loading,
  projectChoices,
  projectChoicesLoaded,
  projectChoicesLoading,
  onAutoLink,
  onClose,
  onCreate,
  onLink,
  onLoadProjects,
  onRefresh,
  onSelectProject,
}) {
  return (
    <section className="project-candidates-panel">
      <div className="project-candidates-header">
        <div>
          <h3>Document Candidates</h3>
          <span>
            {loading
              ? "Scanning AutoCount quotations and invoices"
              : `${candidates.length} document${
                  candidates.length === 1 ? "" : "s"
                } without Project link`}
          </span>
        </div>
        <div className="project-candidates-actions">
          <button
            className="ghost-button"
            disabled={loading || autoLinking || !candidates.length}
            type="button"
            onClick={onAutoLink}
          >
            <FileText aria-hidden="true" size={16} />
            {autoLinking ? "Auto Linking..." : `Auto Link ${AUTO_LINK_RECOMMENDED_MIN_SCORE}+`}
          </button>
          <button
            className="ghost-button"
            disabled={loading || autoLinking}
            type="button"
            onClick={onRefresh}
          >
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
          <button
            className="ghost-button"
            disabled={loading || autoLinking}
            type="button"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>

      {!loading && candidates.length === 0 ? (
        <div className="project-candidates-empty">No document candidates found.</div>
      ) : (
        <div className="project-candidates-table">
          <table>
            <thead>
              <tr>
                <th>Document</th>
                <th>Debtor</th>
                <th>Description</th>
                <th>Amount</th>
                <th>Outstanding</th>
                <th>Recommended</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => {
                const candidateKey = getDocumentCandidateKey(candidate);
                const docNo = readValue(candidate, "docNo");
                const moduleLabel = readValue(candidate, "moduleLabel");
                const debtorCode = readValue(candidate, "debtorCode");
                const debtorName = readValue(candidate, "debtorName");
                const currencyCode = readValue(candidate, "currencyCode");
                const existingProjects = candidate.existingProjects || [];
                const recommendedProject = candidate.recommendedProject || null;
                const recommendedCode = readValue(recommendedProject, "projectCode");
                const recommendedScore = readValue(recommendedProject, "matchScore");
                const recommendedReasons =
                  candidate.matchReasons || recommendedProject?.matchReasons || [];
                const selectedProject = links[candidateKey] || "";
                const projectOptions = getProjectOptions(projectChoices, selectedProject);
                const linking = linkingKey === candidateKey || autoLinking;
                return (
                  <tr key={candidateKey}>
                    <td>
                      <strong>{docNo}</strong>
                      <span>
                        {moduleLabel}
                        {readValue(candidate, "docDate")
                          ? ` - ${readValue(candidate, "docDate")}`
                          : ""}
                      </span>
                    </td>
                    <td>
                      <strong>{debtorName || debtorCode || "-"}</strong>
                      <span>{debtorCode || "-"}</span>
                    </td>
                    <td>
                      <div className="project-candidate-address">
                        {readValue(candidate, "description") || "-"}
                      </div>
                    </td>
                    <td className="number">
                      {formatValue(readValue(candidate, "amount"), "money", currencyCode)}
                    </td>
                    <td className="number">
                      {formatValue(readValue(candidate, "outstanding"), "money", currencyCode)}
                    </td>
                    <td>
                      {recommendedCode ? (
                        <>
                          <strong>
                            {recommendedCode}
                            {recommendedScore ? ` (${recommendedScore})` : ""}
                          </strong>
                          <span>
                            {recommendedReasons.length
                              ? recommendedReasons.join(", ")
                              : readValue(recommendedProject, "title") || "Recommended"}
                          </span>
                        </>
                      ) : existingProjects.length ? (
                        <>
                          <strong>{readValue(existingProjects[0], "projectCode")}</strong>
                          <span>
                            {existingProjects.length > 1
                              ? `${existingProjects.length} possible matches`
                              : readValue(existingProjects[0], "title") || "Possible match"}
                          </span>
                        </>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td>
                      <div className="project-candidate-actions">
                        <select
                          disabled={autoLinking}
                          value={selectedProject}
                          onFocus={() => {
                            if (!projectChoicesLoaded) onLoadProjects();
                          }}
                          onChange={(event) => onSelectProject(candidateKey, event.target.value)}
                        >
                          <option value="">
                            {projectChoicesLoading ? "Loading projects" : "Select project"}
                          </option>
                          {projectOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <button
                          className="secondary-button"
                          disabled={linking || !selectedProject}
                          type="button"
                          onClick={() => onLink(candidate)}
                        >
                          <FileText aria-hidden="true" size={16} />
                          {linking ? "Linking..." : "Link"}
                        </button>
                        <button
                          className="secondary-button"
                          disabled={linking}
                          type="button"
                          onClick={() => onCreate(candidate)}
                        >
                          <Plus aria-hidden="true" size={16} />
                          Create
                        </button>
                      </div>
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

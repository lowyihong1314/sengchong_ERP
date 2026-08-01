import React from "react";
import {
  Plus,
  Save,
} from "lucide-react";
import { DetailDataTable } from "./DetailDataTable.jsx";
import { readValue } from "../lib/format.js";

export function DocumentProjectsPanel({
  availableProjects,
  currencyCode,
  linkedProjects,
  loadingProjects,
  onCreateProject,
  onLinkProject,
  onLoadProjects,
  onOpenProject,
}) {
  const [showLinkForm, setShowLinkForm] = React.useState(false);
  const [selectedProject, setSelectedProject] = React.useState("");
  const linkedCodes = new Set(
    (linkedProjects || []).map((project) => String(readValue(project, "projectCode")))
  );
  const linkChoices = (availableProjects || []).filter((project) => {
    const projectCode = readValue(project, "projectCode");
    return projectCode && !linkedCodes.has(String(projectCode));
  });

  const openLinkForm = () => {
    setShowLinkForm(true);
    if (onLoadProjects) onLoadProjects();
  };
  const submitLink = async (event) => {
    event.preventDefault();
    if (!selectedProject || !onLinkProject) return;
    const ok = await onLinkProject(selectedProject);
    if (ok !== false) {
      setSelectedProject("");
      setShowLinkForm(false);
    }
  };

  return (
    <section className="project-link-panel">
      <div className="related-section-header">
        <h3>Linked Projects</h3>
        <span>{(linkedProjects || []).length} link(s)</span>
      </div>
      <div className="project-link-toolbar">
        <button className="secondary-button" type="button" onClick={openLinkForm}>
          <Plus aria-hidden="true" size={16} />
          Link Existing Project
        </button>
        {onCreateProject && (
          <button className="secondary-button" type="button" onClick={onCreateProject}>
            <Plus aria-hidden="true" size={16} />
            New Project
          </button>
        )}
      </div>
      {showLinkForm && (
        <form className="project-link-form" onSubmit={submitLink}>
          <label className="form-field" htmlFor="project-link-select">
            <span>Project</span>
            <select
              id="project-link-select"
              value={selectedProject}
              onChange={(event) => setSelectedProject(event.target.value)}
              required
            >
              <option value="">
                {loadingProjects ? "Loading projects" : "Select project"}
              </option>
              {linkChoices.map((project) => {
                const projectCode = readValue(project, "projectCode");
                const title = readValue(project, "title");
                return (
                  <option key={projectCode} value={projectCode}>
                    {title ? `${projectCode} - ${title}` : projectCode}
                  </option>
                );
              })}
            </select>
          </label>
          <div className="project-link-form-actions">
            <button
              className="secondary-button"
              type="button"
              onClick={() => setShowLinkForm(false)}
            >
              Cancel
            </button>
            <button
              className="primary-button"
              disabled={!selectedProject || loadingProjects}
              type="submit"
            >
              <Save aria-hidden="true" size={16} />
              Link
            </button>
          </div>
        </form>
      )}
      <DetailDataTable
        columns={[
          ["projectCode", "Project"],
          ["title", "Title"],
          ["debtorName", "Customer"],
          ["serviceCategory", "Category"],
          ["status", "Status"],
          ["outstandingAmount", "Outstanding", "money"],
        ]}
        currencyCode={currencyCode}
        emptyText="No project linked to this document"
        rows={linkedProjects || []}
        title="Projects"
        onRowClick={
          onOpenProject
            ? (project) => onOpenProject(readValue(project, "projectCode"))
            : null
        }
      />
    </section>
  );
}

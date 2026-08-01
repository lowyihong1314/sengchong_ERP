import {
  ArrowLeft,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { DebtorInfo } from "../components/DebtorInfo.jsx";
import { FieldInput, LineCellInput } from "../components/FormInputs.jsx";
import { TotalSummary } from "../components/TotalSummary.jsx";
import {
  getDebtorInfo,
  getDebtorOptions,
  getItemOptions,
  hasDebtorField,
} from "../lib/documents.js";
import { formatValue, readValue } from "../lib/format.js";
import { getDocumentCurrency, getFormLineTotal, getFormSummary } from "../lib/totals.js";

export function NewPage({
  module,
  data,
  debtors,
  items,
  mode = "create",
  onBack,
  onChange,
  onLineChange,
  onAddLine,
  onRemoveLine,
  onSave,
  status,
}) {
  const isEdit = mode === "edit";
  const summaryItems = getFormSummary(module, data);
  const showDebtor = hasDebtorField(module);
  const debtorInfo = getDebtorInfo(data, debtors);
  const debtorChoices = getDebtorOptions(debtors, data?.debtorCode);
  const itemChoices = getItemOptions(
    items,
    (data.lines || []).map((line) => line.itemCode)
  );

  return (
    <section className="content-panel detail-page">
      <div className="detail-page-header">
        <button className="secondary-button" type="button" onClick={onBack}>
          <ArrowLeft aria-hidden="true" size={16} />
          Back
        </button>
        <div>
          <h2>
            {isEdit
              ? `Edit ${readValue(data, module.rowKey) || module.singular}`
              : `${module.createLabel} ${module.singular}`}
          </h2>
          <p>{module.meta}</p>
        </div>
        <div className="page-header-actions">
          <button className="primary-button" type="button" onClick={onSave}>
            <Save aria-hidden="true" size={16} />
            {isEdit ? "Save Changes" : "Save"}
          </button>
        </div>
      </div>
      <div className={`status-bar ${status?.tone || ""}`}>{status?.text || "Ready"}</div>

      {showDebtor && <DebtorInfo debtor={debtorInfo} showEmpty />}

      <div className="line-table-title">Header</div>
      <div className="new-form-wrap">
        <div className="form-grid">
          {module.formFields.map((field) => {
            const isDebtorCode = field.name === "debtorCode";
            const inputField = isDebtorCode
              ? {
                  ...field,
                  type: "select",
                  placeholder: debtorChoices.length ? "Select debtor" : "Loading debtors",
                }
              : field;

            return (
              <FieldInput
                field={inputField}
                key={field.name}
                options={isDebtorCode ? debtorChoices : field.options}
                value={data[field.name]}
                onChange={(value) => onChange(field.name, value)}
              />
            );
          })}
        </div>
      </div>

      {module.lineFields.length > 0 && (
        <section className="form-lines page-form-lines">
          <div className="line-editor-header">
            <h3>Lines</h3>
            <button className="secondary-button" type="button" onClick={onAddLine}>
              <Plus aria-hidden="true" size={16} />
              Add Line
            </button>
          </div>

          <div className="line-table-editor">
            <table>
              <thead>
                <tr>
                  {module.lineFields.map((field) => (
                    <th key={field.name}>{field.label}</th>
                  ))}
                  <th>Total</th>
                  <th aria-label="Line actions" />
                </tr>
              </thead>
              <tbody>
                {(data.lines || []).length === 0 ? (
                  <tr className="empty-row">
                    <td colSpan={module.lineFields.length + 2}>No lines</td>
                  </tr>
                ) : (
                  (data.lines || []).map((line, lineIndex) => (
                    <tr key={lineIndex}>
                      {module.lineFields.map((field) => {
                        const isItemCode = field.name === "itemCode";
                        const inputField = isItemCode
                          ? {
                              ...field,
                              type: "select",
                              placeholder: itemChoices.length ? "Select item" : "Loading items",
                            }
                          : field;

                        return (
                          <td
                            className={`line-cell line-cell-${field.name}`}
                            key={field.name}
                          >
                            <LineCellInput
                              field={inputField}
                              options={isItemCode ? itemChoices : field.options}
                              value={line[field.name]}
                              onChange={(value) => onLineChange(lineIndex, field.name, value)}
                            />
                          </td>
                        );
                      })}
                      <td className="line-total-cell">
                        {formatValue(getFormLineTotal(module, line), "money", getDocumentCurrency(data))}
                      </td>
                      <td className="line-action-cell">
                        <button
                          className="icon-button danger-button"
                          type="button"
                          onClick={() => onRemoveLine(lineIndex)}
                          title="Remove line"
                        >
                          <Trash2 aria-hidden="true" size={16} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <TotalSummary items={summaryItems} />

      {module.lineFields.length === 0 && (
        <div className="new-page-actions">
          <button className="primary-button" type="button" onClick={onSave}>
            <Save aria-hidden="true" size={16} />
            {isEdit ? "Save Changes" : `Save ${module.singular}`}
          </button>
        </div>
      )}
    </section>
  );
}

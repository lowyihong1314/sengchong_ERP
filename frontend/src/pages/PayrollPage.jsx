import React from "react";
import { Download, Lock, Plus, RefreshCw, Trash2 } from "lucide-react";

import { formatValue } from "../lib/format.js";

/**
 * Monthly payroll: pick a period, generate from the timesheet, adjust the
 * lines, then lock.
 *
 * Locking is one-way on purpose. Once a month has been paid, a later raise or
 * a backdated timesheet must not reach into it, so the run keeps its own copy
 * of every figure and the lines stop being editable.
 */
export function PayrollPage({
  period,
  run,
  runs,
  loading,
  saving,
  status,
  onPeriodChange,
  onGenerate,
  onSelectRun,
  onItemChange,
  onItemSave,
  onLock,
  employees,
  onAddItem,
  onDelete,
  onDownloadPayslips,
  onRefresh,
  onRemoveItem,
}) {
  const items = run?.items || [];
  const locked = Boolean(run?.locked);
  const [pick, setPick] = React.useState("");

  // Nobody twice on one run: the PDF prints a page per line, so a duplicate
  // would hand the employee two contradictory payslips. The backend refuses it
  // too -- this only keeps the name out of the picker.
  const onRun = new Set(items.map((item) => item.employeeId));
  const available = (employees || []).filter((employee) => !onRun.has(employee.id));

  function submitAdd() {
    if (!pick) return;
    onAddItem(pick);
    setPick("");
  }

  /** A money cell: editable while the run is a draft, plain text once locked. */
  function money(item, field, editable) {
    if (locked || !editable) return formatValue(item[field], "money");
    return (
      <input
        className="cell-input"
        step="0.01"
        type="number"
        value={item[field] ?? ""}
        onChange={(event) => onItemChange(item.id, field, event.target.value)}
        onBlur={() => onItemSave(item.id)}
      />
    );
  }

  return (
    <section className="content-panel payroll-page">
      <div className="detail-page-header">
        <div>
          <h2>Payroll</h2>
          <p>
            {run
              ? `${run.company} ${run.period} - ${run.status}, ${run.headcount} employee(s)`
              : "Pick a month and generate from the timesheet"}
          </p>
        </div>
        <div className="topbar-actions">
          <button className="ghost-button" disabled={loading} type="button" onClick={onRefresh}>
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
          {run && !locked && (
            <button className="secondary-button" disabled={saving} type="button" onClick={onDelete}>
              <Trash2 aria-hidden="true" size={16} />
              Delete Draft
            </button>
          )}
          {run && (
            <button
              className="secondary-button"
              disabled={saving}
              type="button"
              onClick={onDownloadPayslips}
            >
              <Download aria-hidden="true" size={16} />
              Payslips PDF
            </button>
          )}
          {run && !locked && (
            <button className="primary-button" disabled={saving} type="button" onClick={onLock}>
              <Lock aria-hidden="true" size={16} />
              Lock Run
            </button>
          )}
        </div>
      </div>

      <div className="toolbar">
        <label className="form-field">
          <span>Period</span>
          <input
            type="month"
            value={period}
            onChange={(event) => onPeriodChange(event.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Existing runs</span>
          <select value={run?.id || ""} onChange={(event) => onSelectRun(event.target.value)}>
            <option value="">Select a run</option>
            {runs.map((item) => (
              <option key={item.id} value={item.id}>
                {item.company} {item.period} - {item.status} ({item.headcount})
              </option>
            ))}
          </select>
        </label>
        <div className="toolbar-actions">
          <button className="secondary-button" disabled={loading} type="button" onClick={() => onGenerate(false)}>
            Generate
          </button>
          <button className="ghost-button" disabled={loading || locked} type="button" onClick={() => onGenerate(true)}>
            Regenerate (discards edits)
          </button>
        </div>
      </div>

      {/* Where these figures came from. Shown here, for whoever is checking
          the run -- deliberately not printed on the payslip the employee gets. */}
      {run?.statutoryNote && <div className="status-bar">Source: {run.statutoryNote}</div>}
      {locked && (
        <div className="status-bar ok">
          Locked {run.lockedAt} by {run.lockedBy}. Figures are frozen; correct a locked month with
          an adjustment on a later run.
        </div>
      )}

      <div className="table-wrap">
        <table className="payroll-table">
          <thead>
            <tr>
              <th>Employee</th>
              <th className="number">Days</th>
              <th className="number">OT Hrs</th>
              <th className="number">Normal</th>
              <th className="number">OT</th>
              <th className="number">Overnight</th>
              <th className="number">Allowance</th>
              <th className="number">Adjustment</th>
              <th className="number">Gross</th>
              <th className="number">EPF</th>
              <th className="number">SOCSO</th>
              <th className="number">EIS</th>
              <th className="number">PCB</th>
              <th className="number">Other</th>
              <th className="number">Net</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={16}>
                  {loading
                    ? "Loading..."
                    : locked
                    ? "This run has no lines."
                    : "No lines. Generate pulls them from the day sheet; for a month with no attendance recorded, add people by hand below."}
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr className={item.manual ? "manual-line" : ""} key={item.id}>
                  <td>
                    <strong>{item.name}</strong>
                    <span>
                      {item.employeeCode} - {item.position || "-"}
                      {item.manual ? " - by hand" : ""}
                    </span>
                  </td>
                  {/* Days, hours and earnings are priced from the day sheet on a
                      generated line, so they are typed only on a hand-added one.
                      The backend enforces this too; the row just stops offering
                      an edit that would be rejected. */}
                  <td className="number">{money(item, "dayUnits", item.manual)}</td>
                  <td className="number">{money(item, "otHours", item.manual)}</td>
                  <td className="number">{money(item, "normalPay", item.manual)}</td>
                  <td className="number">{money(item, "otPay", item.manual)}</td>
                  <td className="number">{money(item, "overnightPay", item.manual)}</td>
                  <td className="number">{money(item, "fixedAllowance", true)}</td>
                  <td className="number">{money(item, "adjustment", true)}</td>
                  <td className="number">
                    <strong>{formatValue(item.grossPay, "money")}</strong>
                  </td>
                  {[
                    "epfEmployee",
                    "socsoEmployee",
                    "eisEmployee",
                    "pcb",
                    "otherDeduction",
                  ].map((field) => (
                    <td className="number" key={field}>
                      {money(item, field, true)}
                    </td>
                  ))}
                  <td className="number">
                    <strong>{formatValue(item.netPay, "money")}</strong>
                  </td>
                  <td className="number">
                    {!locked && (
                      <button
                        aria-label={`Remove ${item.name}`}
                        className="icon-button"
                        disabled={saving}
                        title={`Remove ${item.name} from this run`}
                        type="button"
                        onClick={() => onRemoveItem(item.id)}
                      >
                        <Trash2 aria-hidden="true" size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
          {run && items.length > 0 && (
            <tfoot>
              <tr>
                <td>Total ({run.headcount})</td>
                <td className="number">{run.totalDayUnits}</td>
                <td className="number">{run.totalOtHours}</td>
                <td colSpan={5} />
                <td className="number">{formatValue(run.totalGross, "money")}</td>
                <td colSpan={5} className="number">
                  deductions {formatValue(run.totalDeductions, "money")}
                </td>
                <td className="number">{formatValue(run.totalNet, "money")}</td>
                <td />
              </tr>
              <tr>
                <td colSpan={14}>
                  Employer cost including employer contributions
                </td>
                <td className="number">{formatValue(run.totalEmployerCost, "money")}</td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {run && !locked && (
        <div className="toolbar payroll-add-row">
          <label className="form-field">
            <span>Add employee to this run</span>
            <select
              disabled={saving || available.length === 0}
              value={pick}
              onChange={(event) => setPick(event.target.value)}
            >
              <option value="">
                {available.length === 0
                  ? "Everyone is already on this run"
                  : "Select an employee"}
              </option>
              {available.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.employeeCode} - {employee.name}
                  {employee.status && employee.status !== "Active" ? ` (${employee.status})` : ""}
                </option>
              ))}
            </select>
          </label>
          <div className="toolbar-actions">
            <button
              className="secondary-button"
              disabled={!pick || saving}
              type="button"
              onClick={submitAdd}
            >
              <Plus aria-hidden="true" size={16} />
              Add Line
            </button>
          </div>
          <p className="field-hint">
            A hand-added line starts at zero and its days, hours and earnings are
            typed here. Regenerate rebuilds from the day sheet and will discard it.
          </p>
        </div>
      )}

      <div className={`status-bar ${status.tone}`}>{status.text}</div>
    </section>
  );
}

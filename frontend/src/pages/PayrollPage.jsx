import React from "react";
import { Download, Lock, RefreshCw, Save, Trash2 } from "lucide-react";

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
  onDelete,
  onDownloadPayslips,
  onRefresh,
}) {
  const items = run?.items || [];
  const locked = Boolean(run?.locked);

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
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={15}>
                  {loading ? "Loading..." : "No lines. Pick a month and press Generate."}
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <strong>{item.name}</strong>
                    <span>
                      {item.employeeCode} - {item.position || "-"}
                    </span>
                  </td>
                  <td className="number">{item.dayUnits}</td>
                  <td className="number">{item.otHours}</td>
                  <td className="number">{formatValue(item.normalPay, "money")}</td>
                  <td className="number">{formatValue(item.otPay, "money")}</td>
                  <td className="number">{formatValue(item.overnightPay, "money")}</td>
                  {[
                    "fixedAllowance",
                    "adjustment",
                  ].map((field) => (
                    <td className="number" key={field}>
                      {locked ? (
                        formatValue(item[field], "money")
                      ) : (
                        <input
                          className="cell-input"
                          step="0.01"
                          type="number"
                          value={item[field] ?? ""}
                          onChange={(event) => onItemChange(item.id, field, event.target.value)}
                          onBlur={() => onItemSave(item.id)}
                        />
                      )}
                    </td>
                  ))}
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
                      {locked ? (
                        formatValue(item[field], "money")
                      ) : (
                        <input
                          className="cell-input"
                          step="0.01"
                          type="number"
                          value={item[field] ?? ""}
                          onChange={(event) => onItemChange(item.id, field, event.target.value)}
                          onBlur={() => onItemSave(item.id)}
                        />
                      )}
                    </td>
                  ))}
                  <td className="number">
                    <strong>{formatValue(item.netPay, "money")}</strong>
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
              </tr>
              <tr>
                <td colSpan={14}>
                  Employer cost including employer contributions
                </td>
                <td className="number">{formatValue(run.totalEmployerCost, "money")}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      <div className={`status-bar ${status.tone}`}>{status.text}</div>
    </section>
  );
}

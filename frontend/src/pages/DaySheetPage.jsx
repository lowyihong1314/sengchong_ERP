import React from "react";
import { RefreshCw, Save } from "lucide-react";

import { formatValue, readValue } from "../lib/format.js";

/**
 * Batch attendance for one date and one company.
 *
 * Every active employee is listed whether or not anything is recorded, because
 * the foreman goes down the crew once at the end of the day rather than
 * hunting for who is missing. Clearing a row to zero deletes its entry, so
 * fixing a mistake is the same gesture as making one.
 *
 * Somebody who worked for both companies that day appears on both sheets and
 * is paid a full day by each; that is the arrangement here, not a double
 * entry to be warned about.
 */
export function DaySheetPage({
  companies,
  company,
  loading,
  rows,
  saving,
  status,
  workDate,
  onCompanyChange,
  onDateChange,
  onRefresh,
  onRowChange,
  onSave,
}) {
  const totals = rows.reduce(
    (sum, row) => ({
      days: sum.days + Number(row.dayUnits || 0),
      ot: sum.ot + Number(row.otHours || 0),
      nights: sum.nights + Number(row.overnightNights || 0),
      pay: sum.pay + (row.payable ? Number(row.totalPay || 0) : 0),
    }),
    { days: 0, ot: 0, nights: 0, pay: 0 }
  );
  const recorded = rows.filter((row) => Number(row.dayUnits || 0) || Number(row.otHours || 0));
  const missingSetup = rows.filter((row) => !row.payable && !row.entryId).length;

  return (
    <section className="content-panel day-sheet-page">
      <div className="detail-page-header">
        <div>
          <h2>Daily Entry</h2>
          <p>
            {recorded.length} of {rows.length} recorded
            {missingSetup ? ` - ${missingSetup} without salary setup` : ""}
          </p>
        </div>
        <div className="topbar-actions">
          <button className="ghost-button" disabled={loading} type="button" onClick={onRefresh}>
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
          <button className="primary-button" disabled={saving || loading} type="button" onClick={onSave}>
            <Save aria-hidden="true" size={16} />
            {saving ? "Saving..." : "Save Sheet"}
          </button>
        </div>
      </div>

      <div className="toolbar">
        <label className="form-field">
          <span>Date</span>
          <input
            type="date"
            value={workDate}
            onChange={(event) => onDateChange(event.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Company</span>
          <select value={company} onChange={(event) => onCompanyChange(event.target.value)}>
            {companies.map((item) => (
              <option key={item.value} value={item.value}>
                {item.value} - {item.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="table-wrap">
        <table className="day-sheet-table">
          <thead>
            <tr>
              <th>Employee</th>
              <th>Position</th>
              <th className="number">Days</th>
              <th className="number">OT Hrs</th>
              <th className="number">Nights</th>
              <th className="number">Night Hrs</th>
              <th>Project</th>
              <th>Remark</th>
              <th className="number">Pay</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={9}>{loading ? "Loading..." : "No active employees."}</td>
              </tr>
            ) : (
              rows.map((row) => {
                const touched =
                  Number(row.dayUnits || 0) ||
                  Number(row.otHours || 0) ||
                  Number(row.overnightNights || 0) ||
                  Number(row.overnightHours || 0);
                return (
                  <tr className={touched ? "recorded" : ""} key={row.employeeId}>
                    <td>
                      <strong>{readValue(row, "name")}</strong>
                      <span>{readValue(row, "employeeCode")}</span>
                    </td>
                    <td>{readValue(row, "position") || "-"}</td>
                    {["dayUnits", "otHours", "overnightNights", "overnightHours"].map((field) => (
                      <td className="number" key={field}>
                        <input
                          className="cell-input"
                          min="0"
                          step={field === "overnightNights" ? "1" : "0.25"}
                          type="number"
                          value={row[field] ?? ""}
                          onChange={(event) => onRowChange(row.employeeId, field, event.target.value)}
                        />
                      </td>
                    ))}
                    <td>
                      <input
                        className="cell-input"
                        placeholder="optional"
                        value={row.projectCode ?? ""}
                        onChange={(event) =>
                          onRowChange(row.employeeId, "projectCode", event.target.value)
                        }
                      />
                    </td>
                    <td>
                      <input
                        className="cell-input"
                        value={row.note ?? ""}
                        onChange={(event) => onRowChange(row.employeeId, "note", event.target.value)}
                      />
                    </td>
                    <td className="number">
                      {row.payable ? (
                        formatValue(row.totalPay, "money")
                      ) : (
                        <span className="muted" title={row.payableNote}>
                          no setup
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
          {rows.length > 0 && (
            <tfoot>
              <tr>
                <td colSpan={2}>Total</td>
                <td className="number">{totals.days.toFixed(2)}</td>
                <td className="number">{totals.ot.toFixed(2)}</td>
                <td className="number">{totals.nights.toFixed(2)}</td>
                <td className="number" />
                <td colSpan={2} />
                <td className="number">{formatValue(totals.pay, "money")}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      <div className={`status-bar ${status.tone}`}>{status.text}</div>
    </section>
  );
}

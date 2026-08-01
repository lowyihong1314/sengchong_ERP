import { formatValue, getRelatedRowKey, readValue } from "../lib/format.js";

export function DetailDataTable({ title, rows, columns, emptyText, currencyCode, onRowClick }) {
  const clickable = Boolean(onRowClick);

  return (
    <section className="related-section">
      <div className="related-section-header">
        <h3>{title}</h3>
        <span>{rows.length} row{rows.length === 1 ? "" : "s"}</span>
      </div>
      <div className="related-table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map(([, label]) => (
                <th key={`${title}-${label}`}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr className="empty-row">
                <td colSpan={columns.length}>{emptyText}</td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <tr
                  className={clickable ? "clickable-row" : ""}
                  key={getRelatedRowKey(row, index)}
                  onClick={clickable ? () => onRowClick(row) : undefined}
                >
                  {columns.map(([key, , kind]) => (
                    <td className={kind === "number" || kind === "money" ? "number" : ""} key={key}>
                      {formatValue(readValue(row, key), kind, currencyCode)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

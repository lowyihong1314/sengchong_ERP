import { formatValue } from "../lib/format.js";

export function TotalSummary({ items }) {
  return (
    <dl className="total-summary">
      {items.map(([label, value, kind]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{formatValue(value, kind)}</dd>
        </div>
      ))}
    </dl>
  );
}

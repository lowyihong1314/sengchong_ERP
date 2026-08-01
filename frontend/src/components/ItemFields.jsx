import {
  formatValue,
  isFlagOn,
  readValue,
  toNumber,
} from "../lib/format.js";

export function ItemFieldList({ detail, fields }) {
  return (
    <dl className="item-field-list">
      {fields.map(([key, label, kind]) => (
        <div key={key}>
          <dt>{label}</dt>
          <dd>{formatValue(readValue(detail, key), kind) || "-"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ItemFlag({ label, value }) {
  const enabled = isFlagOn(value);

  return (
    <span className={`item-flag ${enabled ? "on" : ""}`}>
      {label}: {enabled ? "Yes" : "No"}
    </span>
  );
}

export function ItemMetrics({ data }) {
  const price = readValue(data, "price");
  const cost = readValue(data, "cost");
  const hasPrice = price !== "" && price !== null && price !== undefined;
  const hasCost = cost !== "" && cost !== null && cost !== undefined;
  const margin = hasPrice && hasCost ? toNumber(price, 0) - toNumber(cost, 0) : "";

  return (
    <dl className="item-metrics">
      <div>
        <dt>Price</dt>
        <dd>{formatValue(price, "number") || "-"}</dd>
      </div>
      <div>
        <dt>Cost</dt>
        <dd>{formatValue(cost, "number") || "-"}</dd>
      </div>
      <div>
        <dt>Margin</dt>
        <dd>{margin === "" ? "-" : formatValue(margin, "number")}</dd>
      </div>
    </dl>
  );
}

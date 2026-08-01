import {
  ArrowLeft,
  Save,
} from "lucide-react";
import { FieldInput } from "../components/FormInputs.jsx";
import { ItemMetrics } from "../components/ItemFields.jsx";

export function ItemNewPage({ module, data, onBack, onChange, onSave, status }) {
  const fields = new Map(module.formFields.map((field) => [field.name, field]));
  const renderField = (name) => {
    const field = fields.get(name);
    if (!field) return null;

    return (
      <FieldInput
        field={field}
        key={field.name}
        value={data[field.name]}
        onChange={(value) => onChange(field.name, value)}
      />
    );
  };

  return (
    <section className="content-panel item-page">
      <div className="detail-page-header">
        <button className="secondary-button" type="button" onClick={onBack}>
          <ArrowLeft aria-hidden="true" size={16} />
          Back
        </button>
        <div>
          <h2>New Item</h2>
          <p>Stock item master</p>
        </div>
        <div className="page-header-actions">
          <button className="primary-button" type="button" onClick={onSave}>
            <Save aria-hidden="true" size={16} />
            Save Item
          </button>
        </div>
      </div>
      <div className={`status-bar ${status?.tone || ""}`}>{status?.text || "Ready"}</div>

      <div className="item-new-layout">
        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Basic Info</h3>
          </div>
          <div className="item-form-grid">
            {["itemCode", "description"].map(renderField)}
          </div>
        </section>

        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>UOM & Pricing</h3>
          </div>
          <div className="item-form-grid">
            {["baseUom", "salesUom", "purchaseUom", "uomRate", "price", "cost"].map(renderField)}
          </div>
        </section>

        <section className="item-card">
          <div className="item-card-header">
            <h3>Classification</h3>
          </div>
          <div className="item-form-grid single">
            {["itemGroup", "itemType", "itemBrand", "itemCategory"].map(renderField)}
          </div>
        </section>

        <section className="item-card">
          <div className="item-card-header">
            <h3>Tax</h3>
          </div>
          <div className="item-form-grid single">
            {["taxCode", "purchaseTaxCode"].map(renderField)}
          </div>
        </section>

        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Controls</h3>
          </div>
          <div className="item-control-grid">
            {["isActive", "isSalesItem", "isPurchaseItem", "allowUpdate"].map(renderField)}
          </div>
        </section>

        <section className="item-save-panel">
          <ItemMetrics data={data} />
          <button className="primary-button" type="button" onClick={onSave}>
            <Save aria-hidden="true" size={16} />
            Save Item
          </button>
        </section>
      </div>
    </section>
  );
}

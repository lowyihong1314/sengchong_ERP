import {
  ArrowLeft,
  Package,
  RefreshCw,
} from "lucide-react";
import { ItemFieldList, ItemFlag, ItemMetrics } from "../components/ItemFields.jsx";
import { formatValue, getDetailLines, readValue } from "../lib/format.js";

export function ItemDetailPage({ module, detail, detailKey, loading, status, onBack, onRefresh }) {
  const uoms = getDetailLines(module, detail);
  const primaryUom = uoms[0] || {};
  const detailWithPrice = detail
    ? {
        ...detail,
        price: readValue(primaryUom, "price"),
        cost: readValue(primaryUom, "cost"),
      }
    : {};
  const pageTitle = detail ? readValue(detail, "itemCode") : module.singular;

  return (
    <section className="content-panel item-page">
      <div className="detail-page-header">
        <button className="secondary-button" type="button" onClick={onBack}>
          <ArrowLeft aria-hidden="true" size={16} />
          Back
        </button>
        <div>
          <h2>{pageTitle}</h2>
          <p>Stock item master</p>
        </div>
        <button className="icon-button" type="button" onClick={onRefresh} title="Refresh item">
          <RefreshCw aria-hidden="true" size={17} />
        </button>
      </div>
      <div className={`status-bar ${status?.tone || ""}`}>{status?.text || "Ready"}</div>

      {loading ? (
        <div className="detail-empty">Loading...</div>
      ) : !detail ? (
        <div className="detail-empty">No item selected</div>
      ) : (
        <>
          <section className="item-hero">
            <div className="item-hero-icon">
              <Package aria-hidden="true" size={26} />
            </div>
            <div className="item-hero-main">
              <span>Item Master</span>
              <h2>{readValue(detail, "itemCode")}</h2>
              <p>{readValue(detail, "description") || "No description"}</p>
            </div>
            <div className="item-hero-flags">
              <ItemFlag label="Active" value={readValue(detail, "isActive")} />
              <ItemFlag label="Sales" value={readValue(detail, "isSalesItem")} />
              <ItemFlag label="Purchase" value={readValue(detail, "isPurchaseItem")} />
            </div>
          </section>

          <div className="item-detail-layout">
            <section className="item-card">
              <div className="item-card-header">
                <h3>Profile</h3>
              </div>
              <ItemFieldList
                detail={detail}
                fields={[
                  ["description", "Description"],
                  ["desc2", "Description 2"],
                  ["baseUom", "Base UOM"],
                  ["salesUom", "Sales UOM"],
                  ["purchaseUom", "Purchase UOM"],
                ]}
              />
            </section>

            <section className="item-card">
              <div className="item-card-header">
                <h3>Classification</h3>
              </div>
              <ItemFieldList
                detail={detail}
                fields={[
                  ["itemGroup", "Group"],
                  ["itemType", "Type"],
                  ["itemBrand", "Brand"],
                  ["itemCategory", "Category"],
                ]}
              />
            </section>

            <section className="item-card">
              <div className="item-card-header">
                <h3>Pricing</h3>
              </div>
              <ItemMetrics data={detailWithPrice} />
            </section>

            <section className="item-card">
              <div className="item-card-header">
                <h3>Tax</h3>
              </div>
              <ItemFieldList
                detail={detail}
                fields={[
                  ["taxCode", "Sales Tax"],
                  ["purchaseTaxCode", "Purchase Tax"],
                  ["stockControl", "Stock Control"],
                  ["discontinued", "Discontinued"],
                ]}
              />
            </section>

            <section className="item-card item-card-wide">
              <div className="item-card-header">
                <h3>UOM & Price Levels</h3>
              </div>
              <div className="item-uom-table">
                <table>
                  <thead>
                    <tr>
                      {module.detailLineColumns.map(([, label]) => (
                        <th key={`${detailKey}-${label}`}>{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {uoms.length === 0 ? (
                      <tr className="empty-row">
                        <td colSpan={module.detailLineColumns.length}>No UOM rows</td>
                      </tr>
                    ) : (
                      uoms.map((uom, index) => (
                        <tr key={readValue(uom, "uom") || index}>
                          {module.detailLineColumns.map(([key, , kind]) => (
                            <td className={kind === "number" ? "number" : ""} key={key}>
                              {formatValue(readValue(uom, key), kind)}
                            </td>
                          ))}
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </>
      )}
    </section>
  );
}

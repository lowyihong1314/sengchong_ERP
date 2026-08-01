import {
  Globe2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";

export function RdpAllowPage({
  data,
  input,
  loading,
  status,
  onInputChange,
  onAdd,
  onAddCurrent,
  onApply,
  onRefresh,
  onRemove,
}) {
  const externalIps = data?.externalIps || [];
  const lanCidrs = data?.lanCidrs || [];
  const effectiveRemoteIps = data?.effectiveRemoteIps || [];
  const currentIp = data?.currentRdpRemoteIp || "";
  const recentLog = data?.recentLog || [];

  return (
    <section className="content-panel rdp-page">
      <div className="detail-page-header">
        <div className="rdp-title">
          <div className="item-hero-icon">
            <ShieldCheck aria-hidden="true" size={24} />
          </div>
          <div>
            <h2>Allow IP for RDP</h2>
            <p>Windows Remote Desktop</p>
          </div>
        </div>
        <div className="page-header-actions rdp-actions">
          <button className="secondary-button" type="button" onClick={onRefresh}>
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
          <button className="primary-button" type="button" onClick={onApply}>
            <ShieldCheck aria-hidden="true" size={16} />
            Apply
          </button>
        </div>
      </div>

      <div className={`status-bar ${status?.tone || ""}`}>
        {loading ? "Loading..." : status?.text || "Ready"}
      </div>

      <div className="rdp-layout">
        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Current Session</h3>
          </div>
          <div className="rdp-current">
            <div>
              <span>RDP Source</span>
              <strong>{currentIp || "-"}</strong>
            </div>
            <button
              className="secondary-button"
              disabled={!currentIp}
              type="button"
              onClick={onAddCurrent}
            >
              <Plus aria-hidden="true" size={16} />
              Add Current
            </button>
          </div>
        </section>

        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Public IPs</h3>
          </div>
          <form className="rdp-add-form" onSubmit={onAdd}>
            <label className="form-field" htmlFor="rdp-ip-input">
              <span>IPv4 Address</span>
              <input
                id="rdp-ip-input"
                value={input}
                onChange={(event) => onInputChange(event.target.value)}
                inputMode="decimal"
                placeholder="180.74.224.155"
              />
            </label>
            <button className="primary-button" type="submit">
              <Plus aria-hidden="true" size={16} />
              Add IP
            </button>
          </form>

          <div className="rdp-ip-list">
            {externalIps.length === 0 ? (
              <div className="detail-empty">No public IPs</div>
            ) : (
              externalIps.map((ip) => (
                <div className="rdp-ip-row" key={ip}>
                  <div>
                    <Globe2 aria-hidden="true" size={16} />
                    <span>{ip}</span>
                  </div>
                  <button
                    className="icon-button danger-button"
                    type="button"
                    onClick={() => onRemove(ip)}
                    title="Remove IP"
                  >
                    <Trash2 aria-hidden="true" size={16} />
                  </button>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="item-card">
          <div className="item-card-header">
            <h3>LAN</h3>
          </div>
          <div className="rdp-chip-list">
            {lanCidrs.map((cidr) => (
              <span className="item-flag on" key={cidr}>
                {cidr}
              </span>
            ))}
          </div>
        </section>

        <section className="item-card">
          <div className="item-card-header">
            <h3>Effective Sources</h3>
          </div>
          <div className="rdp-chip-list">
            {effectiveRemoteIps.map((source) => (
              <span className="item-flag" key={source}>
                {source}
              </span>
            ))}
          </div>
        </section>

        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Recent Guard Log</h3>
          </div>
          <pre className="rdp-log">{recentLog.slice(-10).join("\n") || "No log entries"}</pre>
        </section>
      </div>
    </section>
  );
}

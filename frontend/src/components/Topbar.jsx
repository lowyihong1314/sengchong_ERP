import { LogOut, RefreshCw } from "lucide-react";

/** Module title, company switcher, signed-in user, logout and refresh. */
export function Topbar({
  companies,
  module,
  selectedCompany,
  session,
  onLogout,
  onRefresh,
  onSwitchCompany,
}) {
  return (
    <header className="topbar">
      <div>
        <h1>{module.title}</h1>
        <p>{module.meta}</p>
      </div>
      <div className="topbar-actions">
        <label className="company-switch" htmlFor="company-switch">
          <span>Company</span>
          <select id="company-switch" value={selectedCompany} onChange={onSwitchCompany}>
            {companies.map((company) => (
              <option key={company.value} value={company.value}>
                {company.value} - {company.label}
              </option>
            ))}
          </select>
        </label>
        <span className="session-pill signed-in">
          {session?.displayName || session?.username || "Signed in"}
        </span>
        <button className="secondary-button" type="button" onClick={onLogout}>
          <LogOut aria-hidden="true" size={16} />
          Logout
        </button>
        <button className="icon-button" type="button" onClick={onRefresh} title="Refresh">
          <RefreshCw aria-hidden="true" size={17} />
        </button>
      </div>
    </header>
  );
}

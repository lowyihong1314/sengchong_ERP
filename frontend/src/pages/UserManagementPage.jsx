import {
  Plus,
  RefreshCw,
  Trash2,
  Users,
} from "lucide-react";
import { USER_ROLE_OPTIONS } from "../constants.js";
import { formatValue, readValue } from "../lib/format.js";

export function UserManagementPage({
  companies,
  draft,
  loading,
  saving,
  status,
  users,
  onDelete,
  onDraftChange,
  onRefresh,
  onSubmit,
}) {
  const userRows = Array.isArray(users) ? users : [];

  return (
    <section className="content-panel item-page user-management-page">
      <div className="detail-page-header">
        <div className="rdp-title">
          <div className="item-hero-icon">
            <Users aria-hidden="true" size={24} />
          </div>
          <div>
            <h2>User Management</h2>
            <p>ERP login users</p>
          </div>
        </div>
        <div className="page-header-actions">
          <button className="secondary-button" type="button" onClick={onRefresh}>
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
        </div>
      </div>

      <div className={`status-bar ${status?.tone || ""}`}>
        {loading ? "Loading users..." : status?.text || "Ready"}
      </div>

      <div className="user-management-layout">
        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Add User</h3>
          </div>
          <form className="user-form-grid" onSubmit={onSubmit}>
            <label className="form-field" htmlFor="user-management-username">
              <span>Username</span>
              <input
                id="user-management-username"
                autoComplete="username"
                value={draft.username || ""}
                onChange={(event) => onDraftChange("username", event.target.value)}
                required
              />
            </label>
            <label className="form-field" htmlFor="user-management-display-name">
              <span>Display Name</span>
              <input
                id="user-management-display-name"
                value={draft.displayName || ""}
                onChange={(event) => onDraftChange("displayName", event.target.value)}
              />
            </label>
            <label className="form-field" htmlFor="user-management-password">
              <span>Password</span>
              <input
                id="user-management-password"
                autoComplete="new-password"
                type="password"
                value={draft.password || ""}
                onChange={(event) => onDraftChange("password", event.target.value)}
                required
              />
            </label>
            <label className="form-field" htmlFor="user-management-role">
              <span>Role</span>
              <select
                id="user-management-role"
                value={draft.role || "user"}
                onChange={(event) => onDraftChange("role", event.target.value)}
              >
                {USER_ROLE_OPTIONS.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-field" htmlFor="user-management-company">
              <span>Default Company</span>
              <select
                id="user-management-company"
                value={draft.defaultCompany || ""}
                onChange={(event) => onDraftChange("defaultCompany", event.target.value)}
              >
                <option value="">Use login selection</option>
                {companies.map((company) => (
                  <option key={company.value} value={company.value}>
                    {company.value} - {company.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="user-form-actions">
              <button className="primary-button" disabled={saving} type="submit">
                <Plus aria-hidden="true" size={16} />
                {saving ? "Saving..." : "Add User"}
              </button>
            </div>
          </form>
        </section>

        <section className="item-card item-card-wide">
          <div className="item-card-header">
            <h3>Users</h3>
          </div>
          <div className="related-table-wrap user-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Default Company</th>
                  <th>Updated</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {userRows.length === 0 ? (
                  <tr className="empty-row">
                    <td colSpan={5}>No users</td>
                  </tr>
                ) : (
                  userRows.map((user) => {
                    const username = readValue(user, "username");
                    const protectedUser = String(username).toLowerCase() === "yukang";
                    return (
                      <tr key={username}>
                        <td>
                          <strong>{readValue(user, "displayName") || username}</strong>
                          <span>{username}</span>
                        </td>
                        <td>{readValue(user, "role") || "user"}</td>
                        <td>{readValue(user, "defaultCompany") || "-"}</td>
                        <td>{formatValue(readValue(user, "updatedAt")) || "-"}</td>
                        <td>
                          <div className="user-row-actions">
                            {protectedUser && <span className="item-flag on">Protected</span>}
                            <button
                              className="icon-button danger-button"
                              disabled={saving || protectedUser}
                              type="button"
                              onClick={() => onDelete(username)}
                              title={protectedUser ? "yukang cannot be removed" : "Remove user"}
                            >
                              <Trash2 aria-hidden="true" size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </section>
  );
}

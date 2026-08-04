import React from "react";

import { EMPTY_USER_DRAFT, USER_ROLE_OPTIONS } from "../constants.js";
import { requestJson } from "../lib/api.js";
import { readValue } from "../lib/format.js";
import { normalizeRows } from "../lib/normalize.js";

/**
 * Owns the two admin-only screens: ERP user accounts and the RDP allow-list.
 * Both are ERP-owned data (never AutoCount), so they share one hook.
 */
export function useAdminSettings({
  token,
  activeModuleRef,
  authHeaders,
  handleAuthError,
  setStatus,
  updateModuleStage,
}) {
  const [rdpAllow, setRdpAllow] = React.useState(null);
  const [rdpInput, setRdpInput] = React.useState("");
  const [rdpLoading, setRdpLoading] = React.useState(false);
  const [users, setUsers] = React.useState([]);
  const [userDraft, setUserDraft] = React.useState(() => ({ ...EMPTY_USER_DRAFT }));
  const [userManagementLoading, setUserManagementLoading] = React.useState(false);
  const [userManagementSaving, setUserManagementSaving] = React.useState(false);

  const loadRdpAllowList = React.useCallback(
    async (options = {}) => {
      if (!token) return;

      try {
        setRdpLoading(true);
        if (options.showStatus !== false) {
          setStatus({ tone: "", text: "Loading RDP allow-list..." });
        }
        const payload = await requestJson("/api/rdp-allow-list", {
          headers: authHeaders(),
        });
        setRdpAllow(payload);
        if (options.showStatus !== false) {
          setStatus({
            tone: "ok",
            text: `${(payload.externalIps || []).length} public IP${
              (payload.externalIps || []).length === 1 ? "" : "s"
            } allowed`,
          });
        }
      } catch (error) {
        handleAuthError(error);
        setStatus({ tone: "error", text: error.message });
      } finally {
        setRdpLoading(false);
      }
    },
    [authHeaders, handleAuthError, token]
  );

  const loadUsers = React.useCallback(
    async (options = {}) => {
      if (!token) return;

      try {
        setUserManagementLoading(true);
        if (options.showStatus !== false) {
          setStatus({ tone: "", text: "Loading users..." });
        }
        const payload = await requestJson("/api/users", {
          headers: authHeaders(),
        });
        const nextUsers = normalizeRows(payload);
        const nextStatus = {
          tone: "ok",
          text: `${nextUsers.length} user${nextUsers.length === 1 ? "" : "s"}`,
        };
        setUsers(nextUsers);
        updateModuleStage("user-management", {
          rows: nextUsers,
          loaded: true,
          status: nextStatus,
        });
        if (activeModuleRef.current === "user-management" && options.showStatus !== false) {
          setStatus(nextStatus);
        }
      } catch (error) {
        handleAuthError(error);
        const nextStatus = { tone: "error", text: error.message };
        updateModuleStage("user-management", { status: nextStatus });
        if (activeModuleRef.current === "user-management") {
          setStatus(nextStatus);
        }
      } finally {
        setUserManagementLoading(false);
      }
    },
    [authHeaders, handleAuthError, token, updateModuleStage]
  );

  function getRdpApplyStatus(payload, fallback) {
    if (payload?.apply && !payload.apply.ok) {
      return {
        tone: "error",
        text: payload.apply.stderr || payload.apply.stdout || "Saved, but apply failed",
      };
    }
    return { tone: "ok", text: fallback };
  }

  async function addRdpIp(event, overrideIp = "") {
    if (event?.preventDefault) {
      event.preventDefault();
    }

    const ip = (overrideIp || rdpInput).trim();
    if (!ip) {
      setStatus({ tone: "error", text: "IP address is required" });
      return;
    }

    try {
      setRdpLoading(true);
      setStatus({ tone: "", text: "Saving RDP allow-list..." });
      const payload = await requestJson("/api/rdp-allow-list/ip", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ ip }),
      });
      setRdpAllow(payload);
      setRdpInput("");
      setStatus(getRdpApplyStatus(payload, `Allowed ${ip}`));
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setRdpLoading(false);
    }
  }

  async function removeRdpIp(ip) {
    try {
      setRdpLoading(true);
      setStatus({ tone: "", text: "Updating RDP allow-list..." });
      const payload = await requestJson(`/api/rdp-allow-list/ip/${encodeURIComponent(ip)}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      setRdpAllow(payload);
      setStatus(getRdpApplyStatus(payload, `Removed ${ip}`));
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setRdpLoading(false);
    }
  }

  async function applyRdpAllowList() {
    try {
      setRdpLoading(true);
      setStatus({ tone: "", text: "Applying RDP firewall..." });
      const payload = await requestJson("/api/rdp-allow-list/apply", {
        method: "POST",
        headers: authHeaders(),
      });
      setRdpAllow(payload);
      setStatus(getRdpApplyStatus(payload, "RDP firewall applied"));
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setRdpLoading(false);
    }
  }

  function updateUserDraftField(name, value) {
    setUserDraft((current) => ({ ...current, [name]: value }));
  }

  async function submitUser(event) {
    event.preventDefault();

    const username = String(userDraft.username || "").trim();
    const password = String(userDraft.password || "");
    const role = USER_ROLE_OPTIONS.includes(userDraft.role) ? userDraft.role : "user";
    if (!username) {
      setStatus({ tone: "error", text: "Username is required" });
      return;
    }
    if (!password) {
      setStatus({ tone: "error", text: "Password is required" });
      return;
    }

    try {
      setUserManagementSaving(true);
      setStatus({ tone: "", text: "Saving user..." });
      const saved = await requestJson("/api/users", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          username,
          password,
          displayName: userDraft.displayName,
          role,
          defaultCompany: userDraft.defaultCompany,
        }),
      });
      await loadUsers({ showStatus: false });
      setUserDraft({ ...EMPTY_USER_DRAFT });
      setStatus({
        tone: "ok",
        text: `Saved user ${readValue(saved, "username") || username}`,
      });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setUserManagementSaving(false);
    }
  }

  async function changeDefaultCompany(username, company) {
    const target = String(username || "").trim().toLowerCase();
    if (!target) return;
    try {
      setUserManagementSaving(true);
      // PATCH, not the upsert POST -- that one takes a password and would
      // reset theirs as a side effect of changing a company.
      await requestJson(`/api/users/${encodeURIComponent(target)}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ defaultCompany: company }),
      });
      await loadUsers({ showStatus: false });
      setStatus({
        tone: "ok",
        text: company
          ? `${target} now starts in ${company}`
          : `${target} will use whatever they pick at login`,
      });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setUserManagementSaving(false);
    }
  }

  async function deleteUser(username) {
    const target = String(username || "").trim().toLowerCase();
    if (!target) return;
    if (target === "yukang") {
      setStatus({ tone: "error", text: "yukang cannot be removed" });
      return;
    }
    if (!window.confirm(`Remove user ${target}?`)) return;

    try {
      setUserManagementSaving(true);
      setStatus({ tone: "", text: "Removing user..." });
      await requestJson(`/api/users/${encodeURIComponent(target)}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      await loadUsers({ showStatus: false });
      setStatus({ tone: "ok", text: `Removed user ${target}` });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setUserManagementSaving(false);
    }
  }

  // Full teardown, used when the whole workspace resets (logout, company switch).
  const resetAdminSettings = React.useCallback(() => {
    setRdpAllow(null);
    setRdpInput("");
    setUsers([]);
    setUserDraft({ ...EMPTY_USER_DRAFT });
    setUserManagementLoading(false);
    setUserManagementSaving(false);
  }, []);

  // Narrower teardown that runs when the token disappears. The set of fields
  // cleared here is deliberately kept identical to the pre-refactor behaviour.
  const clearAdminSettingsOnSignOut = React.useCallback(() => {
    setUsers([]);
    setUserDraft({ ...EMPTY_USER_DRAFT });
    setUserManagementLoading(false);
    setUserManagementSaving(false);
  }, []);

  return {
    rdpAllow,
    rdpInput,
    rdpLoading,
    userDraft,
    userManagementLoading,
    userManagementSaving,
    users,
    addRdpIp,
    applyRdpAllowList,
    clearAdminSettingsOnSignOut,
    changeDefaultCompany,
    deleteUser,
    loadRdpAllowList,
    loadUsers,
    removeRdpIp,
    resetAdminSettings,
    setRdpInput,
    submitUser,
    updateUserDraftField,
  };
}

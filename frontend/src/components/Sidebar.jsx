import React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { MODULE_GROUPS } from "../constants.js";
import { MODULES } from "../modules.js";

/**
 * Left-hand module rail, grouped by area. Clicking a tab always opens that
 * module's list. The group holding the active module is kept expanded, so
 * arriving by URL or by Back never leaves the current tab hidden.
 */
export function Sidebar({ activeModule, onSelectModule }) {
  const activeGroup = MODULE_GROUPS.find((group) => group.modules.includes(activeModule))?.key;
  const [openGroups, setOpenGroups] = React.useState(() => new Set(activeGroup ? [activeGroup] : []));

  React.useEffect(() => {
    if (!activeGroup) return;
    setOpenGroups((current) =>
      current.has(activeGroup) ? current : new Set([...current, activeGroup])
    );
  }, [activeGroup]);

  function toggleGroup(key) {
    setOpenGroups((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">AC</div>
        <div>
          <div className="brand-name">AutoCount</div>
          <div className="brand-subtitle">ERP Gateway</div>
        </div>
      </div>

      <nav className="nav" aria-label="Main modules">
        {MODULE_GROUPS.map((group) => {
          const open = openGroups.has(group.key);
          const hasActive = group.modules.includes(activeModule);
          const ChevronIcon = open ? ChevronDown : ChevronRight;
          return (
            <div className="nav-group" key={group.key}>
              <button
                aria-expanded={open}
                className={`nav-group-header ${hasActive ? "has-active" : ""}`}
                type="button"
                onClick={() => toggleGroup(group.key)}
              >
                <ChevronIcon aria-hidden="true" size={14} />
                <span>{group.label}</span>
              </button>

              {open && (
                <div className="nav-group-items">
                  {group.modules.map((key) => {
                    const module = MODULES[key];
                    const Icon = module.icon;
                    return (
                      <button
                        className={`nav-item ${activeModule === key ? "active" : ""}`}
                        key={key}
                        type="button"
                        onClick={() => onSelectModule(key)}
                      >
                        <Icon aria-hidden="true" size={17} />
                        <span>{module.label}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}

import React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { MODULE_GROUPS } from "../constants.js";
import { MODULES } from "../modules.js";

/**
 * Left-hand module rail, grouped by area. Clicking a tab always opens that
 * module's list. The group holding the active module is kept expanded, so
 * arriving by URL or by Back never leaves the current tab hidden.
 *
 * On a narrow screen the same rail becomes a drawer that slides in from the
 * left, over the page rather than above it. `open` and `onClose` are only
 * consulted at that width -- on a desktop the rail is always there and neither
 * does anything.
 */
export function Sidebar({ activeModule, open, onClose, onSelectModule }) {
  const activeGroup = MODULE_GROUPS.find((group) => group.modules.includes(activeModule))?.key;
  const [openGroups, setOpenGroups] = React.useState(() => new Set(activeGroup ? [activeGroup] : []));

  React.useEffect(() => {
    if (!activeGroup) return;
    setOpenGroups((current) =>
      current.has(activeGroup) ? current : new Set([...current, activeGroup])
    );
  }, [activeGroup]);

  // Escape closes the drawer, which is what a phone keyboard user and anyone
  // on a tablet with a keyboard will try first.
  React.useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  // The page behind a drawer must not scroll: on a phone, dragging the scrim
  // otherwise moves the content underneath and the drawer looks broken.
  React.useEffect(() => {
    if (!open) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  function toggleGroup(key) {
    setOpenGroups((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <>
      {/* Rendered only while open so it cannot swallow clicks on a desktop,
          where the drawer does not exist at all. */}
      {open && <div className="sidebar-scrim" onClick={onClose} />}

      <aside className={`sidebar${open ? " open" : ""}`}>
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
                        onClick={() => {
                          onSelectModule(key);
                          onClose?.();
                        }}
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
    </>
  );
}

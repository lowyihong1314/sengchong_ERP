import { moduleKeys } from "../constants.js";
import { MODULES } from "../modules.js";

/** Left-hand module rail. Clicking a tab always opens that module's list. */
export function Sidebar({ activeModule, onSelectModule }) {
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
        {moduleKeys.map((key) => {
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
      </nav>
    </aside>
  );
}

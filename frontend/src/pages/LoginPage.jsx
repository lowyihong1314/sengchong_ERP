import { LogIn } from "lucide-react";

/**
 * Standalone sign-in screen. The workspace stays hidden until Flask has
 * verified the credentials through the AutoCount SDK.
 */
export function LoginPage({ login, status, onLoginChange, onSubmit }) {
  return (
    <main className="login-screen">
      <section className="login-card">
        <div className="login-card-header">
          <div className="brand-mark">AC</div>
          <div>
            <h1>AutoCount ERP Gateway</h1>
            <p>Sign in with your ERP user.</p>
          </div>
        </div>

        <form className="login-form login-form-stacked" onSubmit={onSubmit}>
          <label className="login-field">
            <span>User</span>
            <input
              className="login-input"
              value={login.username}
              onChange={(event) => onLoginChange("username", event.target.value)}
              autoComplete="username"
            />
          </label>
          <label className="login-field">
            <span>Password</span>
            <input
              className="login-input"
              value={login.password}
              onChange={(event) => onLoginChange("password", event.target.value)}
              type="password"
              autoComplete="current-password"
            />
          </label>
          <button className="primary-button" type="submit">
            <LogIn aria-hidden="true" size={16} />
            Login
          </button>
        </form>

        <div className={`status-bar login-status ${status.tone}`}>{status.text}</div>
      </section>
    </main>
  );
}

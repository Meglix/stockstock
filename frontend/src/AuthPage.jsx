import { useEffect, useState } from "react";

const MODES = ["login", "register"];

const PW_RULES = [
  { key: "len",     label: "At least 8 characters",       test: (p) => p.length >= 8 },
  { key: "upper",   label: "One uppercase letter (A–Z)",   test: (p) => /[A-Z]/.test(p) },
  { key: "number",  label: "One number (0–9)",             test: (p) => /[0-9]/.test(p) },
  { key: "special", label: "One special character (!@#…)", test: (p) => /[^A-Za-z0-9]/.test(p) },
];

const EMAIL_RULES = [
  { key: "at",  label: 'Contains "@"',          test: (e) => e.includes("@") },
  { key: "dot", label: 'Has a domain (e.g. .com)', test: (e) => /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(e) },
];

function getSafeAuthError(mode) {
  if (mode === "login") {
    return "Invalid username or password.";
  }
  return "Could not create account. Please check your input and try again.";
}

export default function AuthPage({ onAuthSuccess, initialError = "" }) {
  const [mode, setMode] = useState("login");
  const [focusedField, setFocusedField] = useState(null);
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialError) {
      setError(initialError);
    }
  }, [initialError]);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const payload =
        mode === "login"
          ? { username, password }
          : {
              first_name: firstName.trim(),
              last_name: lastName.trim(),
              username,
              email,
              password,
              role: "user",
            };

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const safeMessage = typeof data?.detail === "string" && data.detail.toLowerCase().includes("invalid email")
          ? "Please enter a valid email address."
          : getSafeAuthError(mode);
        setError(safeMessage);
        return;
      }

      onAuthSuccess(data);
    } catch {
      setError("Network error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-layout">
        <section className="auth-showcase">
          <div className="auth-showcase__badge">Smart Parts Management</div>
          <h2 className="auth-showcase__title">Keep stock healthy across every location.</h2>
          <p className="auth-showcase__text">
            Forecast demand, monitor stock risk, and coordinate replenishment decisions in one place.
          </p>
          <div className="auth-showcase__stats">
            <div className="auth-stat">
              <span className="auth-stat__value">18+</span>
              <span className="auth-stat__label">Parts tracked</span>
            </div>
            <div className="auth-stat">
              <span className="auth-stat__value">EU</span>
              <span className="auth-stat__label">Multi-location</span>
            </div>
            <div className="auth-stat">
              <span className="auth-stat__value">24h</span>
              <span className="auth-stat__label">Token window</span>
            </div>
          </div>
        </section>

        <section className={`auth-card auth-card--${mode}`}>
          <div className="auth-brand">AutoParts Optimizer</div>
          <h1 className="auth-title">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p className="auth-subtitle">
            {mode === "login"
              ? "Sign in with your existing admin or user account."
              : "Create a new internal user account to access the dashboard and workflows."}
          </p>

          <div className={`auth-mode-switch auth-mode-switch--${mode}`}>
            {MODES.map((m) => (
              <button
                key={m}
                className={`auth-tab ${mode === m ? "is-active" : ""}`}
                onClick={() => {
                  setMode(m);
                  setError("");
                }}
                type="button"
              >
                {m === "login" ? "Sign In" : "Create Account"}
              </button>
            ))}
          </div>

          <form className="auth-form" onSubmit={submit}>
            <div className="auth-register-fields" data-visible={mode === "register"}>
              <div className="auth-name-row">
                <div>
                  <label>First Name *</label>
                  <input value={firstName} onChange={(e) => setFirstName(e.target.value)} maxLength={80} required={mode === "register"} />
                </div>
                <div>
                  <label>Last Name *</label>
                  <input value={lastName} onChange={(e) => setLastName(e.target.value)} maxLength={80} required={mode === "register"} />
                </div>
              </div>

              <label>Email *</label>
              <div className="field-wrap">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onFocus={() => setFocusedField("email")}
                  onBlur={() => setFocusedField(null)}
                  required={mode === "register"}
                />
                {focusedField === "email" && email.length > 0 && (
                  <ul className="pw-rules pw-rules--bubble">
                    {EMAIL_RULES.map((r) => (
                      <li key={r.key} className={`pw-rule ${r.test(email) ? "pw-rule--ok" : "pw-rule--fail"}`}>
                        <span className="pw-rule__icon">{r.test(email) ? "✓" : "✗"}</span>
                        {r.label}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <label>Username *</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} minLength={3} required />

            <label>Password *</label>
            <div className="field-wrap">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={() => setFocusedField("password")}
                onBlur={() => setFocusedField(null)}
                minLength={8}
                required
              />
              {mode === "register" && focusedField === "password" && password.length > 0 && (
                <ul className="pw-rules pw-rules--bubble">
                  {PW_RULES.map((r) => (
                    <li key={r.key} className={`pw-rule ${r.test(password) ? "pw-rule--ok" : "pw-rule--fail"}`}>
                      <span className="pw-rule__icon">{r.test(password) ? "✓" : "✗"}</span>
                      {r.label}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {error && (
              <div className="state state--error state--animated">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: 15, height: 15, flexShrink: 0 }}>
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                {error}
              </div>
            )}

            <button className="btn-primary" type="submit" disabled={submitting}>
              {submitting ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
            </button>

            <small className="auth-required-note">Fields marked with * are required.</small>
            {mode === "register" && (
              <small className="auth-required-note">Register creates a user account only in the current flow.</small>
            )}
          </form>
        </section>
      </div>
    </div>
  );
}

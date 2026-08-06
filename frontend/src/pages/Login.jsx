import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/home";

  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function onChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(form);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Welcome back</h1>
        <p className="muted">Log in to continue your Safe Journey setup.</p>

        {error && <div className="alert alert-error">{error}</div>}

        <label>
          Email
          <input
            type="email"
            name="email"
            value={form.email}
            onChange={onChange}
            required
            autoComplete="email"
            placeholder="you@example.com"
          />
        </label>

        <label>
          Password
          <input
            type="password"
            name="password"
            value={form.password}
            onChange={onChange}
            required
            autoComplete="current-password"
            placeholder="Your password"
          />
        </label>

        <button className="btn" type="submit" disabled={submitting}>
          {submitting ? "Signing in…" : "Login"}
        </button>

        <p className="switch-auth">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </form>
    </main>
  );
}

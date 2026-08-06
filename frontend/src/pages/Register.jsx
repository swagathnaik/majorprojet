import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    password: "",
  });
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
      await register(form);
      navigate("/home");
    } catch (err) {
      setError(err.message || "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Create account</h1>
        <p className="muted">Register to start using Safe Journey Mode.</p>

        {error && <div className="alert alert-error">{error}</div>}

        <label>
          Full name
          <input
            name="name"
            value={form.name}
            onChange={onChange}
            required
            autoComplete="name"
            placeholder="Your name"
          />
        </label>

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
          Phone (optional)
          <input
            name="phone"
            value={form.phone}
            onChange={onChange}
            autoComplete="tel"
            placeholder="+91 …"
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
            minLength={6}
            autoComplete="new-password"
            placeholder="At least 6 characters"
          />
        </label>

        <button className="btn" type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Register"}
        </button>

        <p className="switch-auth">
          Already have an account? <Link to="/login">Login</Link>
        </p>
      </form>
    </main>
  );
}

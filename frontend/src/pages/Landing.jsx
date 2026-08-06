import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Landing() {
  const { isAuthenticated } = useAuth();

  return (
    <main className="page landing">
      <section className="hero">
        <p className="eyebrow">Proactive personal journey safety</p>
        <h1>SafeRoute</h1>
        <p className="lede">
          Monitor your journey for unusual patterns, verify that you are safe,
          and escalate to trusted contacts only when needed.
        </p>
        <div className="cta-row">
          {isAuthenticated ? (
            <Link className="btn" to="/home">
              Go to Home
            </Link>
          ) : (
            <>
              <Link className="btn" to="/register">
                Get started
              </Link>
              <Link className="btn btn-ghost" to="/login">
                Login
              </Link>
            </>
          )}
        </div>
        <p className="fineprint">
          SafeRoute does not replace 112 India or claim to detect crimes. It
          complements emergency systems with verification before alerts.
        </p>
      </section>
    </main>
  );
}

import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Home() {
  const { user, logout } = useAuth();

  return (
    <main className="page home-page">
      <section className="panel">
        <h1>Welcome, {user?.name}</h1>
        <p className="muted">
          Opens the map directly — search a destination, see the safest path
          from crime data, and start live monitoring.
        </p>

        <div className="profile-grid">
          <div>
            <span className="label">Email</span>
            <p>{user?.email}</p>
          </div>
          <div>
            <span className="label">Phone</span>
            <p>{user?.phone || "Not set"}</p>
          </div>
          <div>
            <span className="label">User ID</span>
            <p>{user?.id}</p>
          </div>
        </div>

        <div className="cta-row">
          <Link className="btn" to="/journey">
            START JOURNEY
          </Link>
          <Link className="btn btn-ghost" to="/contacts">
            Contacts
          </Link>
        </div>



        <button type="button" className="btn btn-ghost" onClick={logout}>
          Logout
        </button>
      </section>
    </main>
  );
}

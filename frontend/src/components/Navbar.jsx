import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <header className="navbar">
      <Link to="/" className="brand">
        SafeRoute
      </Link>
      <nav className="nav-links">
        {isAuthenticated ? (
          <>
            <span className="nav-user">Hi, {user?.name?.split(" ")[0]}</span>
            <Link to="/home">Home</Link>
            <Link to="/contacts">Contacts</Link>
            <Link to="/journey">Journey</Link>
            <button type="button" className="link-btn" onClick={logout}>
              Logout
            </button>

          </>
        ) : (
          <>
            <Link to="/login">Login</Link>
            <Link to="/register" className="btn btn-small">
              Register
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}

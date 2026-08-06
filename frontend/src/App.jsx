import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Home from "./pages/Home";
import Contacts from "./pages/Contacts";
import Track from "./pages/Track";
import Journey from "./pages/Journey";
import ContactTrack from "./pages/ContactTrack";
import "./styles/app.css";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="app-shell">
          <Navbar />
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route
              path="/home"
              element={
                <ProtectedRoute>
                  <Home />
                </ProtectedRoute>
              }
            />
            <Route
              path="/contacts"
              element={
                <ProtectedRoute>
                  <Contacts />
                </ProtectedRoute>
              }
            />
            <Route
              path="/journey"
              element={
                <ProtectedRoute>
                  <Journey />
                </ProtectedRoute>
              }
            />
            <Route
              path="/track"
              element={
                <ProtectedRoute>
                  <Track />
                </ProtectedRoute>
              }
            />
            <Route path="/s/:token" element={<ContactTrack />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

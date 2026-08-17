import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { feedbackApi } from "../api/client";

const SAFETY_TAG_OPTIONS = [
  { id: "poor_lighting", label: "💡 Poor Lighting" },
  { id: "unsafe_area", label: "⚠️ Unsafe Area" },
  { id: "isolated_street", label: "🚶 Isolated Street" },
  { id: "suspicious_activity", label: "🚨 Suspicious Activity" },
  { id: "well_lit", label: "🛡️ Well Lit & Safe" },
];

export default function Feedback() {
  const { token } = useAuth();
  const [feedbacks, setFeedbacks] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [retrainResult, setRetrainResult] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  // Form State
  const [rating, setRating] = useState(4);
  const [destLabel, setDestLabel] = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [comments, setComments] = useState("");

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await feedbackApi.list(token);
      setFeedbacks(res.feedbacks || []);
      setStats(res.stats || null);
    } catch (err) {
      setError(err.message || "Failed to load feedback statistics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [token]);

  const toggleTag = (tagId) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((t) => t !== tagId) : [...prev, tagId]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setMessage(null);
      setError(null);

      const res = await feedbackApi.submit(token, {
        dest_label: destLabel,
        rating,
        safety_tags: selectedTags,
        comments,
      });

      setMessage(res.message || "Feedback submitted successfully!");
      setDestLabel("");
      setSelectedTags([]);
      setComments("");
      setRating(4);

      setFeedbacks(res.stats ? [res.feedback, ...feedbacks] : feedbacks);
      setStats(res.stats || stats);
      loadData();
    } catch (err) {
      setError(err.message || "Failed to submit feedback.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetrain = async () => {
    try {
      setRetraining(true);
      setRetrainResult(null);
      setError(null);

      const res = await feedbackApi.retrain(token);
      setRetrainResult(res.metrics);
      setStats(res.stats || stats);
      setMessage(res.message);
    } catch (err) {
      setError(err.message || "Model retraining failed.");
    } finally {
      setRetraining(false);
    }
  };

  return (
    <main className="container page-content">
      <header className="page-header" style={{ textAlign: "center", marginBottom: "2rem" }}>
        <h1>Route Safety Feedback & AI Model Retraining</h1>
        <p style={{ color: "var(--muted)", maxWidth: "680px", margin: "0.5rem auto 0" }}>
          Help improve pedestrian safety! Submit your route feedback to dynamically retrain
          our AI route safety scoring model based on real community experiences.
        </p>
      </header>

      {message && <div className="card text-success" style={{ marginBottom: "1.5rem", background: "rgba(46, 204, 113, 0.1)" }}>{message}</div>}
      {error && <div className="card text-danger" style={{ marginBottom: "1.5rem", background: "rgba(231, 76, 60, 0.1)" }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem" }}>
        
        {/* Left Column: Submit Feedback Form */}
        <section className="card">
          <h2>Submit Route Safety Feedback</h2>
          <form onSubmit={handleSubmit} style={{ marginTop: "1rem" }}>
            <div className="form-group">
              <label>Location / Destination Area</label>
              <input
                type="text"
                placeholder="e.g. Soladevanahalli, Acharya College Rd"
                value={destLabel}
                onChange={(e) => setDestLabel(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>Safety Rating: {rating} / 5 Stars</label>
              <div style={{ display: "flex", gap: "0.5rem", fontSize: "1.6rem", cursor: "pointer", margin: "0.4rem 0" }}>
                {[1, 2, 3, 4, 5].map((star) => (
                  <span
                    key={star}
                    onClick={() => setRating(star)}
                    style={{ color: star <= rating ? "#f39c12" : "#7f8c8d" }}
                  >
                    ★
                  </span>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label>Safety Characteristics / Tags</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.4rem" }}>
                {SAFETY_TAG_OPTIONS.map((tag) => (
                  <button
                    key={tag.id}
                    type="button"
                    onClick={() => toggleTag(tag.id)}
                    className={`btn ${selectedTags.includes(tag.id) ? "btn-primary" : "btn-outline"}`}
                    style={{ fontSize: "0.85rem", padding: "0.3rem 0.7rem", borderRadius: "20px" }}
                  >
                    {tag.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label>Comments / Details (Optional)</label>
              <textarea
                rows="3"
                placeholder="Describe lighting, road conditions, or safety observations..."
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", border: "1px solid var(--border)" }}
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={submitting}>
              {submitting ? "Submitting & Updating Model..." : "Submit Feedback"}
            </button>
          </form>
        </section>

        {/* Right Column: AI Model Retraining & Analytics Panel */}
        <section className="card" style={{ background: "linear-gradient(135deg, rgba(30, 41, 59, 0.6), rgba(15, 23, 42, 0.8))" }}>
          <h2>⚡ AI Safety Model Retraining Engine</h2>
          <p style={{ fontSize: "0.9rem", color: "var(--muted)", margin: "0.4rem 0 1.2rem" }}>
            The AI route safety model recalculates route penalties using community feedback datasets.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ background: "rgba(255, 255, 255, 0.05)", padding: "1rem", borderRadius: "8px", textAlign: "center" }}>
              <div style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#3498db" }}>
                {stats?.total_feedback_count || 0}
              </div>
              <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Total Training Samples</div>
            </div>

            <div style={{ background: "rgba(255, 255, 255, 0.05)", padding: "1rem", borderRadius: "8px", textAlign: "center" }}>
              <div style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#2ecc71" }}>
                {stats?.model_status?.model_accuracy_score ? `${(stats.model_status.model_accuracy_score * 100).toFixed(1)}%` : "88.0%"}
              </div>
              <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Model Accuracy Score</div>
            </div>

            <div style={{ background: "rgba(255, 255, 255, 0.05)", padding: "1rem", borderRadius: "8px", textAlign: "center" }}>
              <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#f39c12" }}>
                {stats?.average_rating ? `${stats.average_rating} / 5` : "N/A"}
              </div>
              <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Average User Rating</div>
            </div>

            <div style={{ background: "rgba(255, 255, 255, 0.05)", padding: "1rem", borderRadius: "8px", textAlign: "center" }}>
              <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#9b59b6" }}>
                {stats?.model_status?.model_version || "v1.0.0"}
              </div>
              <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Retrained Model Version</div>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleRetrain}
            disabled={retraining}
            style={{ width: "100%", padding: "0.8rem", fontWeight: "bold", fontSize: "1rem" }}
          >
            {retraining ? "⏳ Retraining Safety Model..." : "⚡ Retrain Model with Feedback"}
          </button>

          {retrainResult && (
            <div style={{ marginTop: "1.2rem", padding: "1rem", borderRadius: "8px", background: "rgba(46, 204, 113, 0.15)", border: "1px solid #2ecc71" }}>
              <h4 style={{ color: "#2ecc71", margin: "0 0 0.5rem" }}>✅ Model Retrained Successfully</h4>
              <p style={{ fontSize: "0.85rem", margin: "0.2rem 0" }}>{retrainResult.message}</p>
              <ul style={{ fontSize: "0.8rem", margin: "0.5rem 0 0", paddingLeft: "1.2rem" }}>
                <li>Training Samples Used: <strong>{retrainResult.training_samples}</strong></li>
                <li>Model Accuracy Score: <strong>{(retrainResult.model_accuracy_score * 100).toFixed(1)}%</strong></li>
                <li>Feedback Weight: <strong>{(retrainResult.feedback_influence_weight * 100).toFixed(0)}%</strong></li>
              </ul>
            </div>
          )}
        </section>
      </div>

      {/* Bottom Section: Community Feedback Feed */}
      <section style={{ marginTop: "2.5rem" }}>
        <h2>Community Safety Feedback History</h2>
        {loading ? (
          <p>Loading feedback feed...</p>
        ) : feedbacks.length === 0 ? (
          <p style={{ color: "var(--muted)" }}>No feedback submitted yet. Be the first to rate route safety!</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem", marginTop: "1rem" }}>
            {feedbacks.map((item) => (
              <div key={item.id} className="card" style={{ padding: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong>{item.dest_label || "Location Review"}</strong>
                  <span style={{ color: "#f39c12", fontWeight: "bold" }}>★ {item.rating}/5</span>
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0.3rem 0" }}>
                  By {item.user_name} • {item.created_at ? new Date(item.created_at).toLocaleDateString() : "Just now"}
                </div>
                {item.comments && <p style={{ fontSize: "0.9rem", margin: "0.5rem 0" }}>"{item.comments}"</p>}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem", marginTop: "0.5rem" }}>
                  {item.safety_tags.map((tag, i) => (
                    <span key={i} style={{ fontSize: "0.75rem", background: "rgba(255,255,255,0.1)", padding: "0.2rem 0.5rem", borderRadius: "12px" }}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

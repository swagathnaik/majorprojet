import { useState } from "react";
import { feedbackApi } from "../api/client";

const SAFETY_TAG_OPTIONS = [
  { id: "poor_lighting", label: "💡 Poor Lighting" },
  { id: "unsafe_area", label: "⚠️ Unsafe Area" },
  { id: "isolated_street", label: "🚶 Isolated Street" },
  { id: "suspicious_activity", label: "🚨 Suspicious Activity" },
  { id: "well_lit", label: "🛡️ Well Lit & Safe" },
];

export default function PostJourneyFeedbackModal({ isOpen, onClose, journey, token }) {
  const [rating, setRating] = useState(5);
  const [selectedTags, setSelectedTags] = useState([]);
  const [comments, setComments] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const toggleTag = (tagId) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((t) => t !== tagId) : [...prev, tagId]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);

      const destLabel = journey?.dest_label || "Completed Journey Route";
      const lat = journey?.dest_lat || journey?.last_lat || 12.9716;
      const lng = journey?.dest_lng || journey?.last_lng || 77.5946;

      await feedbackApi.submit(token, {
        journey_id: journey?.id,
        dest_label: destLabel,
        lat,
        lng,
        rating,
        safety_tags: selectedTags,
        comments,
      });

      // Automatically trigger AI model retraining
      await feedbackApi.retrain(token);

      setSubmitted(true);
      setTimeout(() => {
        onClose();
      }, 1800);
    } catch (err) {
      setError(err.message || "Failed to submit feedback.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="post-journey-feedback-backdrop">
      <div className="post-journey-feedback-card">

        {submitted ? (
          <div style={{ textAlign: "center", padding: "1.5rem 0" }}>
            <div style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>🎉</div>
            <h3 style={{ color: "#2ecc71", margin: "0 0 0.5rem" }}>Thank You for Your Feedback!</h3>
            <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
              Our AI Safety Model has been retrained with your route observations.
            </p>
          </div>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.25rem", color: "var(--fg)" }}>
                🏁 Journey Ended — Rate Route Safety
              </h3>
              <button
                type="button"
                className="btn-ghost"
                onClick={onClose}
                style={{ fontSize: "1.2rem", cursor: "pointer", border: "none", background: "none", color: "var(--muted)" }}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: "0.88rem", color: "var(--muted)", marginBottom: "1.2rem" }}>
              How safe was your route to <strong>{journey?.dest_label || "your destination"}</strong>?
            </p>

            {error && (
              <div className="text-danger" style={{ marginBottom: "1rem", fontSize: "0.85rem", background: "rgba(231,76,60,0.1)", padding: "0.5rem", borderRadius: "6px" }}>
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div style={{ textAlign: "center", marginBottom: "1.2rem" }}>
                <label style={{ fontSize: "0.9rem", fontWeight: "bold", display: "block", marginBottom: "0.4rem" }}>
                  Overall Safety Rating: {rating} / 5
                </label>
                <div style={{ display: "flex", justifyContent: "center", gap: "0.6rem", fontSize: "2rem", cursor: "pointer" }}>
                  {[1, 2, 3, 4, 5].map((star) => (
                    <span
                      key={star}
                      onClick={() => setRating(star)}
                      style={{ color: star <= rating ? "#f39c12" : "#4a5568", transition: "color 0.15s ease" }}
                    >
                      ★
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ marginBottom: "1.2rem" }}>
                <label style={{ fontSize: "0.85rem", fontWeight: "bold", display: "block", marginBottom: "0.4rem" }}>
                  Select Route Observations (Optional)
                </label>
                <div className="tag-chips-container">
                  {SAFETY_TAG_OPTIONS.map((tag) => {
                    const isSelected = selectedTags.includes(tag.id);
                    return (
                      <button
                        key={tag.id}
                        type="button"
                        onClick={() => toggleTag(tag.id)}
                        className={`tag-chip ${isSelected ? "active" : ""}`}
                        aria-pressed={isSelected}
                      >
                        <span>{tag.label}</span>
                        {isSelected && <span style={{ marginLeft: "0.2rem", fontWeight: "bold" }}>✓</span>}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div style={{ marginBottom: "1.2rem" }}>
                <label style={{ fontSize: "0.85rem", fontWeight: "bold", display: "block", marginBottom: "0.4rem" }}>
                  Comments / Notes (Optional)
                </label>
                <textarea
                  rows="2"
                  placeholder="e.g. Well lit main road, dark alley near station..."
                  value={comments}
                  onChange={(e) => setComments(e.target.value)}
                  style={{ width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--border)", background: "var(--bg)", color: "var(--fg)" }}
                />
              </div>

              <div style={{ display: "flex", gap: "0.6rem" }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ flex: 1, fontWeight: "bold" }}
                  disabled={submitting}
                >
                  {submitting ? "Submitting..." : "Submit Feedback"}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={onClose}
                  disabled={submitting}
                >
                  Skip
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

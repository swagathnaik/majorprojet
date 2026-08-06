import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { contactsApi } from "../api/client";

const RELATIONSHIPS = [
  "Mother",
  "Father",
  "Sibling",
  "Friend",
  "Spouse",
  "Guardian",
  "Other",
];

const EMPTY_FORM = {
  name: "",
  phone: "",
  relationship: "Friend",
  is_primary: false,
};

/**
 * Emergency contact management – Phase 3.
 */
export default function Contacts() {
  const { token } = useAuth();
  const [contacts, setContacts] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadContacts = useCallback(async () => {
    setError("");
    try {
      const data = await contactsApi.list(token);
      setContacts(data.contacts || []);
    } catch (err) {
      setError(err.message || "Failed to load contacts.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  function onChange(e) {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  function startEdit(contact) {
    setEditingId(contact.id);
    setForm({
      name: contact.name,
      phone: contact.phone,
      relationship: contact.relationship || "Other",
      is_primary: contact.is_primary,
    });
    setMessage("");
    setError("");
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  async function onSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      if (editingId) {
        await contactsApi.update(token, editingId, form);
        setMessage("Contact updated.");
      } else {
        await contactsApi.create(token, form);
        setMessage("Contact added.");
      }
      cancelEdit();
      await loadContacts();
    } catch (err) {
      setError(err.message || "Could not save contact.");
    } finally {
      setSaving(false);
    }
  }

  async function makePrimary(id) {
    setError("");
    setMessage("");
    try {
      await contactsApi.setPrimary(token, id);
      setMessage("Primary contact updated.");
      await loadContacts();
    } catch (err) {
      setError(err.message || "Could not set primary.");
    }
  }

  async function removeContact(id, name) {
    const ok = window.confirm(`Delete emergency contact "${name}"?`);
    if (!ok) return;
    setError("");
    setMessage("");
    try {
      await contactsApi.remove(token, id);
      if (editingId === id) cancelEdit();
      setMessage("Contact deleted.");
      await loadContacts();
    } catch (err) {
      setError(err.message || "Could not delete contact.");
    }
  }

  return (
    <main className="page contacts-page">
      <section className="panel contacts-panel">
        <h1>Emergency contacts</h1>
        <p className="muted">
          Add trusted people who should be alerted if SafeRoute escalates an SOS.
          One contact can be marked as primary.
        </p>

        {error && <div className="alert alert-error">{error}</div>}
        {message && <div className="alert alert-success">{message}</div>}

        <form className="contact-form" onSubmit={onSubmit}>
          <h2>{editingId ? "Edit contact" : "Add contact"}</h2>

          <div className="form-row">
            <label>
              Name
              <input
                name="name"
                value={form.name}
                onChange={onChange}
                required
                placeholder="e.g. Priya"
              />
            </label>
            <label>
              Phone
              <input
                name="phone"
                value={form.phone}
                onChange={onChange}
                required
                placeholder="e.g. 9876543210"
              />
            </label>
          </div>

          <div className="form-row">
            <label>
              Relationship
              <select
                name="relationship"
                value={form.relationship}
                onChange={onChange}
              >
                {RELATIONSHIPS.map((rel) => (
                  <option key={rel} value={rel}>
                    {rel}
                  </option>
                ))}
              </select>
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="is_primary"
                checked={form.is_primary}
                onChange={onChange}
              />
              Set as primary contact
            </label>
          </div>

          <div className="form-actions">
            <button className="btn" type="submit" disabled={saving}>
              {saving ? "Saving…" : editingId ? "Save changes" : "Add contact"}
            </button>
            {editingId && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={cancelEdit}
              >
                Cancel
              </button>
            )}
          </div>
        </form>

        <div className="contacts-list-wrap">
          <h2>Your contacts</h2>
          {loading ? (
            <p className="muted">Loading…</p>
          ) : contacts.length === 0 ? (
            <p className="muted empty-hint">
              No contacts yet. Add at least one before starting a Safe Journey.
            </p>
          ) : (
            <ul className="contacts-list">
              {contacts.map((c) => (
                <li key={c.id} className="contact-item">
                  <div className="contact-main">
                    <div className="contact-title-row">
                      <strong>{c.name}</strong>
                      {c.is_primary && (
                        <span className="badge badge-primary">Primary</span>
                      )}
                    </div>
                    <p className="contact-meta">
                      {c.relationship || "Other"} · {c.phone}
                    </p>
                  </div>
                  <div className="contact-actions">
                    {!c.is_primary && (
                      <button
                        type="button"
                        className="link-btn"
                        onClick={() => makePrimary(c.id)}
                      >
                        Make primary
                      </button>
                    )}
                    <button
                      type="button"
                      className="link-btn"
                      onClick={() => startEdit(c)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="link-btn danger"
                      onClick={() => removeContact(c.id, c.name)}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}

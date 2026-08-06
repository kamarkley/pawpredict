import { useState } from "react";

import { updateDog } from "../services/api";
import type { Dog } from "../types/dog";

interface Props { dog: Dog; onDogUpdated: (dog: Dog) => void; }

export function DogProfile({ dog, onDogUpdated }: Props) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    name: dog.name,
    birth_date: dog.birth_date,
    breed: dog.breed ?? "",
    sex: dog.sex,
    weight_lbs: dog.weight_lbs ?? "",
    neutered: dog.neutered === null ? "UNKNOWN" : dog.neutered ? "YES" : "NO",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true); setError(null);
    try {
      const updated = await updateDog(dog.id, {
        name: form.name.trim(), birth_date: form.birth_date,
        breed: form.breed.trim() || null, sex: form.sex as Dog["sex"],
        weight_lbs: form.weight_lbs ? Number(form.weight_lbs) : null,
        neutered: form.neutered === "UNKNOWN" ? null : form.neutered === "YES",
      });
      onDogUpdated(updated); setEditing(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update profile."); }
    finally { setSaving(false); }
  }

  return (
    <section className="dog-profile-card">
      <div className="section-heading"><div><p className="eyebrow">Dog profile</p><h1>{dog.name}</h1></div><button className="secondary-button" type="button" onClick={() => setEditing(!editing)}>{editing ? "Cancel" : "Edit profile"}</button></div>
      {!editing ? (
        <div className="profile-grid">
          <div><span>Breed</span><strong>{dog.breed ?? "Not set"}</strong></div>
          <div><span>Age</span><strong>{dog.age_in_weeks} weeks</strong></div>
          <div><span>Weight</span><strong>{dog.weight_lbs ? `${dog.weight_lbs} lb` : "Not set"}</strong></div>
          <div><span>Neutered</span><strong>{dog.neutered === null ? "Unknown" : dog.neutered ? "Yes" : "No"}</strong></div>
        </div>
      ) : (
        <div className="profile-edit-form">
          {error && <p className="event-error">{error}</p>}
          <label className="field-label">Name<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
          <label className="field-label">Birth date<input type="date" value={form.birth_date} onChange={(event) => setForm({ ...form, birth_date: event.target.value })} /></label>
          <label className="field-label">Breed<input value={form.breed} onChange={(event) => setForm({ ...form, breed: event.target.value })} /></label>
          <label className="field-label">Sex<select value={form.sex} onChange={(event) => setForm({ ...form, sex: event.target.value as Dog["sex"] })}><option value="MALE">Male</option><option value="FEMALE">Female</option><option value="UNKNOWN">Unknown</option></select></label>
          <label className="field-label">Weight (lb)<input type="number" min="0" step="0.1" value={form.weight_lbs} onChange={(event) => setForm({ ...form, weight_lbs: event.target.value })} /></label>
          <label className="field-label">Neutered<select value={form.neutered} onChange={(event) => setForm({ ...form, neutered: event.target.value })}><option value="UNKNOWN">Unknown</option><option value="YES">Yes</option><option value="NO">No</option></select></label>
          <button className="save-button full-width" disabled={saving} type="button" onClick={() => void save()}>{saving ? "Saving…" : "Save profile"}</button>
        </div>
      )}
    </section>
  );
}

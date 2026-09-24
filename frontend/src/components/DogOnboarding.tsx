import { useState } from "react";

import { createDog } from "../services/api";
import type { Dog, DogSex } from "../types/dog";

interface Props {
  onCreated: (dog: Dog) => void;
  onCancel?: () => void;
}

export function DogOnboarding({ onCreated, onCancel }: Props) {
  const [name, setName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [breed, setBreed] = useState("");
  const [sex, setSex] = useState<DogSex>("UNKNOWN");
  const [weight, setWeight] = useState("");
  const [neutered, setNeutered] = useState<"UNKNOWN" | "YES" | "NO">("UNKNOWN");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || !birthDate) return;
    setBusy(true);
    setError(null);
    try {
      const dog = await createDog({
        name: name.trim(),
        birth_date: birthDate,
        breed: breed.trim() || null,
        sex,
        weight_lbs: weight ? Number(weight) : null,
        neutered: neutered === "UNKNOWN" ? null : neutered === "YES",
      });
      onCreated(dog);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create dog profile.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="onboarding-card">
      <div><p className="eyebrow">New dog</p><h1>Set up a PawPredict profile</h1><p>Start with the basics. Tracking preferences can be changed later.</p></div>
      {error && <p className="event-error">{error}</p>}
      <form onSubmit={(event) => void submit(event)}>
        <div className="profile-form-grid">
          <label className="field-label">Name<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
          <label className="field-label">Birth date<input type="date" max={new Date().toISOString().slice(0, 10)} value={birthDate} onChange={(event) => setBirthDate(event.target.value)} required /></label>
          <label className="field-label">Breed <span>Optional</span><input value={breed} onChange={(event) => setBreed(event.target.value)} /></label>
          <label className="field-label">Sex<select value={sex} onChange={(event) => setSex(event.target.value as DogSex)}><option value="UNKNOWN">Unknown</option><option value="MALE">Male</option><option value="FEMALE">Female</option></select></label>
          <label className="field-label">Weight (lb) <span>Optional</span><input type="number" min="0.1" step="0.1" value={weight} onChange={(event) => setWeight(event.target.value)} /></label>
          <label className="field-label">Neutered / spayed<select value={neutered} onChange={(event) => setNeutered(event.target.value as "UNKNOWN" | "YES" | "NO")}><option value="UNKNOWN">Unknown / not set</option><option value="YES">Yes</option><option value="NO">No</option></select></label>
        </div>
        <div className="form-actions">
          {onCancel && <button className="cancel-button" type="button" onClick={onCancel}>Cancel</button>}
          <button className="save-button" disabled={busy || !name.trim() || !birthDate} type="submit">{busy ? "Creating…" : "Create dog profile"}</button>
        </div>
      </form>
    </section>
  );
}

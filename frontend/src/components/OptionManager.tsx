import { useState } from "react";

import { createSavedOption, updateSavedOption } from "../services/api";
import type { SavedOption } from "../types/event";

const MANAGEABLE = ["TREAT", "SLEEP_LOCATION", "MEAL_AMOUNT", "MEDICATION", "SYMPTOM", "SOCIAL_ACTIVITY", "BEHAVIOR"];
interface Props { dogId: string; options: SavedOption[]; onOptionsChanged: () => void; }

export function OptionManager({ dogId, options, onOptionsChanged }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [category, setCategory] = useState("TREAT");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function add() {
    if (!name.trim()) return;
    try { await createSavedOption(dogId, category, name.trim()); setName(""); onOptionsChanged(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not add option."); }
  }

  async function deactivate(option: SavedOption) {
    try { await updateSavedOption(option.id, { is_active: false }); onOptionsChanged(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not remove option."); }
  }

  return (
    <section className="settings-card">
      <button className="manual-log-toggle" type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}><span><span className="eyebrow">Reusable choices</span><strong>Manage saved options</strong></span><span>{expanded ? "−" : "+"}</span></button>
      {expanded && <div className="settings-body">{error && <p className="event-error">{error}</p>}<label className="field-label">Option type<select value={category} onChange={(event) => setCategory(event.target.value)}>{MANAGEABLE.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ").toLowerCase()}</option>)}</select></label><div className="inline-create"><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Add a reusable option" /><button type="button" onClick={() => void add()}>Add</button></div><div className="option-chip-list">{options.filter((option) => option.category === category && option.is_active).map((option) => <span className="option-chip" key={option.id}>{option.name}<button type="button" aria-label={`Remove ${option.name}`} onClick={() => void deactivate(option)}>×</button></span>)}</div></div>}
    </section>
  );
}

import { useState } from "react";

import { createEvent } from "../services/api";
import type { EventType, SavedOption } from "../types/event";
import { EventFields, type EventFieldValues } from "./EventFields";

const ICONS: Record<string, string> = {
  PEE: "💧", POOP: "💩", POTTY_ATTEMPT: "🚪", MEAL: "🍽️", WATER: "🥤",
  TREAT: "🦴", SLEEP: "😴", SLEEP_NIGHT: "🌙", PLAY: "🎾", TRAINING: "⭐",
  ZOOMIES: "⚡", BATH: "🛁", MEDICATION: "💊", WALK: "🦮", SYMPTOM: "🩺", SOCIAL: "🐕",
  BEHAVIOR: "🧠", GROOMING: "🛁", VET_VISIT: "🏥",
};

const EMPTY: EventFieldValues = { state: null, optionId: "", numericValue: "", unit: "", severity: "", notes: "" };

interface Props {
  dogId: string;
  dogName: string;
  eventTypes: EventType[];
  options: SavedOption[];
  onOptionCreated: (option: SavedOption) => void;
  onEventSaved: () => void;
}

export function EventLogger({ dogId, dogName, eventTypes, options, onOptionCreated, onEventSaved }: Props) {
  const [selected, setSelected] = useState<EventType | null>(null);
  const [values, setValues] = useState<EventFieldValues>(EMPTY);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function valid() {
    if (!selected) return false;
    if (selected.supports_state && !values.state) return false;
    if (selected.option_required && !values.optionId) return false;
    if (selected.numeric_required && !values.numericValue) return false;
    if (selected.severity_required && !values.severity) return false;
    if (values.numericValue && selected.allowed_units.length > 0 && !values.unit) return false;
    return true;
  }

  async function save() {
    if (!selected || !valid()) return;
    setIsSaving(true); setError(null); setMessage(null);
    try {
      await createEvent({
        dog_id: dogId, event_type_id: selected.id, state: values.state,
        location: "NOT_APPLICABLE", option_id: values.optionId || null,
        numeric_value: values.numericValue ? Number(values.numericValue) : null,
        unit: values.numericValue ? values.unit || null : null,
        severity: values.severity ? Number(values.severity) : null,
        notes: values.notes.trim() || null, entry_method: "QUICK_LOG",
      });
      setMessage(`${selected.display_name} logged.`);
      setSelected(null); setValues(EMPTY); onEventSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save event.");
    } finally { setIsSaving(false); }
  }

  return (
    <section className="event-logger">
      <div className="section-heading"><div><p className="eyebrow">Quick log</p><h2>What did {dogName} do?</h2></div></div>
      {message && <p className="success-message">{message}</p>}
      {error && <p className="event-error">{error}</p>}
      <div className="event-button-grid">
        {eventTypes.map((type) => (
          <button className="event-button" key={type.id} type="button" onClick={() => { setSelected(type); setValues(EMPTY); }}>
            <span className="event-icon">{ICONS[type.code] ?? "🐾"}</span><span>{type.display_name}</span>
          </button>
        ))}
      </div>
      {selected && (
        <div className="event-selection">
          <p>Logging: <strong>{selected.display_name}</strong></p>
          <EventFields dogId={dogId} eventType={selected} options={options} values={values} onChange={setValues} onOptionCreated={onOptionCreated} />
          <div className="form-actions">
            <button className="cancel-button" type="button" onClick={() => setSelected(null)}>Cancel</button>
            <button className="save-button" disabled={!valid() || isSaving} type="button" onClick={() => void save()}>{isSaving ? "Saving…" : "Save event"}</button>
          </div>
        </div>
      )}
    </section>
  );
}

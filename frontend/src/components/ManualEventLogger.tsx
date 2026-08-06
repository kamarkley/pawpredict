import { useState } from "react";

import { createEvent } from "../services/api";
import type { EventType, SavedOption } from "../types/event";
import { getCurrentLocalDateTime } from "../utils/date";
import { EventFields, type EventFieldValues } from "./EventFields";

const EMPTY: EventFieldValues = { state: null, optionId: "", numericValue: "", unit: "", severity: "", notes: "" };
function localNow() { return getCurrentLocalDateTime(); }

interface Props {
  dogId: string;
  dogName: string;
  eventTypes: EventType[];
  options: SavedOption[];
  onOptionCreated: (option: SavedOption) => void;
  onEventSaved: () => void;
}

export function ManualEventLogger({ dogId, dogName, eventTypes, options, onOptionCreated, onEventSaved }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [eventTypeId, setEventTypeId] = useState("");
  const [dateTime, setDateTime] = useState(localNow());
  const [values, setValues] = useState<EventFieldValues>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selected = eventTypes.find((type) => type.id === Number(eventTypeId)) ?? null;

  function valid() {
    if (!selected || !dateTime) return false;
    if (new Date(dateTime) > new Date()) return false;

    if (selected.supports_state && !values.state) return false;
     if (selected.option_required && !values.optionId) return false;
     if (selected.numeric_required && !values.numericValue) return false;
     if (selected.severity_required && !values.severity) return false;

     if (
       values.numericValue &&
       selected.allowed_units.length > 0 &&
       !values.unit
     ) {
       return false;
     }

     return true;
    }

  async function save() {
    if (!selected || !valid()) return;
    setSaving(true); setError(null); setMessage(null);
    try {
      await createEvent({
        dog_id: dogId, event_type_id: selected.id, event_time: new Date(dateTime).toISOString(),
        state: values.state, location: "NOT_APPLICABLE", option_id: values.optionId || null,
        numeric_value: values.numericValue ? Number(values.numericValue) : null,
        unit: values.numericValue ? values.unit || null : null,
        severity: values.severity ? Number(values.severity) : null,
        notes: values.notes.trim() || null, entry_method: "MANUAL",
      });
      setMessage(`${selected.display_name} added to ${dogName}’s timeline.`);
      setEventTypeId(""); setDateTime(localNow()); setValues(EMPTY); onEventSaved();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save event."); }
    finally { setSaving(false); }
  }

  return (
    <section className="manual-log-card">
      <button className="manual-log-toggle" type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
        <span><span className="eyebrow">Backfill an event</span><strong>Add a manual log</strong></span><span>{expanded ? "−" : "+"}</span>
      </button>
      {expanded && <div className="manual-log-form">
        {message && <p className="success-message">{message}</p>}{error && <p className="event-error">{error}</p>}
        <label className="field-label">Event type<select value={eventTypeId} onChange={(event) => { setEventTypeId(event.target.value); setValues(EMPTY); }}><option value="">Choose an event</option>{eventTypes.map((type) => <option key={type.id} value={type.id}>{type.display_name}</option>)}</select></label>
        <label className="field-label">
          Date and time
          <input
            type="datetime-local"
            value={dateTime}
            max={localNow()}
            onChange={(event) => setDateTime(event.target.value)}
          />
        </label>
        {selected && <EventFields dogId={dogId} eventType={selected} options={options} values={values} onChange={setValues} onOptionCreated={onOptionCreated} />}
        <div className="form-actions"><button className="cancel-button" type="button" onClick={() => { setEventTypeId(""); setValues(EMPTY); }}>Clear</button><button className="save-button" disabled={!valid() || saving} type="button" onClick={() => void save()}>{saving ? "Saving…" : "Add to timeline"}</button></div>
      </div>}
    </section>
  );
}

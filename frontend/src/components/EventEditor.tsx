import { useState } from "react";

import { deleteEvent, updateEvent } from "../services/api";
import type {
  EventLocation,
  EventType,
  LoggedEvent,
  SavedOption,
} from "../types/event";
import { getCurrentLocalDateTime } from "../utils/date";
import { EventFields, type EventFieldValues } from "./EventFields";

interface Props {
  dogId: string;
  event: LoggedEvent;
  eventType: EventType;
  options: SavedOption[];
  onOptionCreated: (option: SavedOption) => void;
  onSaved: (event: LoggedEvent) => void;
  onDeleted: (eventId: string) => void;
  onCancel: () => void;
}

function localDateTime(value: string): string {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

function initialValues(event: LoggedEvent): EventFieldValues {
  return {
    state: event.state,
    optionId: event.option_id ?? "",
    numericValue: event.numeric_value ? String(Number(event.numeric_value)) : "",
    unit: event.unit ?? "",
    severity: event.severity ? String(event.severity) : "",
    notes: event.notes ?? "",
  };
}

export function EventEditor({
  dogId,
  event,
  eventType,
  options,
  onOptionCreated,
  onSaved,
  onDeleted,
  onCancel,
}: Props) {
  const [dateTime, setDateTime] = useState(() => localDateTime(event.event_time));
  const [location, setLocation] = useState<EventLocation>(event.location);
  const [values, setValues] = useState<EventFieldValues>(() => initialValues(event));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);


  function valid(): boolean {
    if (!dateTime || new Date(dateTime) > new Date()) return false;
    if (eventType.supports_state && !values.state) return false;
    if (eventType.supports_location && location === "NOT_APPLICABLE") return false;
    if (eventType.option_required && !values.optionId) return false;
    if (eventType.numeric_required && !values.numericValue) return false;
    if (eventType.severity_required && !values.severity) return false;
    if (values.numericValue && eventType.allowed_units.length > 0 && !values.unit) return false;
    return true;
  }

  async function save() {
    if (!valid()) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateEvent(event.id, {
        event_time: new Date(dateTime).toISOString(),
        state: values.state,
        location: eventType.supports_location ? location : event.location,
        option_id: values.optionId || null,
        numeric_value: values.numericValue ? Number(values.numericValue) : null,
        unit: values.numericValue ? values.unit || null : null,
        severity: values.severity ? Number(values.severity) : null,
        notes: values.notes.trim() || null,
      });
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update event.");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete the ${event.event_type_name} log?`)) return;
    setSaving(true);
    setError(null);
    try {
      await deleteEvent(event.id);
      onDeleted(event.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete event.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="edit-event-panel" role="dialog" aria-label={`Edit ${event.event_type_name}`}>
      <div className="edit-event-heading">
        <div><p className="eyebrow">Edit log</p><h3>{event.event_type_name}</h3></div>
        <button className="icon-button" type="button" aria-label="Close editor" onClick={onCancel}>×</button>
      </div>
      {error && <p className="event-error">{error}</p>}
      <label className="field-label">
        Date and time
        <input
          type="datetime-local"
          value={dateTime}
          max={getCurrentLocalDateTime()}
          onChange={(changeEvent) => setDateTime(changeEvent.target.value)}
        />
      </label>
      {eventType.supports_location && (
        <fieldset>
          <legend>Location</legend>
          <div className="option-row">
            <button
              className={location === "OUTSIDE" ? "selected-option" : ""}
              type="button"
              onClick={() => setLocation("OUTSIDE")}
            >Outside</button>
            <button
              className={location === "INSIDE" ? "selected-option" : ""}
              type="button"
              onClick={() => setLocation("INSIDE")}
            >Inside</button>
          </div>
        </fieldset>
      )}
      <EventFields
        dogId={dogId}
        eventType={eventType}
        options={options}
        values={values}
        onChange={setValues}
        onOptionCreated={onOptionCreated}
      />
      <div className="form-actions split-actions">
        <button className="delete-button" disabled={saving} type="button" onClick={() => void remove()}>Delete log</button>
        <div>
          <button className="cancel-button" disabled={saving} type="button" onClick={onCancel}>Cancel</button>
          <button className="save-button" disabled={!valid() || saving} type="button" onClick={() => void save()}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

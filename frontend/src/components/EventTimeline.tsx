import { useEffect, useState } from "react";

import { deleteEvent, getEvents, updateEvent } from "../services/api";
import type { EventType, LoggedEvent, SavedOption } from "../types/event";
import { getLocalDayRange } from "../utils/date";
import { EventFields, type EventFieldValues } from "./EventFields";

const ICONS: Record<string, string> = {
  PEE: "💧", POOP: "💩", POTTY_ATTEMPT: "🚪", MEAL: "🍽️", WATER: "🥤",
  TREAT: "🦴", SLEEP: "😴", SLEEP_NIGHT: "🌙", PLAY: "🎾", TRAINING: "⭐",
  ZOOMIES: "⚡", MEDICATION: "💊", WALK: "🦮", SYMPTOM: "🩺", SOCIAL: "🐕",
  BEHAVIOR: "🧠", GROOMING: "🛁", VET_VISIT: "🏥",
};

interface Props {
  dogId: string;
  refreshKey: number;
  eventTypes: EventType[];
  options: SavedOption[];
  onOptionCreated: (option: SavedOption) => void;
  onTimelineChanged: () => void;
}

function details(event: LoggedEvent): string[] {
  const values: string[] = [];
  if (event.state) values.push(event.state === "START" ? "Start" : "End");
  if (event.option_name) values.push(event.option_name);
  if (event.numeric_value) values.push(`${Number(event.numeric_value)}${event.unit ? ` ${event.unit}` : ""}`);
  if (event.severity) values.push(`Severity ${event.severity}/10`);
  return values;
}

export function EventTimeline({ dogId, refreshKey, eventTypes, options, onOptionCreated, onTimelineChanged }: Props) {
  const [events, setEvents] = useState<LoggedEvent[]>([]);
  const [editing, setEditing] = useState<LoggedEvent | null>(null);
  const [editDateTime, setEditDateTime] = useState("");
  const [values, setValues] = useState<EventFieldValues>({ state: null, optionId: "", numericValue: "", unit: "", severity: "", notes: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true); setError(null);
      try {
        const { start, end } = getLocalDayRange();
        setEvents(await getEvents(dogId, start, end, controller.signal));
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      } finally { setLoading(false); }
    }
    void load();
    return () => controller.abort();
  }, [dogId, refreshKey]);

  const editingType = editing ? eventTypes.find((type) => type.id === editing.event_type_id) ?? null : null;

  function beginEdit(event: LoggedEvent) {
    const date = new Date(event.event_time);
    setEditDateTime(new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16));
    setValues({
      state: event.state,
      optionId: event.option_id ?? "",
      numericValue: event.numeric_value ? String(Number(event.numeric_value)) : "",
      unit: event.unit ?? "",
      severity: event.severity ? String(event.severity) : "",
      notes: event.notes ?? "",
    });
    setEditing(event); setError(null);
  }

  async function saveEdit() {
    if (!editing || !editingType || !editDateTime) return;
    setSaving(true); setError(null);
    try {
      await updateEvent(editing.id, {
        event_time: new Date(editDateTime).toISOString(),
        state: values.state,
        option_id: values.optionId || null,
        numeric_value: values.numericValue ? Number(values.numericValue) : null,
        unit: values.numericValue ? values.unit || null : null,
        severity: values.severity ? Number(values.severity) : null,
        notes: values.notes.trim() || null,
      });
      setEditing(null); onTimelineChanged();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update event."); }
    finally { setSaving(false); }
  }

  async function remove(event: LoggedEvent) {
    if (!window.confirm(`Delete the ${event.event_type_name} log?`)) return;
    try { await deleteEvent(event.id); if (editing?.id === event.id) setEditing(null); onTimelineChanged(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not delete event."); }
  }

  return (
    <section className="timeline-card">
      <div className="section-heading"><div><p className="eyebrow">Today</p><h2>Activity timeline</h2></div><span className="timeline-count">{events.length} {events.length === 1 ? "event" : "events"}</span></div>
      {loading && <p>Loading today’s activity…</p>}{error && <p className="event-error">{error}</p>}
      {!loading && !error && events.length === 0 && <div className="timeline-empty"><span>🐾</span><p>No events logged today.</p></div>}
      <ol className="timeline-list">
        {events.map((event) => (
          <li className="timeline-item" key={event.id}>
            <div className="timeline-icon">{ICONS[event.event_type_code] ?? "🐾"}</div>
            <div className="timeline-content">
              <div className="timeline-event-heading"><strong>{event.event_type_name}</strong><time>{new Date(event.event_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</time></div>
              {details(event).length > 0 && <p className="timeline-details">{details(event).join(" · ")}</p>}
              {event.notes && <p className="timeline-notes">{event.notes}</p>}
              <div className="timeline-actions"><button type="button" onClick={() => beginEdit(event)}>Edit</button><button className="delete-action" type="button" onClick={() => void remove(event)}>Delete</button></div>
            </div>
          </li>
        ))}
      </ol>
      {editing && editingType && (
        <div className="edit-event-panel">
          <p className="eyebrow">Edit log</p><h3>{editing.event_type_name}</h3>
          <label className="field-label">Date and time<input type="datetime-local" value={editDateTime} onChange={(event) => setEditDateTime(event.target.value)} /></label>
          <EventFields dogId={dogId} eventType={editingType} options={options} values={values} onChange={setValues} onOptionCreated={onOptionCreated} />
          <div className="form-actions"><button className="cancel-button" type="button" onClick={() => setEditing(null)}>Cancel</button><button className="save-button" disabled={saving} type="button" onClick={() => void saveEdit()}>{saving ? "Saving…" : "Save changes"}</button></div>
        </div>
      )}
    </section>
  );
}

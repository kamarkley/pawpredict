import { useEffect, useMemo, useState } from "react";

import { getEvents, getObservationPeriods } from "../services/api";
import type { EventType, LoggedEvent, SavedOption } from "../types/event";
import type { ObservationPeriod } from "../types/observation";
import { getLocalDayRange } from "../utils/date";
import { EventEditor } from "./EventEditor";

const ICONS: Record<string, string> = {
  PEE: "💧", POOP: "💩", POTTY_ATTEMPT: "🚪", MEAL: "🍽️", WATER: "🥤",
  TREAT: "🦴", SLEEP: "😴", SLEEP_NIGHT: "🌙", PLAY: "🎾", TRAINING: "⭐",
  ZOOMIES: "⚡", BATH: "🛁", MEDICATION: "💊", WALK: "🦮", SYMPTOM: "🩺", SOCIAL: "🐕",
  BEHAVIOR: "🧠", GROOMING: "🛁", VET_VISIT: "🏥",
};

interface Props {
  dogId: string;
  refreshKey: number;
  observationRefreshKey: number;
  eventTypes: EventType[];
  options: SavedOption[];
  onOptionCreated: (option: SavedOption) => void;
  onTimelineChanged: () => void;
}

type TimelineEntry =
  | { kind: "event"; time: string; event: LoggedEvent }
  | { kind: "observation"; time: string; period: ObservationPeriod };

function details(event: LoggedEvent): string[] {
  const values: string[] = [];
  if (event.state) values.push(event.state === "START" ? "Start" : "End");
  if (event.location !== "NOT_APPLICABLE") values.push(event.location === "OUTSIDE" ? "Outside" : "Inside");
  if (event.option_name) values.push(event.option_name);
  if (event.numeric_value) values.push(`${Number(event.numeric_value)}${event.unit ? ` ${event.unit}` : ""}`);
  if (event.severity) values.push(`Severity ${event.severity}/10`);
  return values;
}

function formatDuration(period: ObservationPeriod): string {
  if (!period.end_time) return "Active now";
  const minutes = Math.max(1, Math.round((new Date(period.end_time).getTime() - new Date(period.start_time).getTime()) / 60000));
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (!hours) return `${minutes} min`;
  return remainder ? `${hours} hr ${remainder} min` : `${hours} hr`;
}

export function EventTimeline({
  dogId,
  refreshKey,
  observationRefreshKey,
  eventTypes,
  options,
  onOptionCreated,
  onTimelineChanged,
}: Props) {
  const [events, setEvents] = useState<LoggedEvent[]>([]);
  const [periods, setPeriods] = useState<ObservationPeriod[]>([]);
  const [editing, setEditing] = useState<LoggedEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadEvents() {
      setLoading(true);
      setError(null);
      try {
        const { start, end } = getLocalDayRange();
        setEvents(await getEvents(dogId, start, end, controller.signal));
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void loadEvents();
    return () => controller.abort();
  }, [dogId, refreshKey]);

  useEffect(() => {
    const controller = new AbortController();
    async function loadPeriods() {
      try {
        const { start, end } = getLocalDayRange();
        setPeriods(await getObservationPeriods(dogId, start, end, false, controller.signal));
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      }
    }
    void loadPeriods();
    return () => controller.abort();
  }, [dogId, observationRefreshKey]);

  const timeline = useMemo<TimelineEntry[]>(() => [
    ...events.map((event): TimelineEntry => ({ kind: "event", time: event.event_time, event })),
    ...periods.map((period): TimelineEntry => ({ kind: "observation", time: period.start_time, period })),
  ].sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime()), [events, periods]);

  const editingType = editing ? eventTypes.find((type) => type.id === editing.event_type_id) ?? null : null;

  function saved(updated: LoggedEvent) {
    const { start, end } = getLocalDayRange();
    const timestamp = new Date(updated.event_time).getTime();
    const remainsToday = timestamp >= new Date(start).getTime() && timestamp < new Date(end).getTime();
    setEvents((current) => remainsToday
      ? current.map((event) => event.id === updated.id ? updated : event)
      : current.filter((event) => event.id !== updated.id));
    setEditing(null);
    onTimelineChanged();
  }

  function deleted(eventId: string) {
    setEvents((current) => current.filter((event) => event.id !== eventId));
    setEditing(null);
    onTimelineChanged();
  }

  return (
    <section className="timeline-card">
      <div className="section-heading">
        <div><p className="eyebrow">Today</p><h2>Activity timeline</h2></div>
        <span className="timeline-count">{timeline.length} {timeline.length === 1 ? "item" : "items"}</span>
      </div>
      {loading && <p>Loading today’s activity…</p>}
      {error && <p className="event-error">{error}</p>}
      {!loading && !error && timeline.length === 0 && <div className="timeline-empty"><span>🐾</span><p>No activity logged today.</p></div>}
      <ol className="timeline-list">
        {timeline.map((entry) => entry.kind === "event" ? (
          <li className="timeline-item" key={`event-${entry.event.id}`}>
            <div className="timeline-icon">{ICONS[entry.event.event_type_code] ?? "🐾"}</div>
            <div className="timeline-content">
              <div className="timeline-event-heading">
                <strong>{entry.event.event_type_name}</strong>
                <time>{new Date(entry.event.event_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</time>
              </div>
              {details(entry.event).length > 0 && <p className="timeline-details">{details(entry.event).join(" · ")}</p>}
              {entry.event.notes && <p className="timeline-notes">{entry.event.notes}</p>}
              <div className="timeline-actions"><button type="button" onClick={() => setEditing(entry.event)}>Edit</button></div>
            </div>
          </li>
        ) : (
          <li className="timeline-item observation-timeline-item" key={`observation-${entry.period.id}`}>
            <div className="timeline-icon">👁️‍🗨️</div>
            <div className="timeline-content">
              <div className="timeline-event-heading">
                <strong>Unobserved · {entry.period.reason_name ?? "Other"}</strong>
                <time>{new Date(entry.period.start_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</time>
              </div>
              <p className="timeline-details">{entry.period.end_time ? `Ended ${new Date(entry.period.end_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}` : "Still active"} · {formatDuration(entry.period)}</p>
              {entry.period.notes && <p className="timeline-notes">{entry.period.notes}</p>}
            </div>
          </li>
        ))}
      </ol>
      {editing && editingType && (
        <EventEditor
          key={editing.id}
          dogId={dogId}
          event={editing}
          eventType={editingType}
          options={options}
          onOptionCreated={onOptionCreated}
          onSaved={saved}
          onDeleted={deleted}
          onCancel={() => setEditing(null)}
        />
      )}
    </section>
  );
}

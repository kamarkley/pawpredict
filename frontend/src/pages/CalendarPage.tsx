import { useEffect, useMemo, useState } from "react";

import { DailyStatsDashboard } from "../components/DailyStatsDashboard";
import { EventEditor } from "../components/EventEditor";
import {
  createScheduledItem,
  deleteScheduledItem,
  getEvents,
  getObservationPeriods,
  getScheduledItems,
  updateScheduledItem,
} from "../services/api";
import type { EventType, LoggedEvent, SavedOption } from "../types/event";
import type { ObservationPeriod } from "../types/observation";
import type { ScheduledItem, ScheduledItemType } from "../types/schedule";

interface Props {
  dogId: string;
  dogName: string;
  refreshKey: number;
  eventTypes: EventType[];
  options: SavedOption[];
  onOptionCreated: (option: SavedOption) => void;
  onTimelineChanged: () => void;
}

const ITEM_LABELS: Record<ScheduledItemType, string> = {
  VET_APPOINTMENT: "Vet appointment",
  GROOMING_APPOINTMENT: "Grooming appointment",
  BATH: "Bath",
  MEDICATION: "Medication",
  DAYCARE: "Daycare",
  TRAINING: "Training",
  OTHER: "Other",
};

const ITEM_ICONS: Record<ScheduledItemType, string> = {
  VET_APPOINTMENT: "🏥", GROOMING_APPOINTMENT: "✂️", BATH: "🛁", MEDICATION: "💊",
  DAYCARE: "🐕", TRAINING: "⭐", OTHER: "📌",
};

function localKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function monthRange(month: Date) {
  const start = new Date(month.getFullYear(), month.getMonth(), 1);
  const end = new Date(month.getFullYear(), month.getMonth() + 1, 1);
  return { start: start.toISOString(), end: end.toISOString() };
}

function dateRange(key: string) {
  const start = new Date(`${key}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start: start.toISOString(), end: end.toISOString() };
}

function eventIcon(code: string) {
  return ({
    PEE: "💧", POOP: "💩", POTTY_ATTEMPT: "🚪", SLEEP: "😴", SLEEP_NIGHT: "🌙",
    WALK: "🦮", BATH: "🛁", VET_VISIT: "🏥", GROOMING: "✂️", ZOOMIES: "⚡", TREAT: "🦴",
  } as Record<string, string>)[code] ?? "🐾";
}

export function CalendarPage({
  dogId,
  dogName,
  refreshKey,
  eventTypes,
  options,
  onOptionCreated,
  onTimelineChanged,
}: Props) {
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [events, setEvents] = useState<LoggedEvent[]>([]);
  const [periods, setPeriods] = useState<ObservationPeriod[]>([]);
  const [scheduled, setScheduled] = useState<ScheduledItem[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [editingEvent, setEditingEvent] = useState<LoggedEvent | null>(null);
  const [localRefreshKey, setLocalRefreshKey] = useState(0);
  const [showAdd, setShowAdd] = useState(false);
  const [type, setType] = useState<ScheduledItemType>("VET_APPOINTMENT");
  const [title, setTitle] = useState("Vet appointment");
  const [when, setWhen] = useState("");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const range = monthRange(month);
    Promise.all([
      getEvents(dogId, range.start, range.end, controller.signal),
      getObservationPeriods(dogId, range.start, range.end, false, controller.signal),
      getScheduledItems(dogId, range.start, range.end, controller.signal),
    ]).then(([eventRows, periodRows, scheduledRows]) => {
      setEvents(eventRows);
      setPeriods(periodRows);
      setScheduled(scheduledRows);
    }).catch((err: unknown) => {
      if (err instanceof Error && err.name !== "AbortError") setError(err.message);
    });
    return () => controller.abort();
  }, [dogId, month, refreshKey, localRefreshKey]);

  const days = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    const result: Array<Date | null> = Array(first.getDay()).fill(null);
    for (let day = 1; day <= count; day += 1) result.push(new Date(month.getFullYear(), month.getMonth(), day));
    return result;
  }, [month]);

  const selectedEvents = selectedDate ? events.filter((event) => localKey(new Date(event.event_time)) === selectedDate) : [];
  const selectedItems = selectedDate ? scheduled.filter((item) => localKey(new Date(item.scheduled_for)) === selectedDate) : [];
  const selectedPeriods = selectedDate ? periods.filter((period) => {
    const { start, end } = dateRange(selectedDate);
    return new Date(period.start_time) < new Date(end) && (!period.end_time || new Date(period.end_time) > new Date(start));
  }) : [];
  const editingType = editingEvent ? eventTypes.find((eventType) => eventType.id === editingEvent.event_type_id) ?? null : null;

  const peeCount = selectedEvents.filter((event) => event.event_type_code === "PEE").length;
  const poopCount = selectedEvents.filter((event) => event.event_type_code === "POOP").length;
  const accidents = selectedEvents.filter((event) => ["PEE", "POOP"].includes(event.event_type_code) && event.option_name?.toLowerCase() === "accident").length;

  function changeMonth(delta: number) {
    setMonth(new Date(month.getFullYear(), month.getMonth() + delta, 1));
    setSelectedDate(null);
    setEditingEvent(null);
  }

  function selectDay(date: Date) {
    const key = localKey(date);
    setSelectedDate(key);
    setEditingEvent(null);
    setWhen(`${key}T09:00`);
  }

  function changeType(next: ScheduledItemType) {
    setType(next);
    setTitle(ITEM_LABELS[next]);
  }

  async function addItem() {
    if (!when || !title.trim()) return;
    try {
      await createScheduledItem({
        dog_id: dogId,
        title: title.trim(),
        item_type: type,
        scheduled_for: new Date(when).toISOString(),
        location: location.trim() || null,
        notes: notes.trim() || null,
      });
      setShowAdd(false);
      setLocation("");
      setNotes("");
      setLocalRefreshKey((key) => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add calendar item.");
    }
  }

  async function toggleComplete(item: ScheduledItem) {
    const updated = await updateScheduledItem(item.id, { is_completed: !item.is_completed });
    setScheduled((current) => current.map((entry) => entry.id === updated.id ? updated : entry));
  }

  async function removeItem(item: ScheduledItem) {
    if (!window.confirm(`Delete ${item.title}?`)) return;
    await deleteScheduledItem(item.id);
    setScheduled((current) => current.filter((entry) => entry.id !== item.id));
  }

  function eventChanged() {
    setEditingEvent(null);
    setLocalRefreshKey((key) => key + 1);
    onTimelineChanged();
  }

  return (
    <>
      <section className="calendar-hero">
        <div><p className="eyebrow">History + care plan</p><h1>Calendar</h1><p>Look back at {dogName}’s data, correct past logs, or plan important care ahead.</p></div>
        <button className="save-button" type="button" onClick={() => setShowAdd((value) => !value)}>+ Add item</button>
      </section>

      {error && <p className="event-error">{error}</p>}

      {showAdd && (
        <section className="calendar-add-card">
          <div className="calendar-form-grid">
            <label className="field-label">Type<select value={type} onChange={(event) => changeType(event.target.value as ScheduledItemType)}>{Object.entries(ITEM_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label className="field-label">Title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
            <label className="field-label">Date & time<input type="datetime-local" value={when} onChange={(event) => setWhen(event.target.value)} /></label>
            <label className="field-label">Location <span>Optional</span><input value={location} onChange={(event) => setLocation(event.target.value)} /></label>
          </div>
          <label className="field-label">Notes <span>Optional</span><textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
          <div className="form-actions"><button className="cancel-button" type="button" onClick={() => setShowAdd(false)}>Cancel</button><button className="save-button" type="button" onClick={() => void addItem()}>Add to calendar</button></div>
        </section>
      )}

      <section className="calendar-card">
        <div className="calendar-toolbar">
          <button type="button" onClick={() => changeMonth(-1)}>‹</button>
          <h2>{month.toLocaleDateString("en-US", { month: "long", year: "numeric" })}</h2>
          <button type="button" onClick={() => changeMonth(1)}>›</button>
        </div>
        <div className="calendar-weekdays">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <span key={day}>{day}</span>)}</div>
        <div className="calendar-grid">
          {days.map((date, index) => {
            if (!date) return <div className="calendar-day empty" key={`empty-${index}`} />;
            const key = localKey(date);
            const dayItems = scheduled.filter((item) => localKey(new Date(item.scheduled_for)) === key);
            const notableEvents = events.filter((event) => localKey(new Date(event.event_time)) === key && ["BATH", "VET_VISIT", "GROOMING"].includes(event.event_type_code));
            const hasActivity = events.some((event) => localKey(new Date(event.event_time)) === key);
            return (
              <button className={`calendar-day ${selectedDate === key ? "selected" : ""}`} type="button" key={key} onClick={() => selectDay(date)}>
                <span className="calendar-number">{date.getDate()}</span>
                <span className="calendar-dots">
                  {dayItems.slice(0, 3).map((item) => <span key={item.id} title={item.title}>{ITEM_ICONS[item.item_type]}</span>)}
                  {notableEvents.slice(0, 2).map((event) => <span key={event.id}>{eventIcon(event.event_type_code)}</span>)}
                  {hasActivity && !dayItems.length && !notableEvents.length && <i aria-label="Activity logged" />}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {selectedDate && (
        <section className="calendar-detail">
          <div className="section-heading">
            <div><p className="eyebrow">Selected day</p><h2>{new Date(`${selectedDate}T12:00:00`).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</h2></div>
            <button className="secondary-button" type="button" onClick={() => { setSelectedDate(null); setEditingEvent(null); }}>Close</button>
          </div>
          <div className="day-summary-grid">
            <article><span>Pees</span><strong>{peeCount}</strong></article>
            <article><span>Poops</span><strong>{poopCount}</strong></article>
            <article><span>Accidents</span><strong>{accidents}</strong></article>
            <article><span>Unobserved periods</span><strong>{selectedPeriods.length}</strong></article>
          </div>

          {selectedItems.length > 0 && (
            <div className="calendar-section">
              <h3>Care & appointments</h3>
              {selectedItems.map((item) => (
                <div className={`scheduled-row ${item.is_completed ? "completed" : ""}`} key={item.id}>
                  <span className="scheduled-icon">{ITEM_ICONS[item.item_type]}</span>
                  <div><strong>{item.title}</strong><p>{new Date(item.scheduled_for).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}{item.location ? ` · ${item.location}` : ""}</p>{item.notes && <small>{item.notes}</small>}</div>
                  <div className="scheduled-actions"><button type="button" onClick={() => void toggleComplete(item)}>{item.is_completed ? "Undo" : "Done"}</button><button type="button" onClick={() => void removeItem(item)}>Delete</button></div>
                </div>
              ))}
            </div>
          )}

          <div className="calendar-section">
            <div className="calendar-section-heading"><h3>Activity</h3><span className="muted-copy">Past logs can be corrected here.</span></div>
            {selectedEvents.length ? (
              <div className="history-list">
                {[...selectedEvents].sort((a, b) => new Date(a.event_time).getTime() - new Date(b.event_time).getTime()).map((event) => (
                  <div className="history-row editable-history-row" key={event.id}>
                    <span>{eventIcon(event.event_type_code)}</span>
                    <div><strong>{event.event_type_name}</strong><small>{new Date(event.event_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}{event.option_name ? ` · ${event.option_name}` : ""}</small></div>
                    <button className="secondary-button compact-button" type="button" onClick={() => setEditingEvent(event)}>Edit</button>
                  </div>
                ))}
              </div>
            ) : <p className="muted-copy">No activity logged for this day.</p>}
          </div>

          {editingEvent && editingType && (
            <EventEditor
              key={editingEvent.id}
              dogId={dogId}
              event={editingEvent}
              eventType={editingType}
              options={options}
              onOptionCreated={onOptionCreated}
              onSaved={eventChanged}
              onDeleted={eventChanged}
              onCancel={() => setEditingEvent(null)}
            />
          )}

          <div className="calendar-day-insights">
            <DailyStatsDashboard
              dogId={dogId}
              startTime={dateRange(selectedDate).start}
              endTime={dateRange(selectedDate).end}
              rangeLabel={new Date(`${selectedDate}T12:00:00`).toLocaleDateString("en-US", { month: "long", day: "numeric" })}
              previousStartTime={null}
              previousEndTime={null}
              comparisonLabel={null}
              refreshKey={refreshKey + localRefreshKey}
              preferenceRefreshKey={0}
              embedded
            />
          </div>
        </section>
      )}
    </>
  );
}
